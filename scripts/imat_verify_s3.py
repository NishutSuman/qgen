#!/usr/bin/env python3
"""imat_verify_s3.py — confirm chart S3 links are correct and attached everywhere.

For every graph set it verifies three things:
  1. ATTACHMENT — every question of the set carries the SAME image URL(s) (so all
     N questions that share a chart point to one S3 object).
  2. CSV PARITY — each of those questions' rows in the exported CSV embeds that URL
     in contentBody (the link the platform will actually use).
  3. OBJECT EXISTS — the object is present in the bucket (S3 head_object). With
     --public it also tries an unauthenticated GET and reports the HTTP status.

Run with the project venv (boto3, reads creds from .env):
    .venv/bin/python scripts/imat_verify_s3.py --in work/imat/questions.json \
        --csv output/imat_paper.csv [--public]
Exits non-zero on any attachment / parity / missing-object failure.
"""
import argparse
import csv
import json
import os
import sys
import urllib.request

from imat_upload_assets import load_dotenv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/imat/questions.json")
    ap.add_argument("--csv", default="output/imat_paper.csv")
    ap.add_argument("--public", action="store_true",
                    help="also try an anonymous HTTP GET on each URL")
    args = ap.parse_args()

    load_dotenv()
    bucket = os.environ.get("AWS_BUCKET_NAME")
    bucket_url = (os.environ.get("AWS_BUCKET_URL") or "").rstrip("/")
    region = os.environ.get("AWS_REGION")

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)
    with open(args.csv, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    # CSV is written in question order, so row i corresponds to qs[i]
    body_by_id = {q["question_id"]: rows[i]["contentBody"] for i, q in enumerate(qs)}

    sets = {}
    for q in qs:
        s = q.get("stimulus") or {}
        if q.get("shared_set") and s.get("kind") == "graph":
            sets.setdefault(q["set_id"], []).append(q)

    if not sets:
        print("[OK] no graph sets to verify")
        return

    import boto3
    s3 = boto3.client(
        "s3", region_name=region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )

    errors = []
    checked_objs = 0
    for sid, members in sets.items():
        url_sets = {tuple((m.get("stimulus") or {}).get("image_urls") or []) for m in members}
        if len(url_sets) != 1:
            errors.append(f"{sid}: members carry DIFFERENT image_urls {url_sets}")
            continue
        urls = list(url_sets.pop())
        if not urls:
            errors.append(f"{sid}: no image_urls attached")
            continue
        # 2. CSV parity
        for m in members:
            body = body_by_id.get(m["question_id"], "")
            for u in urls:
                if u not in body:
                    errors.append(f"{sid} Q{m['question_id']}: URL not in CSV contentBody")
        # 3. object exists
        for u in urls:
            if bucket_url and u.startswith(bucket_url + "/"):
                key = u[len(bucket_url) + 1:]
            else:
                errors.append(f"{sid}: URL {u} not under bucket {bucket_url}")
                continue
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
                checked_objs += 1
                ct = head.get("ContentType")
                size = head.get("ContentLength")
                msg = f"   {sid}: s3://{bucket}/{key} OK ({ct}, {size} bytes)"
                if args.public:
                    try:
                        with urllib.request.urlopen(u, timeout=10) as resp:
                            msg += f"  | public GET {resp.status}"
                    except Exception as e:  # noqa: BLE001
                        msg += f"  | public GET failed ({e.__class__.__name__}) — bucket likely private"
                print(msg)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{sid}: object missing in bucket ({key}): {e.__class__.__name__}")

    if errors:
        print("[FAIL] S3 verification errors:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"[OK] S3 verified: {len(sets)} graph set(s), {checked_objs} object(s) present, "
          f"links attached to every set question and present in the CSV.")


if __name__ == "__main__":
    main()
