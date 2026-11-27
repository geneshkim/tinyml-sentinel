"""Validate a dataset folder against SDD 3.1.1 and 3.1.2, and print stats.

A dataset folder looks like this:
    <folder>/scenarios/<scenario_id>.jsonl   one event per line (3.1.1)
    <folder>/labels.jsonl                    one line per agent per scenario (3.1.2)
    <folder>/meta.jsonl                      optional provenance (see schema.py)

Usage:
    python validate.py samples
    python validate.py out/dev out/test_real --splits   also checks R7 (no overlap)
"""
import argparse
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

from schema import (CASES, EVENT_FIELDS, EVENT_TYPES, NEEDS_ATTENTION_CASES,
                    approx_tokens, read_jsonl)

# Quality lint (4.2.1 "Quality checks"): implicit agents must never say they
# are stuck, otherwise they are really explicit cases.
STUCK_WORDS = re.compile(
    r"\b(i'?m stuck|i am stuck|need (your )?help|can you (help|provide)|could you (help|provide)|"
    r"please advise|cannot proceed|can't proceed|waiting for (your )?input)\b", re.I)
# The finish text must not give the outcome away.
LEAKY_FINISH = re.compile(r"\b(resolved|unresolved|failed|failure|success|passed|correct)\b", re.I)


def check_folder(folder):
    errors, warnings = [], []
    sc_dir = os.path.join(folder, "scenarios")
    if not os.path.isdir(sc_dir):
        return [f"{folder}: no scenarios/ folder"], [], {}
    scenarios = {}
    for name in sorted(os.listdir(sc_dir)):
        if name.endswith(".jsonl"):
            scenarios[name[:-6]] = read_jsonl(os.path.join(sc_dir, name))

    # ---- events (3.1.1) ----
    agents_of = {}
    for sid, events in scenarios.items():
        where = f"{sid}"
        if not events:
            errors.append(f"{where}: empty scenario")
            continue
        seen_start, finished = set(), set()
        for n, ev in enumerate(events):
            for field, typ in EVENT_FIELDS.items():
                if field not in ev:
                    errors.append(f"{where} line {n}: missing {field}")
                elif not isinstance(ev[field], typ) or (typ is int and isinstance(ev[field], bool)):
                    errors.append(f"{where} line {n}: {field} should be {typ.__name__}")
            extra = set(ev) - set(EVENT_FIELDS)
            if extra:
                errors.append(f"{where} line {n}: unexpected fields {sorted(extra)}")
            if ev.get("i") != n:
                errors.append(f"{where} line {n}: i is {ev.get('i')}, expected {n}")
            a, t = ev.get("agent"), ev.get("type")
            if t not in EVENT_TYPES:
                errors.append(f"{where} line {n}: type {t!r} not in {EVENT_TYPES}")
            if a in finished:
                errors.append(f"{where} line {n}: agent {a} has an event after its finish")
            if t == "start":
                if a in seen_start:
                    errors.append(f"{where} line {n}: agent {a} starts twice")
                seen_start.add(a)
            elif a not in seen_start:
                errors.append(f"{where} line {n}: agent {a} has {t} before its start")
            if t == "finish":
                finished.add(a)
            if not str(ev.get("text", "")).strip():
                warnings.append(f"{where} line {n}: empty text")
        missing_finish = seen_start - finished
        if missing_finish:
            warnings.append(f"{where}: agents without finish: {sorted(missing_finish)}")
        agents_of[sid] = seen_start

    # ---- labels (3.1.2) ----
    labels_path = os.path.join(folder, "labels.jsonl")
    labels = read_jsonl(labels_path) if os.path.exists(labels_path) else []
    if not labels:
        errors.append(f"{folder}: labels.jsonl missing or empty")
    labelled = set()
    for n, lab in enumerate(labels):
        where = f"labels line {n} ({lab.get('scenario')}/{lab.get('agent')})"
        sid, agent, case = lab.get("scenario"), lab.get("agent"), lab.get("case")
        if sid not in scenarios:
            errors.append(f"{where}: no scenario file")
            continue
        if agent not in agents_of.get(sid, ()):
            errors.append(f"{where}: agent not in scenario")
        if (sid, agent) in labelled:
            errors.append(f"{where}: duplicate label")
        labelled.add((sid, agent))
        if case not in CASES:
            errors.append(f"{where}: case {case!r} not in {CASES}")
            continue
        need = case in NEEDS_ATTENTION_CASES
        if lab.get("needs_attention") is not need:
            errors.append(f"{where}: needs_attention should be {need} for {case}")
        fe = lab.get("from_event")
        if need:
            if not isinstance(fe, int) or isinstance(fe, bool):
                errors.append(f"{where}: from_event must be an integer")
                continue
            events = scenarios[sid]
            if not 0 <= fe < len(events):
                errors.append(f"{where}: from_event {fe} out of range")
                continue
            ev = events[fe]
            if ev["agent"] != agent:
                errors.append(f"{where}: from_event {fe} belongs to agent {ev['agent']}")
            if ev["type"] == "start":
                errors.append(f"{where}: from_event {fe} points at a start event")
        elif "from_event" in lab:
            errors.append(f"{where}: from_event must be absent when needs_attention is false")
        if case == "implicit":
            for ev in scenarios[sid]:
                if ev["agent"] == agent and ev["type"] != "start" and STUCK_WORDS.search(ev["text"]):
                    warnings.append(f"{where}: implicit agent sounds stuck at event {ev['i']}: "
                                    f"{STUCK_WORDS.search(ev['text']).group(0)!r}")
                    break
    for sid, agents in agents_of.items():
        for a in agents:
            if (sid, a) not in labelled:
                errors.append(f"{sid}/{a}: agent has no label")
    for sid, events in scenarios.items():
        for ev in events:
            if ev.get("type") == "finish" and LEAKY_FINISH.search(ev.get("text", "")):
                warnings.append(f"{sid} event {ev['i']}: finish text may leak the outcome: "
                                f"{ev['text'][:60]!r}")

    # ---- stats ----
    cases = Counter(l.get("case") for l in labels)
    per_agent_events = defaultdict(int)
    tokens = []
    for sid, events in scenarios.items():
        for ev in events:
            per_agent_events[(sid, ev.get("agent"))] += 1
        tokens.append(sum(approx_tokens(ev.get("text", "")) for ev in events))
    stats = {
        "scenarios": len(scenarios),
        "agents": len(labels),
        "cases": dict(cases),
        "events_per_agent_median": statistics.median(per_agent_events.values()) if per_agent_events else 0,
        "approx_tokens_per_scenario_median": statistics.median(tokens) if tokens else 0,
        "approx_tokens_per_scenario_max": max(tokens) if tokens else 0,
    }
    return errors, warnings, stats


