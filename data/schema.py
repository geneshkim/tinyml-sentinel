"""Shared definitions for the Data workstream (SDD 3.1.1, 3.1.2).

Everything here uses only the standard library, so no tokenizer or model is needed.
Positions are always EVENT INDICES (the `i` field), never token counts.
"""
import json
import os

# --- 3.1.1 Scenario events -------------------------------------------------
EVENT_TYPES = ("start", "output", "finish")
EVENT_FIELDS = {"i": int, "agent": str, "type": str, "text": str}

# --- 3.1.2 Labels ----------------------------------------------------------
CASES = ("explicit", "implicit", "resolved", "clean")
NEEDS_ATTENTION_CASES = ("explicit", "implicit")
LABEL_FIELDS = ("scenario", "agent", "case", "needs_attention", "from_event")

# --- Provenance sidecar (meta.jsonl) ---------------------------------------
# Not part of the 3.1.2 interface, so scoring never reads it. It exists so that
# split.py can keep calibration / dev / test separate (R7) and so the memo can
# report real and synthetic results apart.
#   scenario   scenario id
#   source     rootse | nebius | trail | own_run | synthetic | handwritten | mix
#   origin_id  id of the original trajectory; one origin never spans two splits
#   real       True for real traces, False for synthetic or hand-written
#   case       same as the label (single-agent) or "mixed"
#   note       free text, e.g. the dataset's failure_reason

# Each event's text is cut to this many characters. Long file views and test
# logs would otherwise dominate the stream. Agree the value with Gene (7.2).
MAX_EVENT_CHARS = 1500


def truncate(text, limit=MAX_EVENT_CHARS):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = int(limit * 0.7)
    tail = limit - head - 20
    return text[:head] + "\n...[truncated]...\n" + text[-tail:]


def approx_tokens(text):
    """Rough token count (about 4 characters per token). For planning only."""
    return len(text) // 4 + 1


def make_label(scenario, agent, case, from_event=None):
    if case not in CASES:
        raise ValueError(f"unknown case {case!r}")
    label = {
        "scenario": scenario,
        "agent": agent,
        "case": case,
        "needs_attention": case in NEEDS_ATTENTION_CASES,
    }
    if label["needs_attention"]:
        if from_event is None:
            raise ValueError(f"{scenario}/{agent}: {case} needs a from_event")
        label["from_event"] = int(from_event)
    return label


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def single_agent_events(task, steps, finish_text, agent="A"):
    """Build a single-agent session: event 0 is start, then one event per step,
    then finish. So dataset step k (0-based) lands on event k + 1."""
    events = [{"i": 0, "agent": agent, "type": "start", "text": truncate(task)}]
    for step_text in steps:
        events.append({"i": len(events), "agent": agent, "type": "output",
                       "text": truncate(step_text)})
    events.append({"i": len(events), "agent": agent, "type": "finish",
                   "text": finish_text})
    return events


def write_dataset(out_dir, scenarios):
    """scenarios: list of (scenario_id, events, labels, meta). Writes
    out_dir/scenarios/<id>.jsonl, out_dir/labels.jsonl and out_dir/meta.jsonl."""
    labels, metas = [], []
    for sid, events, sc_labels, meta in scenarios:
        write_jsonl(os.path.join(out_dir, "scenarios", f"{sid}.jsonl"), events)
        labels.extend(sc_labels)
        metas.append(meta)
    write_jsonl(os.path.join(out_dir, "labels.jsonl"), labels)
    write_jsonl(os.path.join(out_dir, "meta.jsonl"), metas)
