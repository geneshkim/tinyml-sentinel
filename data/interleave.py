"""Merge single-agent sessions into one multi-agent scenario (SDD 4.2.1).

Each agent keeps its own event order. At every step the schedule picks one
agent at random (seeded) among those that have started and still have events.
Agents are retagged A, B, C... and each label's from_event is moved from the
agent's own index to the index in the merged stream.

Because the result depends only on the inputs and the seed, multi-agent test
scenarios can be rebuilt from a frozen single-agent test set at any time.

CLI:
    python interleave.py --in out/test_real --out out/test_real_mix3 --agents 3 --n 20 --seed 5940
"""
import argparse
import os
import random
import string

from schema import read_jsonl, write_dataset


def interleave(scenario_id, parts, seed, max_stagger=5):
    """parts: list of (events, label) for single-agent sessions.
    Returns (events, labels) for the merged scenario."""
    rng = random.Random(seed)
    tags = list(string.ascii_uppercase[: len(parts)])
    queues = [list(events) for events, _ in parts]
    # Agent 0 starts at once; the others join after a few events.
    join_at = [0] + [rng.randint(1, max_stagger) * (k + 1) for k in range(1, len(parts))]
    pos = [0] * len(parts)
    local_to_global = [dict() for _ in parts]
    out = []
    while any(pos[k] < len(queues[k]) for k in range(len(parts))):
        ready = [k for k in range(len(parts)) if pos[k] < len(queues[k]) and join_at[k] <= len(out)]
        if not ready:  # nobody has joined yet: jump to the next agent to join
            k = min((k for k in range(len(parts)) if pos[k] < len(queues[k])), key=lambda k: join_at[k])
            join_at[k] = len(out)
            continue
        k = rng.choice(ready)
        ev = queues[k][pos[k]]
        local_to_global[k][ev["i"]] = len(out)
        out.append({"i": len(out), "agent": tags[k], "type": ev["type"], "text": ev["text"]})
        pos[k] += 1
    labels = []
    for k, (_, label) in enumerate(parts):
        new = {"scenario": scenario_id, "agent": tags[k], "case": label["case"],
               "needs_attention": label["needs_attention"]}
        if "from_event" in label:
            new["from_event"] = local_to_global[k][label["from_event"]]
        labels.append(new)
    return out, labels


def load_single_agent(folder):
    labels = {l["scenario"]: l for l in read_jsonl(os.path.join(folder, "labels.jsonl"))}
    metas = {}
    meta_path = os.path.join(folder, "meta.jsonl")
    if os.path.exists(meta_path):
        metas = {m["scenario"]: m for m in read_jsonl(meta_path)}
    sessions = []
    for sid, label in sorted(labels.items()):
        events = read_jsonl(os.path.join(folder, "scenarios", f"{sid}.jsonl"))
        if len({e["agent"] for e in events}) != 1:
            continue  # skip scenarios that are already mixed
        sessions.append((sid, events, label, metas.get(sid, {})))
    return sessions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="folder of single-agent scenarios")
    ap.add_argument("--out", required=True)
    ap.add_argument("--agents", type=int, default=3)
    ap.add_argument("--n", type=int, default=20, help="number of mixed scenarios")
    ap.add_argument("--seed", type=int, default=5940)
    args = ap.parse_args()
    sessions = load_single_agent(args.inp)
    rng = random.Random(args.seed)
    scenarios = []
    for j in range(args.n):
        picked = rng.sample(sessions, args.agents)
        sid = f"mix{args.agents}_{j:03d}"
        events, labels = interleave(sid, [(p[1], p[2]) for p in picked], seed=args.seed + j)
        meta = {"scenario": sid, "source": "mix", "origin_id": [p[3].get("origin_id", p[0]) for p in picked],
                "real": all(p[3].get("real", False) for p in picked), "case": "mixed",
                "note": "from " + ", ".join(p[0] for p in picked)}
        scenarios.append((sid, events, labels, meta))
    write_dataset(args.out, scenarios)
    print(f"wrote {len(scenarios)} mixed scenarios to {args.out}/")


if __name__ == "__main__":
    main()
