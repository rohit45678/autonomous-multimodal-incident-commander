from incident_commander.correlation import correlate
from incident_commander.ingestion import parse_signals
from incident_commander.ranking import rank_root_causes


def _incident(raw):
    return correlate(parse_signals(raw))[0]


def test_database_pool_exhaustion_ranks_first():
    inc = _incident([
        {"id": "1", "type": "metric", "service": "database", "metric": "db_connections",
         "value": 980, "threshold": 500, "timestamp": "2026-06-01T09:00:00Z",
         "message": "db_connections high - connection pool exhausted"},
        {"id": "2", "type": "log", "service": "database", "level": "error",
         "message": "Too many connections: connection pool exhausted",
         "timestamp": "2026-06-01T09:01:00Z"},
        {"id": "3", "type": "log", "service": "api", "level": "error",
         "message": "Database connection timeout, upstream deadline exceeded",
         "timestamp": "2026-06-01T09:03:00Z"},
        {"id": "4", "type": "alert", "service": "checkout", "severity": "critical",
         "message": "Checkout failing with downstream service timeout",
         "timestamp": "2026-06-01T09:05:00Z"},
    ])
    causes = rank_root_causes(inc)
    assert causes[0].cause == "database_connection_pool_exhaustion"
    assert causes[0].score > causes[1].score if len(causes) > 1 else True
    assert causes[0].evidence  # evidence is attached
    assert 0 < causes[0].confidence <= 0.99


def test_ranking_is_descending_and_deterministic():
    inc = _incident([
        {"id": "1", "type": "log", "service": "cache", "level": "error",
         "message": "Redis cache unavailable, OOM out of memory",
         "timestamp": "2026-06-01T09:00:00Z"},
        {"id": "2", "type": "metric", "service": "cache", "metric": "memory_usage_percent",
         "value": 97, "threshold": 80, "timestamp": "2026-06-01T09:01:00Z",
         "message": "memory pressure"},
    ])
    first = rank_root_causes(inc)
    second = rank_root_causes(inc)
    assert [c.cause for c in first] == [c.cause for c in second]
    scores = [c.score for c in first]
    assert scores == sorted(scores, reverse=True)
    assert first[0].cause in ("memory_pressure_oom", "cache_failure")


def test_unknown_incident_gets_fallback_cause():
    inc = _incident([
        {"id": "1", "type": "log", "service": "api", "level": "error",
         "message": "something unexpected happened", "timestamp": "2026-06-01T09:00:00Z"},
    ])
    causes = rank_root_causes(inc)
    assert len(causes) >= 1
    assert causes[0].cause == "unknown_upstream_failure"
