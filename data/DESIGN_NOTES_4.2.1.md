# 4.2.1 Data — owner design notes (Moses Sun) — DRAFT

Draft text for each entry in SDD 4.2.1. Each entry says what is **proposed** and what **you still decide or check**. When you agree with an entry, paste it into the SDD and delete its tag there.

---

## Approach (TO FILL)

**Proposed text:**
> Three sources, used in this order.
> 1. **Existing labelled datasets.** RootSE (102 failed coding-agent runs; human experts marked the earliest decisive error step) gives the **implicit** cases. Solved runs from nebius/SWE-agent-trajectories (`target = true`) give the **clean** cases. Unused nebius rows become the **calibration** set. TRAIL is a fallback only: its SWE-bench split has about 30 traces, they come from a general agent loop rather than a coding agent, and access is gated.
> 2. **Our own agent runs.** Claude Code or Codex (never Qwen) works on small tasks that have a built-in trap. The agent never sees our format; we convert its log afterwards. These give the **explicit** cases (the agent asks a person for something) and the **resolved** cases (the agent hits a problem and fixes it itself), which the datasets lack.
> 3. **Synthetic sessions** (after the poster). A model that is not Qwen expands seeds from 1 and 2. Labels are written when the session is generated. These are reported apart from the real test set.
>
> Every source is converted to the same single-agent format (3.1.1). Multi-agent scenarios are built from these by a seeded interleave, so they never need new labelling.

**You decide:** whether to use TRAIL at all. Recommendation: no, unless RootSE has fewer usable runs than expected.

---

## Order (TO CHECK)

**Proposed text:**
> Nov 25–26: format, validator and four hand-written samples (one per case) go to Alex for scoring tests. Download RootSE and check how `failure_id` is indexed.
> Nov 26–27: RootSE and nebius converters; first test set (implicit + clean).
> Nov 27–28: own agent runs for explicit and resolved cases (target 6 + 6).
> Nov 29: label mapping written down, Alex reads it, test set frozen (MANIFEST.json hashes). Calibration set handed to Nora.
> After the poster: synthetic sessions, failure catalog, multi-agent mixes for Q4.

**You check:** whether 6 + 6 own runs are realistic by Nov 28. If not, take the SDD shortcut (about 5 hand-written explicit and resolved cases), and decide that **by Nov 29**.

---

## Real test split (TO CHECK, Moses and Alex)

**Proposed text:**
> Four folders, never mixed: `calibration/`, `dev/`, `test_real/`, `test_synth/`. Real traces (datasets and our own runs) go only to `dev/` or `test_real/`. Synthetic sessions go only to `dev/` or `test_synth/`. Headline results are on `test_real/`. `split.py` groups scenarios by their original run (origin_id), so no run appears in two splits (R7), and `validate.py --splits` checks this. Multi-agent test scenarios are interleaved only from `test_real/` sessions, so freezing the single-agent test set freezes them too.

**Check with Alex:** (a) the runner reads `<dataset>/scenarios/*.jsonl` and `<dataset>/labels.jsonl`; (b) `meta.jsonl` is a sidecar that scoring ignores, so 3.1.2 stays unchanged; (c) multi-agent mixes built after Nov 29 from the frozen sessions still count as frozen.

---

## Label mapping (TO DECIDE, due Nov 29)

The problem: RootSE marks the *earliest decisive error step*, which is where the run went wrong. That is often **before** a person could see anything wrong (for example, the agent edits the wrong function and nothing fails yet). `from_event` is meant to be the first point at which attention is needed.

**Working rule for when attention is needed (Moses, Nov 26):**
> An implicit problem starts at the first event where the agent's attempt to recover has visibly failed, for example the same error after a repeated fix. A single error the agent is still working on is friction, not a problem.

Worked example (samples/hand_mix_001, agent A): event 3 is the first failed fix, which is friction because the agent is still correcting itself. Event 8 is the same error after a second, near-identical fix, so the recovery has visibly failed: **from_event = 8**. Event 10, where the agent edits the test so it passes, is too late. Labelling there would count a correct catch at 8 as a false alarm.

This rule also separates the cases. Resolved and implicit agents both hit friction, but only implicit agents fail to recover. It is the reference point for the hand-check of about 20 RootSE dev runs: for each run, mark the event this rule picks, and compare it with the dataset's decisive step.

How each source maps:

| Case | Source | from_event |
|---|---|---|
| implicit | RootSE | The event of the decisive step. One step becomes one event, and event 0 is the task, so step *k* (counted from 0) becomes event *k + 1*. |
| implicit | synthetic | The step the generator marked `problem_starts` (+1). |
| explicit | own runs, synthetic | The event where the agent asks the person. |
| resolved, clean | all | Absent (`needs_attention = false`). |

**Options for RootSE implicit:**
- **A. Decisive step (the SDD placeholder).** Reproducible and needs no hand-labelling. Delay looks longer than a person would feel it.
- **B. First visible symptom after the decisive step** (the first failing test or repeated error). This is closer to "when a person should step in", but it means hand-labelling about 100 runs before Nov 29.
- **C. Decisive step + a fixed k.** Arbitrary, and hard to defend in the memo.

**Recommendation: A**, plus a small measurement. Hand-mark the first visible symptom on about 20 dev runs, then report the median gap between symptom and decisive step in the memo. That turns the known mismatch into a number instead of a caveat. The converter keeps `decisive_event` in `meta.jsonl`, so switching to B later only needs a re-run.

