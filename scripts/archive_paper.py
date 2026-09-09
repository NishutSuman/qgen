#!/usr/bin/env python3
"""archive_paper.py — store a dated, never-deleted copy of every generated paper.

Creates <dir>/<date>/ and copies the given files into it. With --flatten-assets,
the contents of an assets dir are copied directly into the dated folder (no
nested assets subfolder). Files can be renamed with --prefix so same-day papers
(e.g. MBA and BS) coexist in one dated folder without clobbering.

The live output/ files stay; the question bank accumulates separately. Re-runs
the same day get _2, _3 suffixes so nothing is ever overwritten.

Usage (IMAT):
    python scripts/archive_paper.py --dir output/imat_real --prefix imat_BS_ \
        --files output/imat_paper.csv output/imat_paper.pdf \
        --assets-dir output/imat_assets --flatten-assets
Usage (normal mcsc):
    python scripts/archive_paper.py --dir output/mcsc_real --prefix mcsc_ \
        --files output/paper.csv output/paper_answer_key.md output/run_report.md
"""
import argparse
import datetime
import os
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="parent dir, e.g. output/imat_real")
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--assets-dir", default=None)
    ap.add_argument("--flatten-assets", action="store_true",
                    help="copy assets dir CONTENTS directly into the dated folder")
    ap.add_argument("--prefix", default="", help="prepended to copied file names")
    ap.add_argument("--date", default=None)
    ap.add_argument("--move", action="store_true",
                    help="remove the source files (and assets dir) after copying, "
                         "so the dated folder is the ONLY copy (no duplicates in output/)")
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    base = os.path.join(args.dir, date)

    def collides(d):
        """True if any incoming file would overwrite something already in d."""
        names = [args.prefix + os.path.basename(f) for f in args.files]
        if args.assets_dir and os.path.isdir(args.assets_dir) and args.flatten_assets:
            names += os.listdir(args.assets_dir)
        return any(os.path.exists(os.path.join(d, n)) for n in names)

    # Merge into today's folder when nothing would be overwritten (so two papers
    # generated the same day land together); only suffix on a real collision.
    dest, n = base, 2
    while os.path.exists(dest) and collides(dest):
        dest = f"{base}_{n}"
        n += 1
    os.makedirs(dest, exist_ok=True)

    copied = []
    for fp in args.files:
        if os.path.exists(fp):
            shutil.copy2(fp, os.path.join(dest, args.prefix + os.path.basename(fp)))
            copied.append(args.prefix + os.path.basename(fp))
            if args.move:
                os.remove(fp)
        else:
            print(f"   [warn] missing, skipped: {fp}")
    if args.assets_dir and os.path.isdir(args.assets_dir):
        if args.flatten_assets:
            for name in sorted(os.listdir(args.assets_dir)):
                src = os.path.join(args.assets_dir, name)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(dest, name))
                    copied.append(name)
        else:
            shutil.copytree(args.assets_dir, os.path.join(dest, os.path.basename(args.assets_dir)))
            copied.append(os.path.basename(args.assets_dir) + "/")
        if args.move:
            shutil.rmtree(args.assets_dir)

    verb = "moved" if args.move else "archived"
    print(f"[OK] {verb} -> {dest}")
    print(f"     contents: {', '.join(copied)}")


if __name__ == "__main__":
    main()
