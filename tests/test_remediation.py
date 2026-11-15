from incident_commander.correlation import correlate
from incident_commander.ingestion import parse_signals
from incident_commander.pipeline import run_pipeline
from incident_commander.ranking import rank_root_causes
from incident_commander.remediation import suggest_remediation


def test_remediation_for_database_incident_mentions_connections():
    inc = correlate(parse_signals([
        {"id": "1", "type": "log", "service": "database", "level": "error",
         "message": "connection pool exhausted - too many connections",
         "timestamp": "2026-06-01T09:00:00Z"},
    ]))[0]
    steps = suggest_remediation(rank_root_causes(inc))
    assert steps
    assert [s.order for s in steps] == list(range(1, len(steps) + 1))
    joined = " ".join(s.action.lower() for s in steps)
    assert "connection" in joined
    assert all(s.action and s.reason for s in steps)


def test_remediation_steps_are_deduplicated_and_low_risk_first_general_step():
    inc = correlate(parse_signals([
        {"id": "1", "type": "log", "service": "api", "level": "error",
         "message": "unexplained failure", "timestamp": "2026-06-01T09:00:00Z"},
    ]))[0]
    steps = suggest_remediation(rank_root_causes(inc))
    actions = [s.action for s in steps]
    assert len(actions) == len(set(actions))
    assert steps[0].risk == "low"


def test_empty_causes_still_gives_unknown_steps():
    steps = suggest_remediation([])
    assert steps
    assert any("incident" in s.action.lower() or "logs" in s.action.lower() for s in steps)


def test_pipeline_end_to_end_on_sample_scenario():
    report = run_pipeline([
        {"id": "1", "type": "metric", "service": "database", "metric": "db_connections",
         "value": 980, "threshold": 500, "timestamp": "2026-06-01T09:00:00Z",
         "message": "connection pool exhausted"},
        {"id": "2", "type": "log", "service": "api", "level": "error",
         "message": "database connection timeout", "timestamp": "2026-06-01T09:02:00Z"},
        {"id": "3", "type": "log", "service": "billing-worker", "message": "unrelated heartbeat",
         "timestamp": "2026-06-01T20:00:00Z", "host": "other-99"},
    ])
    assert report["signal_count"] == 3
    assert report["incident_count"] == 2
    first = report["incidents"][0]
    assert first["root_causes"][0]["cause"] == "database_connection_pool_exhaustion"
    assert first["remediation"]
