#!/usr/bin/env python3
"""imat_upload_assets.py — upload chart PNGs to S3 and attach the URLs.

For every graph set, upload each local chart PNG to the org S3 bucket and record
the resulting public URL in stimulus.image_urls on EVERY member of the set (so
all questions that share the chart carry the same link — no manual link pasting
per question on the platform). The CSV then embeds the S3 URL in each question's
contentBody; the PDF still uses the local PNG once per set.

Credentials are read from the environment or a local .env (gitignored):
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
    AWS_BUCKET_NAME, AWS_BUCKET_URL

Run with the project venv (needs boto3):
    .venv/bin/python scripts/imat_upload_assets.py --in work/imat/questions.json \
        --base output --prefix imat --date 2026-06-25
    # add --dry-run to compute the URLs WITHOUT uploading (offline / tests)

S3 keys are <prefix>/<date>/<filename>, so re-runs are idempotent per paper-day.
"""
import argparse
import json
import os
import sys


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def graph_sets(qs):
    sets = {}
    for q in qs:
        s = q.get("stimulus") or {}
        if q.get("shared_set") and s.get("kind") == "graph" and s.get("images"):
            sets.setdefault(q["set_id"], []).append(q)
    return sets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/imat/questions.json")
    ap.add_argument("--base", default="output",
                    help="dir the stimulus.images paths are relative to")
    ap.add_argument("--prefix", default="imat")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--acl", default=None, help="optional object ACL, e.g. public-read")
    args = ap.parse_args()

    load_dotenv()
    bucket = os.environ.get("AWS_BUCKET_NAME")
    bucket_url = (os.environ.get("AWS_BUCKET_URL") or "").rstrip("/")
    region = os.environ.get("AWS_REGION")
    date = args.date
    if date is None:
        import datetime
        date = datetime.date.today().isoformat()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)
    sets = graph_sets(qs)
    if not sets:
        print("[OK] no graph sets — nothing to upload")
        return

    if not args.dry_run:
        if not (bucket and bucket_url and region):
            sys.exit("[FAIL] missing AWS_BUCKET_NAME/AWS_BUCKET_URL/AWS_REGION "
                     "(set them in .env). Use --dry-run to skip uploading.")
        try:
            import boto3
        except ImportError:
            sys.exit("[FAIL] boto3 not installed in the venv (.venv/bin/pip install boto3)")
        s3 = boto3.client(
            "s3", region_name=region,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )

    uploaded = 0
    for sid, members in sets.items():
        images = (members[0].get("stimulus") or {}).get("images", [])
        urls = []
        for rel in images:
            fname = os.path.basename(rel)
            key = f"{args.prefix}/{date}/{fname}"
            url = f"{bucket_url}/{key}" if bucket_url else f"s3://{bucket}/{key}"
            if not args.dry_run:
                local = os.path.join(args.base, rel)
                if not os.path.exists(local):
                    sys.exit(f"[FAIL] local chart missing: {local}")
                extra = {"ContentType": "image/png"}
                if args.acl:
                    extra["ACL"] = args.acl
                s3.upload_file(local, bucket, key, ExtraArgs=extra)
                uploaded += 1
            urls.append(url)
        for m in members:               # identical stimulus across the set
            m["stimulus"]["image_urls"] = urls

    with open(args.inp, "w", encoding="utf-8") as f:
        json.dump(qs, f, indent=2, ensure_ascii=False)

    mode = "DRY-RUN (no upload)" if args.dry_run else f"uploaded {uploaded} object(s)"
    print(f"[OK] S3 assets: {mode}; attached URLs to {len(sets)} graph set(s) -> {args.inp}")


if __name__ == "__main__":
    main()
