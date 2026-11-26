"""TRAIL (SWE-bench split) -> implicit cases. OPTIONAL: do RootSE first.

Source: huggingface.co/datasets/PatronusAI/TRAIL (MIT, but GATED: you agree not
to reshare it outside a gated or private location, so keep converted files on
the private team Drive, never in a public repo).
Split `swe_bench`: about 30 traces. Each row has two strings, `trace`
(OpenTelemetry JSON: spans with span_id, child_spans, logs) and `labels`
(errors, each with a span location, category, evidence, description, impact).

Why it is optional: it is small, the traces are o3-mini in a smolagents-style
loop rather than a normal coding agent, and a trace has about 5.7 errors, so
"the" error step needs a rule (earliest error? earliest High-impact error?).

TO FILL (Moses), only if RootSE is not enough:
  1. flatten spans in time order; one LLM or TOOL span -> one output event
  2. from_event = event of the earliest annotated error span (or earliest High impact)
  3. write with schema.write_dataset, source="trail", real=True
"""
raise SystemExit("trail.py is a stub; see the docstring")