def check_splits(folders):
    """R7: no scenario id and no origin_id may appear in two folders."""
    errors = []
    owner_sid, owner_origin = {}, {}
    for folder in folders:
        meta_path = os.path.join(folder, "meta.jsonl")
        if not os.path.exists(meta_path):
            errors.append(f"{folder}: no meta.jsonl, cannot check origins")
            continue
        for m in read_jsonl(meta_path):
            for key, owner in (("scenario", owner_sid), ("origin_id", owner_origin)):
                vals = m.get(key)
                for v in (vals if isinstance(vals, list) else [vals]):
                    if v is None:
                        continue
                    if v in owner and owner[v] != folder:
                        errors.append(f"{key} {v!r} is in both {owner[v]} and {folder}")
                    owner[v] = folder
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--splits", action="store_true", help="also check that folders do not overlap (R7)")
    ap.add_argument("--max-warnings", type=int, default=20)
    args = ap.parse_args()
    total_errors = 0
    for folder in args.folders:
        errors, warnings, stats = check_folder(folder)
        print(f"== {folder}")
        print("   " + ", ".join(f"{k}={v}" for k, v in stats.items()))
        for w in warnings[: args.max_warnings]:
            print("   WARN ", w)
        if len(warnings) > args.max_warnings:
            print(f"   ... {len(warnings) - args.max_warnings} more warnings")
        for e in errors:
            print("   ERROR", e)
        total_errors += len(errors)
    if args.splits:
        errs = check_splits(args.folders)
        for e in errs:
            print("   SPLIT ERROR", e)
        total_errors += len(errs)
    print("OK" if total_errors == 0 else f"FAILED with {total_errors} errors")
    sys.exit(1 if total_errors else 0)


if __name__ == "__main__":
    main()
