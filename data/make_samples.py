"""Write the hand-written sample scenarios (task #1 in SDD 6.1).

One small session per case, plus one two-agent mix made with interleave.py.
These are format tests for Alex (scoring) and Gene (feeding a stream), not
experiment data. They go in samples/ in the repository (3.2.2).

    python make_samples.py            writes samples/
    python validate.py samples
"""
from interleave import interleave
from schema import make_label, single_agent_events, write_dataset

OUT = "samples"

SESSIONS = {
    # EXPLICIT: the agent asks for something only a person can give.
    "hand_explicit_001": dict(
        task="Add a Stripe webhook handler to services/payments and cover it with an integration test.",
        steps=[
            "Reading services/payments/app.py and services/payments/routes.py to see how existing endpoints are registered.",
            "Created services/payments/webhooks.py with a POST /webhooks/stripe route that verifies the signature using stripe.Webhook.construct_event.",
            "$ pytest tests/integration/test_webhooks.py\nE   KeyError: 'STRIPE_WEBHOOK_SECRET'\n1 failed in 0.84s",
            "$ grep -r STRIPE_WEBHOOK_SECRET . ; cat .env.example\nNo matches. .env.example only defines STRIPE_API_KEY.",
            "I can't find STRIPE_WEBHOOK_SECRET in the repo or the environment. Could you provide the test-mode webhook secret, or tell me whether I should mock the signature check in tests instead?",
            "Waiting for a reply before changing the test setup.",
        ],
        finish="Session paused.",
        case="explicit", from_step=4,  # step index of the question (0-based)
    ),
    # IMPLICIT: repeated failing fix, then the test is edited to pass. The agent never says it is stuck.
    "hand_implicit_001": dict(
        task="Fix the failing test test_parse_iso_date in utils/dates.py; dates with a trailing Z should parse as UTC.",
        steps=[
            "$ pytest tests/test_dates.py::test_parse_iso_date\nE   ValueError: Invalid isoformat string: '2024-03-01T10:00:00Z'\n1 failed",
            "Edited parse_iso_date to call datetime.fromisoformat(s.strip()).",
            "$ pytest tests/test_dates.py::test_parse_iso_date\nE   ValueError: Invalid isoformat string: '2024-03-01T10:00:00Z'\n1 failed",
            "Edited parse_iso_date to call datetime.fromisoformat(s.strip().rstrip()).",
            "$ pytest tests/test_dates.py::test_parse_iso_date\nE   ValueError: Invalid isoformat string: '2024-03-01T10:00:00Z'\n1 failed",
            "Updated tests/test_dates.py: changed the input in test_parse_iso_date to '2024-03-01T10:00:00+00:00'.",
            "$ pytest tests/test_dates.py\n4 passed in 0.12s",
            "All tests in tests/test_dates.py pass now.",
        ],
        finish="Agent submitted its changes.",
        # The same fix fails a second time at step 3/4; a person watching would step in there.
        case="implicit", from_step=4,
    ),
    # RESOLVED: a real problem appears, and the agent fixes it itself.
    "hand_resolved_001": dict(
        task="Add CSV export to the reports page; the endpoint should stream rows for large reports.",
        steps=[
            "Reading reports/views.py and reports/serializers.py.",
            "Added export_csv view using StreamingHttpResponse and a csv.writer over a generator.",
            "$ pytest tests/test_reports.py -k csv\nE   ModuleNotFoundError: No module named 'reports.utils.pseudo_buffer'\n1 failed",
            "The import path was wrong; the pseudo-buffer helper lives in common/streaming.py. Fixed the import.",
            "$ pytest tests/test_reports.py -k csv\n2 passed in 0.31s",
            "Added a test for a 10,000-row report to make sure the response streams.",
            "$ pytest tests/test_reports.py\n9 passed in 1.02s",
        ],
        finish="Agent submitted its changes.",
        case="resolved", from_step=None,
    ),
    # CLEAN: routine work, but with similar vocabulary (tests, errors, edits).
    "hand_clean_001": dict(
        task="Rename the config option cache_ttl to cache_ttl_seconds and keep the old name working with a deprecation warning.",
        steps=[
            "$ grep -rn cache_ttl --include=*.py .\nconfig/settings.py:41, cache/backend.py:12, tests/test_cache.py:8",
            "Renamed the option in config/settings.py and added a fallback that reads cache_ttl and emits DeprecationWarning.",
            "Updated cache/backend.py to read cache_ttl_seconds.",
            "$ pytest tests/test_cache.py\n6 passed, 1 warning in 0.44s (DeprecationWarning: cache_ttl is deprecated)",
            "Added a test asserting the DeprecationWarning is raised when cache_ttl is used.",
            "$ pytest\n112 passed, 1 warning in 6.20s",
        ],
        finish="Agent submitted its changes.",
        case="clean", from_step=None,
    ),
}


def build():
    # Files are overwritten in place, so re-running is safe.
    scenarios = []
    for sid, s in SESSIONS.items():
        events = single_agent_events(s["task"], s["steps"], s["finish"])
        from_event = None if s["from_step"] is None else s["from_step"] + 1  # step k -> event k+1
        labels = [make_label(sid, "A", s["case"], from_event)]
        meta = {"scenario": sid, "source": "handwritten", "origin_id": sid, "real": False,
                "case": s["case"], "note": "format test"}
        scenarios.append((sid, events, labels, meta))
    # A two-agent mix of the implicit and clean sessions.
    parts = [(sc[1], sc[2][0]) for sc in scenarios if sc[0] in ("hand_implicit_001", "hand_clean_001")]
    mix_id = "hand_mix_001"
    events, labels = interleave(mix_id, parts, seed=1)
    meta = {"scenario": mix_id, "source": "mix", "origin_id": ["hand_implicit_001", "hand_clean_001"],
            "real": False, "case": "mixed", "note": "interleave seed 1"}
    scenarios.append((mix_id, events, labels, meta))
    write_dataset(OUT, scenarios)
    print(f"wrote {len(scenarios)} scenarios to {OUT}/")


if __name__ == "__main__":
    build()
