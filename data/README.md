# Sentinel — Data workstream (Moses)

This folder builds the scenario and label files described in SDD 3.1.1 and 3.1.2, plus the calibration, dev and test sets (3.2.1). It needs plain Python 3.10 and nothing else. `DESIGN_NOTES_4.2.1.md` has draft text for every entry in SDD 4.2.1.

```
schema.py              formats, helpers, MAX_EVENT_CHARS
validate.py            checks folders against 3.1.1 / 3.1.2 (+ --splits for R7)
show.py                prints a scenario with indices (hand labelling)
make_samples.py        4 hand-written sessions + 1 mix  -> samples/
converters/rootse.py   RootSE            -> implicit
converters/nebius.py   SWE-agent trajs   -> clean, calibration
converters/agent_log.py Claude Code logs -> explicit, resolved (hand-labelled)
converters/trail.py    stub (optional)
catalog.py             failure catalog CSV from RootSE
synth.py               prompts for a non-Qwen model + ingest replies (after poster)
split.py               work/* -> out/{calibration,dev,test_real,test_synth} + MANIFEST.json
interleave.py          single-agent sessions -> multi-agent scenarios
```

Folder flow: `raw/` (downloads, never edited) → `work/<source>/` (converted) → `out/<split>/` (what the runner reads).
Keep `raw/`, `work/`, `out/` on the shared Drive, not in git (3.2.3). Only the code, `samples/` and `split_plan.json` go in the repo.

---

## Step-by-step

### Step 1 — Samples to Alex (today, about 30 min)
- [ ] `python make_samples.py` then `python validate.py samples` → prints `OK`
- [ ] `python show.py samples/scenarios/hand_mix_001.jsonl`. Check that from_event sits where you would step in.
- [ ] Send `samples/` to Alex (for scoring tests) and Gene (for feeding a stream). This is SDD task #1.

### Step 2 — RootSE → implicit (Nov 26)
- [ ] Download RootSE in Colab (`huggingface_hub.snapshot_download("dengdan1999/RootSE", repo_type="dataset", local_dir="raw/rootse")`). Copy `raw/rootse` to here.
- [ ] `python converters/rootse.py raw/rootse --inspect 5`
  - Do the step keys say `thought`, `action`, `observation`? If not, fix `step_text()`.
  - Does the step marked `<== failure_id` match the REASON? If the step *after* it matches better, use `--index-base 1`.
- [ ] `python converters/rootse.py raw/rootse --out work/rootse`, then `python validate.py work/rootse`
- [ ] Look at the stats line. Is approx_tokens_per_scenario reasonable? Tell Gene the numbers (stream lengths, 7.2).

### Step 3 — nebius → clean + calibration (Nov 26–27)
- [ ] In Colab, export a 2,000-row sample to jsonl (the code is in the `converters/nebius.py` docstring)
- [ ] `python converters/nebius.py raw/nebius_sample.jsonl --out work/nebius_clean --kind clean --n 80`
- [ ] `python converters/nebius.py raw/nebius_sample.jsonl --out work/nebius_calib --kind calibration --n 128 --exclude work/nebius_clean`
- [ ] Read 10 clean ones with `show.py`. Are they really clean? Drop or relabel any that aren't.
- [ ] Ask Nora how many calibration samples she wants, and how long they should be.

### Step 4 — Own runs → explicit + resolved (Nov 27–28)
- [ ] Write 6 trap tasks, for example: a missing API key, an ambiguous spec, conflicting requirements, a product decision, a flaky test (resolved), or a wrong import path (resolved).
- [ ] Run Claude Code on each in a scratch repo. The log is `~/.claude/projects/<project>/<session>.jsonl`.
- [ ] `python converters/agent_log.py <log> --id own_explicit_001 --out work/own_runs`, then `show.py`, then re-run it with `--case explicit --from-event N --trap "..."`
- [ ] Check the logs for secrets before sharing.
- [ ] If this is going slowly, take the SDD shortcut (about 5 hand-written cases). **Decide by Nov 29.**

### Step 5 — Decide, split, freeze (Nov 29)
- [ ] Finish the label mapping in DESIGN_NOTES (recommendation: option A). Alex reads it.
- [ ] Edit `split_plan.json` counts, then run `python split.py --plan split_plan.json --out out`
- [ ] `python validate.py out/calibration out/dev out/test_real --splits` → `OK`
- [ ] Copy `out/` to Drive. Announce that the test set is frozen. From now on, `python split.py --verify out` should say `unchanged`.

### Step 6 — After the poster
- [ ] `python catalog.py raw/rootse`, fill the `pattern` column, then `catalog.py --summarize`. Paste the result into the SDD failure catalog.
- [ ] Synthetic sessions: `synth.py prompt` → a non-Qwen model → `synth.py ingest` → `split.py` (test_synth only)
- [ ] Multi-agent mixes for Q4: `python interleave.py --in out/test_real --out out/test_real_mix3 --agents 3 --n 30`

---

## Decisions you own (from the SDD)

| Item | Where | Due | Draft |
|---|---|---|---|
| Label mapping → from_event | 4.2.1 | Nov 29 | DESIGN_NOTES § Label mapping |
| Mix of scenario sources | 4.2.1 / 7.1 | Nov 29 | DESIGN_NOTES § Approach, Open questions |
| Default stream lengths (with Gene) | 7.2 | first real run | DESIGN_NOTES § Open questions |
| Data shortcut (#2) | 6.1 | Nov 29 | README Step 4 |
