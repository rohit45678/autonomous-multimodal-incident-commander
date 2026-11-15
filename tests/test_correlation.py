from incident_commander.correlation import correlate
from incident_commander.ingestion import parse_signals


def _db_cascade():
    return parse_signals([
        {"id": "1", "type": "metric", "service": "database", "metric": "db_connections",
         "value": 980, "threshold": 500, "timestamp": "2026-06-01T09:00:00Z",
         "message": "connection pool exhausted"},
        {"id": "2", "type": "log", "service": "api", "level": "error",
         "message": "database timeout", "timestamp": "2026-06-01T09:03:00Z"},
        {"id": "3", "type": "alert", "service": "checkout", "severity": "critical",
         "message": "checkout failing", "timestamp": "2026-06-01T09:05:00Z"},
    ])


def test_related_signals_group_into_one_incident():
    incidents = correlate(_db_cascade())
    assert len(incidents) == 1
    assert len(incidents[0].signals) == 3
    assert incidents[0].services == {"database", "api", "checkout"}


def test_unrelated_far_apart_signals_stay_separate():
    signals = parse_signals([
        {"id": "1", "type": "log", "service": "database", "message": "a",
         "timestamp": "2026-06-01T09:00:00Z", "host": "db-01"},
        {"id": "2", "type": "log", "service": "billing-worker", "message": "b",
         "timestamp": "2026-06-01T20:00:00Z", "host": "other-99"},
    ])
    incidents = correlate(signals, window_seconds=900)
    assert len(incidents) == 2


def test_same_service_within_window_groups():
    signals = parse_signals([
        {"id": "1", "type": "log", "service": "api", "message": "a", "timestamp": "2026-06-01T09:00:00Z"},
        {"id": "2", "type": "log", "service": "api", "message": "b", "timestamp": "2026-06-01T09:10:00Z"},
    ])
    assert len(correlate(signals)) == 1


def test_shared_incident_key_groups_across_services():
    signals = parse_signals([
        {"id": "1", "type": "log", "service": "svc-a", "message": "a",
         "timestamp": "2026-06-01T09:00:00Z", "incident_key": "INC-X"},
        {"id": "2", "type": "log", "service": "svc-z", "message": "b",
         "timestamp": "2026-06-01T09:02:00Z", "incident_key": "INC-X"},
    ])
    assert len(correlate(signals)) == 1


def test_empty_input_gives_no_incidents():
    assert correlate([]) == []
