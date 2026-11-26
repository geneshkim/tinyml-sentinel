"""Start the failure catalog (SDD 4.2.1 "Failure catalog") from RootSE.

Writes one CSV row per RootSE run with the human failure_reason and the text
of the decisive step. Open it in Excel, fill the `pattern` column with a short
name (e.g. repeated_fix, edits_test, missing_resource, task_drift, wrong_file,
premature_submit), then run --summarize to count patterns and pick one short
real example for each.

    python catalog.py raw/rootse --csv catalog_rootse.csv
    python catalog.py --summarize catalog_rootse.csv
"""
import argparse
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "converters"))


def build(raw, out_csv):
    from rootse import load_rows, step_text
    rows = load_rows(raw)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["instance_id", "agent", "model", "failure_id", "n_steps", "pattern",
                    "failure_reason", "decisive_step_text"])
        for r in rows:
            fid = int(r["failure_id"])
            traj = r["original_traj"]
            step = step_text(traj[fid]) if 0 <= fid < len(traj) else ""
            w.writerow([r["instance_id"], r.get("agent"), r.get("model"), fid, len(traj), "",
                        " ".join(str(r.get("failure_reason", "")).split())[:800],
                        " ".join(step.split())[:400]])
    print(f"wrote {len(rows)} rows to {out_csv}; fill the 'pattern' column")


def summarize(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    counts = Counter(r["pattern"].strip() or "(unfilled)" for r in rows)
    for pattern, n in counts.most_common():
        example = next(r for r in rows if (r["pattern"].strip() or "(unfilled)") == pattern)
        print(f"{n:>4}  {pattern:<20} e.g. {example['instance_id']}: {example['failure_reason'][:140]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="?")
    ap.add_argument("--csv", default="catalog_rootse.csv")
    ap.add_argument("--summarize")
    a = ap.parse_args()
    summarize(a.summarize) if a.summarize else build(a.raw, a.csv)
