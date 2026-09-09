#!/usr/bin/env python3
"""imat_charts.py — render DILR graph stimuli to PNG (matplotlib).

For every shared set whose stimulus.kind == 'graph', render each chart spec in
stimulus.chart (a single spec or a list) to output/imat_assets/<set_id>_<i>.png
and record the relative paths in stimulus.images on EVERY member of the set
(stimuli are identical across a set). Tables stay markdown — only graphs render.

Requires matplotlib — run with the project venv:
    .venv/bin/python scripts/imat_charts.py --in work/imat/questions.json \
        --assets output/imat_assets

Chart spec:
    {"type": "grouped_bar", "title": "Units Sold (in '000)",
     "y_label": "Units ('000)", "categories": ["ProBook", ...],
     "series": {"Q1": [4,2.5,3,5], "Q2": [...], "Q3": [...]}}
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def render_grouped_bar(spec, path):
    cats = spec["categories"]
    series = spec["series"]
    n_series = len(series)
    x = range(len(cats))
    width = 0.8 / max(1, n_series)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, (name, vals) in enumerate(series.items()):
        offs = [xi + (i - (n_series - 1) / 2) * width for xi in x]
        bars = ax.bar(offs, vals, width, label=str(name))
        ax.bar_label(bars, fmt="%g", fontsize=8, padding=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats)
    ax.set_ylabel(spec.get("y_label", ""))
    ax.set_title(spec.get("title", ""))
    ax.legend()
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/imat/questions.json")
    ap.add_argument("--assets", default="output/imat_assets")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)
    os.makedirs(args.assets, exist_ok=True)

    # group graph sets
    sets = {}
    for q in qs:
        s = q.get("stimulus") or {}
        if q.get("shared_set") and s.get("kind") == "graph":
            sets.setdefault(q["set_id"], []).append(q)

    rendered = 0
    for sid, members in sets.items():
        spec = (members[0].get("stimulus") or {}).get("chart")
        specs = spec if isinstance(spec, list) else [spec]
        images = []
        for i, sp in enumerate(specs):
            if not sp:
                continue
            fname = f"{sid}_{i}.png"
            render_grouped_bar(sp, os.path.join(args.assets, fname))
            images.append(os.path.join(os.path.basename(args.assets), fname))
            rendered += 1
        for m in members:               # identical stimulus across the set
            m["stimulus"]["images"] = images

    with open(args.inp, "w", encoding="utf-8") as f:
        json.dump(qs, f, indent=2, ensure_ascii=False)
    print(f"[OK] rendered {rendered} chart(s) for {len(sets)} graph set(s) "
          f"-> {args.assets}")


if __name__ == "__main__":
    main()
