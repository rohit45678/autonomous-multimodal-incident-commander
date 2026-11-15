from incident_commander.ingestion import parse_signal, parse_signals, parse_timestamp
from incident_commander.models import Severity, SignalType


def test_parse_alert():
    s = parse_signal({"type": "alert", "service": "api", "severity": "critical",
                      "message": "API down", "timestamp": "2026-06-01T09:00:00Z", "id": "x1"})
    assert s.type == SignalType.ALERT
    assert s.severity == Severity.CRITICAL
    assert s.service == "api"
    assert s.id == "x1"


def test_parse_log_infers_error_from_level():
    s = parse_signal({"type": "log", "service": "database", "level": "error",
                      "message": "query failed", "timestamp": "2026-06-01T09:00:00Z"})
    assert s.type == SignalType.LOG
    assert s.severity == Severity.ERROR


def test_parse_log_infers_critical_from_oom_keyword():
    s = parse_signal({"type": "log", "service": "cache", "message": "OOM killed process",
                      "timestamp": "2026-06-01T09:00:00Z"})
    assert s.severity == Severity.CRITICAL


def test_parse_metric_breach_escalates_severity():
    s = parse_signal({"type": "metric", "service": "database", "metric": "db_connections",
                      "value": 980, "threshold": 500, "timestamp": "2026-06-01T09:00:00Z"})
    assert s.type == SignalType.METRIC
    assert s.metric_value == 980.0
    assert s.breach_ratio > 1.9
    assert s.severity in (Severity.ERROR, Severity.CRITICAL)


def test_parse_metric_below_threshold_is_info():
    s = parse_signal({"type": "metric", "service": "api", "metric": "cpu_usage_percent",
                      "value": 20, "threshold": 90, "timestamp": "2026-06-01T09:00:00Z"})
    assert s.severity == Severity.INFO


def test_parse_signals_sorts_by_timestamp():
    raw = [
        {"type": "log", "service": "api", "message": "second", "timestamp": "2026-06-01T09:05:00Z"},
        {"type": "log", "service": "api", "message": "first", "timestamp": "2026-06-01T09:00:00Z"},
    ]
    out = parse_signals(raw)
    assert [s.message for s in out] == ["first", "second"]


def test_parse_timestamp_epoch_and_zulu():
    assert parse_timestamp("2026-06-01T09:00:00Z").hour == 9
    assert parse_timestamp(0).year == 1970


def test_parse_signal_rejects_non_dict():
    import pytest
    with pytest.raises(TypeError):
        parse_signal("not-a-dict")  # type: ignore[arg-type]
