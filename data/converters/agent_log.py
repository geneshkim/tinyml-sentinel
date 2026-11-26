"""Our own agent runs -> scenario and label files (explicit and resolved cases).

Run a coding agent that is NOT Qwen (Claude Code, Codex) on a small task with a
built-in trap, let it work normally, then convert its log here. The agent never
sees our format.

Claude Code keeps each session as JSONL under ~/.claude/projects/<project>/<id>.jsonl.
Each line has "type" ("user" or "assistant") and "message" with content blocks
(text, tool_use, tool_result). This converter turns:
    first user text                          -> start event (the task)
    each assistant turn + its tool results   -> one output event
    end of log                               -> finish event

Codex: TO FILL. Its logs (~/.codex/sessions/...) use a different shape; add a
parse_codex() that returns (task, steps) like parse_claude_code() and reuse the rest.

Labels are by hand. Convert once, read it with show.py, then convert again
with the label:
    python converters/agent_log.py run1.jsonl --id own_explicit_001 --out work/own_runs
    python show.py work/own_runs/scenarios/own_explicit_001.jsonl
    python converters/agent_log.py run1.jsonl --id own_explicit_001 --out work/own_runs \
        --case explicit --from-event 14 --trap "missing API key"
Each call adds one scenario to the --out folder (re-running an id replaces it).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schema import CASES, make_label, read_jsonl, single_agent_events, write_jsonl  # noqa: E402

FINISH_TEXT = "Session ended."


def _blocks(message):
    content = message.get("content", "")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content or []


def _block_text(b):
    t = b.get("type")
    if t == "text":
        return b.get("text", "")
    if t == "tool_use":
        return f"[tool {b.get('name')}] " + json.dumps(b.get("input", {}), ensure_ascii=False)
    if t == "tool_result":
        c = b.get("content", "")
        if isinstance(c, list):
            c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
        return "[result] " + str(c)
    return ""  # thinking blocks and images are skipped


def parse_claude_code(path):
    """One step = consecutive assistant lines plus the tool results after them.
    A new step starts when the assistant speaks again after a result."""
    task, steps, current, prev = None, [], None, None
    for line in read_jsonl(path):
        kind, msg = line.get("type"), line.get("message") or {}
        if kind not in ("user", "assistant"):
            continue
        text = "\n".join(x for x in (_block_text(b) for b in _blocks(msg)) if x.strip())
        if not text.strip():
            continue
        is_result = any(b.get("type") == "tool_result" for b in _blocks(msg))
        if kind == "user" and not is_result and task is None:
            task = text
            continue
        if kind == "assistant":
            if current is None or prev in ("result", "user"):
                if current is not None:
                    steps.append(current)
                current = text
            else:
                current += "\n" + text
            prev = "assistant"
        elif is_result:
            current = text if current is None else current + "\n" + text
            prev = "result"
        else:  # a later human message stays visible: it is part of the session
            if current is not None:
                steps.append(current)
            current, prev = "[user] " + text, "user"
    if current is not None:
        steps.append(current)
    return task or "", steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--id", required=True, help="scenario id, e.g. own_explicit_001")
    ap.add_argument("--out", default="work/own_runs")
    ap.add_argument("--format", choices=["claude_code"], default="claude_code")
    ap.add_argument("--case", choices=CASES)
    ap.add_argument("--from-event", type=int)
    ap.add_argument("--trap", default="", help="the trap built into the task, for meta and the memo")
    ap.add_argument("--agent-system", default="Claude Code")
    args = ap.parse_args()

    task, steps = parse_claude_code(args.log)
    events = single_agent_events(task, steps, FINISH_TEXT)
    sc_path = os.path.join(args.out, "scenarios", f"{args.id}.jsonl")
    write_jsonl(sc_path, events)
    print(f"wrote {len(events)} events to {sc_path}")
    if not args.case:
        print("no --case given: read it with show.py, then re-run with --case (and --from-event)")
        return

    def upsert(path, row):
        rows = read_jsonl(path) if os.path.exists(path) else []
        rows = [r for r in rows if r.get("scenario") != args.id] + [row]
        write_jsonl(path, rows)

    upsert(os.path.join(args.out, "labels.jsonl"), make_label(args.id, "A", args.case, args.from_event))
    upsert(os.path.join(args.out, "meta.jsonl"), {
        "scenario": args.id, "source": "own_run", "origin_id": f"own:{args.id}", "real": True,
        "case": args.case, "agent_system": args.agent_system, "trap": args.trap,
        "note": "hand-labelled"})
    print(f"labelled {args.id} as {args.case}" + (f" from event {args.from_event}" if args.from_event else ""))


if __name__ == "__main__":
    main()
