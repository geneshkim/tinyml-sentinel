"""Assign converted scenarios to calibration / dev / test_real / test_synth, and freeze.

Reads work folders (each with scenarios/, labels.jsonl, meta.jsonl) and a plan,
groups scenarios by origin_id so one original run never lands in two splits
(R7), and copies them into out/<split>/. Then writes out/MANIFEST.json with a
hash of every file, so anyone can confirm the test set has not changed.

    python split.py --plan split_plan.json --out out
    python validate.py out/calibration out/dev out/test_real --splits
    python split.py --verify out          # after freezing: did anything change?

Plan format (counts are scenarios; "rest" takes what is left):
    {"seed": 5940,
     "sources": {"work/rootse":       {"dev": 20, "test_real": "rest"},
                 "work/nebius_clean": {"dev": 20, "test_real": "rest"},
                 "work/nebius_calib": {"calibration": "rest"},
                 "work/own_runs":     {"dev": 2, "test_real": "rest"},
                 "work/synthetic":    {"dev": 30, "test_synth": "rest"}}}
"""
import argparse
import hashlib
import json
import os
import random
import shutil
from collections import defaultdict

from schema import read_jsonl, write_jsonl

SPLITS = ("calibration", "dev", "test_real", "test_synth")


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def manifest(out):
    files = {}
    for root, _, names in os.walk(out):
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, out).replace(os.sep, "/")
            if rel != "MANIFEST.json":
                files[rel] = sha(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan")
    ap.add_argument("--out", default="out")
    ap.add_argument("--verify", help="folder with a MANIFEST.json to check")
    args = ap.parse_args()

    if args.verify:
        with open(os.path.join(args.verify, "MANIFEST.json")) as f:
            frozen = json.load(f)["files"]
        now = manifest(args.verify)
        changed = sorted(k for k in set(frozen) | set(now) if frozen.get(k) != now.get(k))
        print("unchanged" if not changed else "CHANGED:\n  " + "\n  ".join(changed))
        raise SystemExit(1 if changed else 0)

    with open(args.plan) as f:
        plan = json.load(f)
    rng = random.Random(plan.get("seed", 5940))
    if os.path.isdir(args.out):
        shutil.rmtree(args.out)
    buckets = {s: {"scenarios": [], "labels": [], "meta": []} for s in SPLITS}
    counts = defaultdict(lambda: defaultdict(int))

    for src, alloc in plan["sources"].items():
        metas = read_jsonl(os.path.join(src, "meta.jsonl"))
        labels = defaultdict(list)
        for lab in read_jsonl(os.path.join(src, "labels.jsonl")):
            labels[lab["scenario"]].append(lab)
        groups = defaultdict(list)  # origin -> metas
        for m in metas:
            key = json.dumps(m.get("origin_id", m["scenario"]))
            groups[key].append(m)
        order = sorted(groups)
        rng.shuffle(order)
        for split, n in alloc.items():
            if split not in SPLITS:
                raise SystemExit(f"unknown split {split!r}")
            take = len(order) if n == "rest" else int(n)
            chosen, order = order[:take], order[take:]
            for key in chosen:
                for m in groups[key]:
                    buckets[split]["scenarios"].append(os.path.join(src, "scenarios", m["scenario"] + ".jsonl"))
                    buckets[split]["labels"].extend(labels[m["scenario"]])
                    buckets[split]["meta"].append(m)
                    counts[split][m.get("case", "?")] += 1
        if order:
            print(f"note: {len(order)} origins from {src} left unassigned")

    for split, b in buckets.items():
        if not b["meta"]:
            continue
        d = os.path.join(args.out, split)
        os.makedirs(os.path.join(d, "scenarios"), exist_ok=True)
        for p in b["scenarios"]:
            shutil.copy(p, os.path.join(d, "scenarios", os.path.basename(p)))
        write_jsonl(os.path.join(d, "labels.jsonl"), b["labels"])
        write_jsonl(os.path.join(d, "meta.jsonl"), b["meta"])
    with open(os.path.join(args.out, "MANIFEST.json"), "w") as f:
        json.dump({"plan": plan, "counts": {k: dict(v) for k, v in counts.items()},
                   "files": manifest(args.out)}, f, indent=1)
    for split in SPLITS:
        if counts[split]:
            print(f"{split:<12} " + ", ".join(f"{c}={n}" for c, n in sorted(counts[split].items())))


if __name__ == "__main__":
    main()