**Tell Alex:** how should an alert on an implicit agent *before* from_event be scored? Recommendation: a false positive, because nothing was wrong yet. With option A this case is rare.

**Before freezing, also check:** whether `failure_id` counts from 0 or 1. Run `converters/rootse.py --inspect 5` and confirm that the step marked `<== failure_id` matches the failure_reason. Then set `--index-base`.

---

## Licenses (TO CHECK)

**Proposed text:**
> - **RootSE:** MIT (dataset card). OK to use and to convert.
> - **nebius/SWE-agent-trajectories:** CC-BY-4.0. Attribute it in the memo and poster. The card adds that model outputs follow the Llama 3.1 license, which is fine for research use. Repositories inside the trajectories keep their own licenses.
> - **TRAIL** (if used): MIT, but gated. Users agree not to reshare it outside a gated or private place, so converted TRAIL files stay on the private team Drive and never go into a public repo.
> - **Own runs:** ours. Check that no secrets or keys appear in the logs before sharing.
> - **Synthetic:** generated by a non-Qwen model under that provider's terms. We do not train on it.

**You check:** whether the team repo is public. If it is, the full datasets stay on Drive only (3.2.3 already says so).

---

## Failure catalog (TO FILL)

**How to fill it:** run `python catalog.py raw/rootse`. It writes a CSV with each run's human `failure_reason` and the text of its decisive step. In Excel, give each row a short pattern name, then run `catalog.py --summarize` to count patterns and get one real example for each.

Starting patterns to confirm or replace with what RootSE actually shows:

| Pattern | What it looks like | Real example |
|---|---|---|
| repeated_fix | Same error after the same kind of edit, more than twice | *(from catalog)* |
| edits_test | Changes the test instead of the code so it passes | |
| missing_resource | Needs a file, key, access or decision it cannot get | *(own runs)* |
| wrong_location | Fixes the wrong function, file or symptom | |
| premature_submit | Submits without reproducing or running tests | |
| task_drift | Works on something other than the task | |

The pattern names feed the synthetic prompts (`synth.py --pattern`) and the per-pattern analysis in the memo.

---

## Internal design (TO FILL)

**Proposed text:**
> Standard-library Python only; no model or tokenizer. `schema.py` holds the formats. There is one converter per source: `converters/rootse.py`, `converters/nebius.py`, `converters/agent_log.py`, and `converters/trail.py` (a stub). Each converter writes a work folder with `scenarios/`, `labels.jsonl` and `meta.jsonl`. `synth.py` builds generation prompts and turns model replies into labelled sessions. `split.py` assigns work folders to calibration, dev, test_real and test_synth by origin, and writes a hash manifest when the test set is frozen. `interleave.py` merges single-agent sessions on a seeded schedule, retags agents, and remaps from_event. `validate.py` checks every folder. `show.py` prints a scenario with indices, for hand-labelling.
>
> Conversion rules: one dataset step becomes one output event (thought + action + observation); each event's text is capped at MAX_EVENT_CHARS (1,500); the finish text is neutral ("Agent submitted its changes."); and gold patches, failing-test lists and failure reasons never enter the stream.

**Decide with Gene and Alex:** MAX_EVENT_CHARS. At about 375 tokens per event, a 2,048-token window holds only about 5 events, which is less than one check interval if check_every is 10. That is a real finding, but agree on it on purpose.

---

## Depends on (TO CHECK)

> Nothing from other parts. Hands off: `samples/` (now), `dev/` (for prompt tuning), `test_real/` (frozen Nov 29), `calibration/` (to Nora; agree the number of samples with her, since it is her open question), and later `test_synth/` and the multi-agent mixes.

## How to test it alone (TO FILL)

> `python make_samples.py && python validate.py samples`. The validator checks every file against 3.1.1 and 3.1.2: consecutive indices; each agent has one start and nothing after its finish; one label per agent; needs_attention agrees with the case; from_event is present only when needed and points at an output or finish event of the same agent. `validate.py --splits` checks that no scenario or origin appears in two splits. `split.py --verify out` confirms the frozen files have not changed.

## Quality checks (TO FILL)

> The validator warns when an implicit agent's text sounds stuck ("I'm stuck", "could you provide"), and when a finish event gives the outcome away. By hand: read 10 scenarios per case with `show.py`, and check that (1) implicit agents never ask for help, (2) from_event sits where the problem starts, (3) clean nebius runs really are clean (a solved run can still contain a moment a person would flag; relabel those as resolved), and (4) problem and clean scenarios use similar words and lengths. Report the event-length distribution per case, so the rule-based baseline cannot win on length alone.

## Open questions (TO DECIDE)

**Proposed numbers** for `test_real`: about 80 implicit (RootSE after 20 to dev), about 60 clean (nebius), and 6 to 10 each of explicit and resolved (own runs). Confirm run time with Nora: roughly 150 scenarios × about 50 events.

**Length of converted traces:** keep runs with 8 to 80 steps. At a 1,500-character cap that is about 3k to 30k tokens, or 1.5 to 15 times a 2,048-token window. That already covers Q1's "short to several times the window"; longer Q1 streams can be made by concatenating sessions. Agree this with Gene (7.2 stream lengths).

## Status (TO FILL)

> In progress, Nov 25: format, validator, samples and converters written and tested on hand-made data; RootSE download next.
