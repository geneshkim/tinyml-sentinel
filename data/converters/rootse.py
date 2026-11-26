"""RootSE -> scenario and label files (implicit cases).

Source: huggingface.co/datasets/dengdan1999/RootSE (MIT). 102 failed coding-agent
runs. Human experts marked the earliest decisive error step (`failure_id`) and
wrote a reason (`failure_reason`).

Fields used:
    instance_id, original_mission_prompt   -> start event
    original_traj[k].thought/action/observation -> output event k+1
    failure_id                              -> from_event (see LABEL MAPPING)
    failure_reason, agent, model            -> meta.jsonl only (never in the stream)
Fields deliberately NOT used, because they would leak the answer:
    gold_patch, test_patch, failed_tests

LABEL MAPPING (TO DECIDE, Moses; placeholder in SDD 4.2.1):
    "decisive" (default)  from_event = event of the decisive step
    "plus_k"              from_event = decisive event + k  (--k)
Pick one before the test set is frozen; record it in the memo.

Download first (Hugging Face is not reachable from every machine; Colab works):
    from huggingface_hub import snapshot_download
    snapshot_download("dengdan1999/RootSE", repo_type="dataset", local_dir="raw/rootse")

Then:
    python converters/rootse.py raw/rootse --out work/rootse --inspect 3   # look first
    python converters/rootse.py raw/rootse --out work/rootse
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schema import make_label, single_agent_events, write_dataset  # noqa: E402

FINISH_TEXT = "Agent submitted its changes."  # neutral: must not reveal pass/fail


def load_rows(path):
    files = [path] if os.path.isfile(path) else sorted(
        glob.glob(os.path.join(path, "**", "*.json*"), recursive=True))
    rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            text = fh.read().strip()
        if not text:
            continue
        if f.endswith(".jsonl"):
            rows.extend(json.loads(line) for line in text.splitlines() if line.strip())
        else:
            data = json.loads(text)
            if isinstance(data, dict):  # {"data": [...]} or a single instance
                data = next((v for v in data.values() if isinstance(v, list)), [data])
            rows.extend(data)
    return [r for r in rows if isinstance(r, dict) and "original_traj" in r]


def step_text(step):
    """One trajectory step -> one event text. TO CHECK: the field names on the
    real data (print one with --inspect)."""
    if isinstance(step, str):
        return step
    parts = []
    for key in ("thought", "action", "observation"):
        val = step.get(key)
        if val:
            val = val if isinstance(val, str) else json.dumps(val)
            parts.append(val if key == "thought" else f"[{key}] {val}")
    if not parts and step.get("response"):
        parts.append(str(step["response"]))
    return "\n".join(parts)


def convert(row, mapping="decisive", k=0, index_base=0):
    sid = "rootse_" + str(row["instance_id"]).replace("/", "__")
    agent_name = f"{row.get('agent', '?')}/{row.get('model', '?')}"
    sid += "_" + "".join(c if c.isalnum() else "-" for c in agent_name)[:40]
    steps = [step_text(s) for s in row["original_traj"]]
    events = single_agent_events(row.get("original_mission_prompt", ""), steps, FINISH_TEXT)
    decisive_step = int(row["failure_id"]) - index_base   # 0-based step index
    decisive_event = decisive_step + 1                     # event 0 is the start event
    from_event = decisive_event + (k if mapping == "plus_k" else 0)
    from_event = min(from_event, len(events) - 1)          # never past the finish event
    label = make_label(sid, "A", "implicit", from_event)
    meta = {"scenario": sid, "source": "rootse", "origin_id": f"rootse:{row['instance_id']}:{agent_name}",
            "real": True, "case": "implicit", "agent_system": row.get("agent"), "model": row.get("model"),
            "repo": row.get("repo"), "decisive_event": decisive_event, "n_events": len(events),
            "note": row.get("failure_reason", "")}
    return sid, events, [label], meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="downloaded RootSE file or folder")
    ap.add_argument("--out", default="work/rootse")
    ap.add_argument("--mapping", choices=["decisive", "plus_k"], default="decisive")
    ap.add_argument("--k", type=int, default=0)
    ap.add_argument("--index-base", type=int, default=0,
                    help="TO CHECK: 0 if failure_id counts steps from 0, 1 if from 1")
    ap.add_argument("--inspect", type=int, default=0, help="print N rows around the decisive step and stop")
    args = ap.parse_args()
    rows = load_rows(args.raw)
    print(f"loaded {len(rows)} rows")
    if args.inspect:
        for row in rows[: args.inspect]:
            fid = int(row["failure_id"])
            traj = row["original_traj"]
            print("=" * 80)
            print(row["instance_id"], row.get("agent"), row.get("model"), f"failure_id={fid} of {len(traj)} steps")
            print("REASON:", row.get("failure_reason", "")[:500])
            print("STEP KEYS:", list(traj[0].keys()) if isinstance(traj[0], dict) else type(traj[0]))
            for j in range(max(0, fid - 1), min(len(traj), fid + 2)):
                print(f"--- step {j}{'  <== failure_id' if j == fid else ''}")
                print(step_text(traj[j])[:600])
        return
    scenarios = [convert(r, args.mapping, args.k, args.index_base) for r in rows]
    write_dataset(args.out, scenarios)
    print(f"wrote {len(scenarios)} scenarios to {args.out}/  (mapping={args.mapping}, k={args.k})")


if __name__ == "__main__":
    main()
