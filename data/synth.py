"""Synthetic sessions from seeds (after the poster). Labels are written at generation time.

The generator model must NOT be Qwen (the model under test). Use Claude, GPT,
Gemini etc. No API key is needed: print a prompt, paste it into the chat, save
the reply as one JSON object per line, then ingest.

    python synth.py prompt --seed work/rootse/scenarios/<id>.jsonl --case implicit --pattern repeated_fix > p.txt
    # paste p.txt into a non-Qwen model; append its JSON reply as one line to raw/synth_replies.jsonl
    python synth.py ingest raw/synth_replies.jsonl --out work/synthetic --generator "claude-x"

Reply format the model is asked for:
    {"task": "...", "case": "implicit", "pattern": "repeated_fix",
     "steps": [{"text": "...", "problem_starts": false}, ...]}
Exactly one step has problem_starts=true for explicit and implicit cases; none for resolved and clean.
"""
import argparse
import json
import os

from schema import CASES, NEEDS_ATTENTION_CASES, make_label, read_jsonl, single_agent_events, write_dataset

CASE_RULES = {
    "explicit": "At some step the agent clearly asks the human for something only a person can give "
                "(a secret, an access right, a product decision). Mark that step problem_starts=true.",
    "implicit": "The agent gets into trouble ({pattern}) but NEVER says it is stuck or asks for help, and it "
                "sounds confident to the end. Mark the first step where a careful human watching the log "
                "should step in as problem_starts=true.",
    "resolved": "The agent hits a real problem (failing test, wrong import, bad assumption) and fixes it "
                "itself within a few steps. No step has problem_starts=true.",
    "clean": "Routine work. Use the same kind of vocabulary as the other cases (test runs, warnings, edits, "
             "error messages that are expected), so keywords alone cannot tell it apart. No step has problem_starts=true.",
}

PROMPT = """You are writing a realistic log of an autonomous coding agent (like SWE-agent or Claude Code)
working in a Python repository. Write it in the same style as the example session below.

Rules:
- {rule}
- 15 to 40 steps. Each step is one agent action with its tool output (commands, file edits, test results).
- Do not write a summary of how it went at the end, and do not use the words "resolved", "failed", "success".
- Do not copy the example's task; invent a different repository and task.

Example session (style only):
{example}

Reply with ONE JSON object and nothing else:
{{"task": "...", "case": "{case}", "pattern": "{pattern}", "steps": [{{"text": "...", "problem_starts": false}}]}}
"""


def cmd_prompt(args):
    events = read_jsonl(args.seed)
    example = "\n".join(f"[{e['type']}] {e['text'][:300]}" for e in events[: args.example_events])
    rule = CASE_RULES[args.case].format(pattern=args.pattern or "a problem")
    print(PROMPT.format(rule=rule, example=example, case=args.case, pattern=args.pattern or ""))


def cmd_ingest(args):
    scenarios, skipped = [], 0
    for n, rep in enumerate(read_jsonl(args.replies)):
        case = rep.get("case")
        steps = rep.get("steps") or []
        marked = [k for k, s in enumerate(steps) if s.get("problem_starts")]
        need = case in NEEDS_ATTENTION_CASES
        if case not in CASES or (need and len(marked) != 1) or (not need and marked):
            skipped += 1
            print(f"skip reply {n}: case={case} marked={marked}")
            continue
        sid = f"synth_{case}_{n:04d}"
        events = single_agent_events(rep["task"], [s["text"] for s in steps], "Agent submitted its changes.")
        label = make_label(sid, "A", case, marked[0] + 1 if need else None)
        meta = {"scenario": sid, "source": "synthetic", "origin_id": f"synth:{n}", "real": False,
                "case": case, "pattern": rep.get("pattern"), "generator": args.generator,
                "seed_scenario": rep.get("seed")}
        scenarios.append((sid, events, [label], meta))
    write_dataset(args.out, scenarios)
    print(f"wrote {len(scenarios)} synthetic scenarios to {args.out}/ ({skipped} skipped)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompt")
    p.add_argument("--seed", required=True)
    p.add_argument("--case", choices=CASES, required=True)
    p.add_argument("--pattern", default="")
    p.add_argument("--example-events", type=int, default=12)
    i = sub.add_parser("ingest")
    i.add_argument("replies")
    i.add_argument("--out", default="work/synthetic")
    i.add_argument("--generator", required=True, help="which model wrote them (must not be Qwen)")
    a = ap.parse_args()
    if a.cmd == "ingest" and "qwen" in a.generator.lower():
        raise SystemExit("the generator must not be the model under test (SDD 4.2.1)")
    cmd_prompt(a) if a.cmd == "prompt" else cmd_ingest(a)
