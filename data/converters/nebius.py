"""nebius/SWE-agent-trajectories -> clean cases and the calibration set.

Source: huggingface.co/datasets/nebius/SWE-agent-trajectories (CC-BY-4.0; the
card also says outputs follow the Llama 3.1 license; cite it). 80,036 SWE-agent
runs. `target` is True when the issue was solved.

    target == True  -> candidate CLEAN cases (no label beyond "it succeeded";
                       hand-check a sample: a solved run can still contain a
                       moment a person would flag, which is really "resolved")
    other rows      -> CALIBRATION text for Nora's AWQ run (never dev or test)

The data is parquet and this machine has no pyarrow, so convert in Colab first:
    import pandas as pd, glob
    df = pd.concat(pd.read_parquet(f) for f in glob.glob("raw/nebius/data/train-0000[0-1]*.parquet"))
    df = df.sample(2000, random_state=5940)          # you do not need all 80k
    df[["instance_id","model_name","target","exit_status","trajectory"]].to_json(
        "raw/nebius_sample.jsonl", orient="records", lines=True)

Then:
    python converters/nebius.py raw/nebius_sample.jsonl --out work/nebius_clean --kind clean --n 120
    python converters/nebius.py raw/nebius_sample.jsonl --out work/nebius_calib --kind calibration --n 128
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schema import make_label, read_jsonl, single_agent_events, write_dataset  # noqa: E402

FINISH_TEXT = "Agent submitted its changes."


def messages(row):
    traj = row["trajectory"]
    if isinstance(traj, str):
        traj = json.loads(traj)
    return traj


def msg_text(m):
    return str(m.get("text") or m.get("content") or "")


def to_steps(row):
    """Pair each 'ai' message with the 'user' observation after it -> one step.
    The system prompt and the first user message (instructions + issue) are
    dropped from the steps; the issue becomes the start event."""
    msgs = [m for m in messages(row) if m.get("role") != "system"]
    task = msg_text(msgs[0]) if msgs and msgs[0].get("role") == "user" else ""
    steps, current = [], None
    for m in msgs[1:]:
        if m.get("role") == "ai":
            if current is not None:
                steps.append(current)
            current = msg_text(m)
        elif current is not None:
            current += "\n[observation] " + msg_text(m)
    if current is not None:
        steps.append(current)
    return task, steps


def task_from_prompt(text):
    """The first user message wraps the issue in instructions; keep the issue."""
    for marker in ("ISSUE:", "<issue>"):
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    for marker in ("INSTRUCTIONS:", "</issue>"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="jsonl exported from the parquet files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--kind", choices=["clean", "calibration"], required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--min-steps", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=80)
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="other work folders whose origins must not be reused (e.g. work/nebius_clean)")
    ap.add_argument("--seed", type=int, default=5940)
    args = ap.parse_args()

    used = set()
    for folder in args.exclude:
        used |= {m["origin_id"] for m in read_jsonl(os.path.join(folder, "meta.jsonl"))}
    rows = read_jsonl(args.raw)
    random.Random(args.seed).shuffle(rows)
    scenarios = []
    for row in rows:
        if len(scenarios) >= args.n:
            break
        solved = bool(row.get("target"))
        if args.kind == "clean" and not solved:
            continue
        origin = f"nebius:{row['instance_id']}:{row.get('model_name')}"
        if origin in used:
            continue
        task, steps = to_steps(row)
        if not args.min_steps <= len(steps) <= args.max_steps:
            continue
        used.add(origin)
        sid = f"nebius_{args.kind}_{len(scenarios):04d}"
        events = single_agent_events(task_from_prompt(task), steps, FINISH_TEXT)
        case = "clean"
        # Calibration files never get scored, but keep the format identical.
        labels = [make_label(sid, "A", case)]
        meta = {"scenario": sid, "source": "nebius", "origin_id": origin, "real": True,
                "case": case if args.kind == "clean" else "calibration",
                "solved": solved, "model": row.get("model_name"), "n_events": len(events)}
        scenarios.append((sid, events, labels, meta))
    write_dataset(args.out, scenarios)
    print(f"wrote {len(scenarios)} {args.kind} scenarios to {args.out}/")


if __name__ == "__main__":
    main()
