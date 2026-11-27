# Data (Sentinel)

Owner: Moses Sun. Status, **Nov 26**: dev, calibration and a provisional test set are ready. Explicit and resolved cases (our own agent runs) are coming next. **The test set freezes Nov 29.**

This part produces the scenario and label files in SDD 3.1.1 and 3.1.2, and the calibration, dev and test sets in SDD 3.2.1. It is plain Python 3.10+ with no model, tokenizer or pip install needed.

## What's ready for whom

| Who | Use | Where |
|---|---|---|
| **Alex** | Format tests for `score` and `format_event` | `data/samples/` (in this repo) |
| **Alex** | Prompt tuning | `data/out/dev/`: 20 implicit + 20 clean |
| **Nora** | AWQ calibration | `data/out/calibration/`: 128 runs, median ~4.7k tokens |
| **Gene** | Long real streams for the sink Stream and Q1 | `data/out/dev/` or `data/out/test_real/`: runs of ~4k to ~44k tokens |
| **Everyone** | Reported results | `out/test_real/`. **Provisional until Nov 29**; don't report numbers from it yet. |

The datasets are in this repo under `data/out/` (about 13 MB). This is a change from SDD 3.2.3, which put them on a shared Drive; they turned out small enough for git. Raw downloads (`raw/`, 136 MB) are not committed; the converters in `converters/` say how to re-download them. In Colab, `!git clone <repo url>` gives you everything.

## Dataset folder layout

Every set is one folder, and `config.dataset` points at it:
```
<dataset>/scenarios/<scenario_id>.jsonl   one event per line: {"i", "agent", "type", "text"}   (3.1.1)
<dataset>/labels.jsonl                    one line per agent: {"scenario", "agent", "case", "needs_attention", "from_event"?}   (3.1.2)
<dataset>/meta.jsonl                      provenance only (source, origin_id, real/synthetic, notes). Scoring ignores it.
```
- `i` is the event index, starting at 0. Each agent has one `start` (its task), then `output` events, then one `finish`.
- `from_event` is present only when `needs_attention` is true. It is an **event index** in the scenario file, never a token count.
- The finish text is always neutral ("Agent submitted its changes.") and never reveals the outcome.

Loading a set:
```python
import json, glob, os
def read_jsonl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
labels = read_jsonl("out/dev/labels.jsonl")
for path in sorted(glob.glob("out/dev/scenarios/*.jsonl")):
    events = read_jsonl(path)           # feed in order: format_event(e) -> stream.feed(...)
```

## What's in it

| Set | Implicit | Clean | Explicit | Resolved | Source |
|---|---|---|---|---|---|
| `samples/` | 2 | 2 | 1 | 1 | Hand-written format tests, incl. one 2-agent mix |
| `out/dev/` | 20 | 20 | – | – | RootSE / nebius |
| `out/test_real/` | 72 | 42 | *coming* | *coming* | RootSE / nebius / own runs |
| `out/calibration/` | – | – | – | – | nebius (unsolved runs) |

- **Implicit**: [RootSE](https://huggingface.co/datasets/dengdan1999/RootSE) (MIT). These are failed runs from SWE-agent, OpenHands and SWE-agent-live. AutoCodeRover and runs under 8 steps are excluded, because they are 3-step single-shot runs, not streams. Median 58 events, about 16k tokens.
- **Clean**: solved runs from [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) (CC-BY-4.0; cite it). Only runs with 20 or more steps are used. Median 29 events, about 7.5k tokens.
- **Explicit / resolved** (by Nov 28): Claude Code runs on small tasks with a built-in trap, labelled by hand.
- **Multi-agent** scenarios for Q4 are built from the frozen single-agent test set with `interleave.py` (seeded), so they need no new labels.

Token counts are estimates (characters / 4). Gene is checking them with the Qwen tokenizer.

## Label rules (draft, final by Nov 29)

| Case | needs_attention | from_event |
|---|---|---|
| explicit | true | The event where the agent asks a person for something |
| implicit (RootSE) | true | The event of the expert-marked **earliest decisive error** step (step k → event k+1) |
| resolved, clean | false | Absent |

Known caveat: RootSE marks where the agent's reasoning first went wrong, which is often **before** anything visibly fails. Our working rule for "a person should step in" is the first event where the agent's attempt to recover has visibly failed. A hand-check of about 20 runs will measure the gap for the memo. Details are in `DESIGN_NOTES_4.2.1.md`.

## Caveats to keep in mind when reading results

- Clean runs are still about **2× shorter** than implicit runs (median 29 vs 58 events). Report results by case, and don't let length alone explain a result.
- Clean runs come from Llama-based SWE-agent; implicit runs come from Claude, GPT and Qwen3-Coder agents.
- A run of about 16k tokens is about 8× a 2,048-token window. 2 of the 92 RootSE runs exceed about 32k tokens, the model's full context, so full mode stops on them (3.3.5).
- Events are capped at 1,500 characters (about 375 tokens), so a 2,048 window holds about 5 events.

## Questions I need answered

- **Alex**: (1) Is this folder layout OK for the runner? (2) Should an alert on an implicit agent *before* from_event count as a false positive? (3) Any objection to from_event = the decisive step?
- **Gene**: (1) Should the 2 runs over the context limit be dropped from the full-context comparison or kept? (2) Is the 1,500-character event cap OK, given about 5 events per window? (3) Default stream lengths (7.2).
- **Nora**: how many calibration samples, and how long?

## Data licenses

RootSE: MIT, © its authors (huggingface.co/datasets/dengdan1999/RootSE). nebius/SWE-agent-trajectories: CC-BY-4.0, © Nebius (huggingface.co/datasets/nebius/SWE-agent-trajectories); its card notes that model outputs follow the Llama 3.1 license. Converted files in `out/` are derived from these and keep their licenses. Cite both in the poster and memo.

## Tools

`validate.py` (format + overlap checks) · `show.py` (prints a scenario with indices) · `converters/` (rootse, nebius, agent_log, trail stub) · `split.py` (splits + freeze manifest) · `interleave.py` (multi-agent) · `synth.py` · `catalog.py`.
```
python validate.py out/dev out/test_real out/calibration --splits    # format + no overlap (R7)
python show.py out/dev/scenarios/<id>.jsonl --width 200              # read a scenario
```
How everything was built, step by step: `WORKBOOK.md`.
