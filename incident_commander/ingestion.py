"""Ingestion: parse raw alert / log / metric dicts into normalized Signals.

Supports three heterogeneous input shapes commonly seen in real systems:

* alerts  -- {"type": "alert", "alert_name"/"name", "status"/"severity", ...}
* logs    -- {"type": "log", "level", "message"/"msg", "logger"/"source", ...}
* metrics -- {"type": "metric", "metric"/"metric_name", "value", "threshold", ...}

Everything is stdlib-only and performs no network I/O.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Severity, Signal, SignalType

_ERROR_KEYWORDS = ("error", "failed", "failure", "exception", "timeout",
                   "refused", "unreachable", "oom", "out of memory")
_CRITICAL_KEYWORDS = ("oom", "out of memory", "kernel panic", "data loss",
                      "connection refused")


def parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            # Fall back to a common log format
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    raise ValueError(f"Unsupported timestamp value: {value!r}")


def _infer_severity(raw: dict, message: str, explicit) -> Severity:
    sev = Severity.from_string(explicit, default=None) if explicit else None
    if sev is not None:
        return sev
    lowered = message.lower()
    if any(k in lowered for k in _CRITICAL_KEYWORDS):
        return Severity.CRITICAL
    if any(k in lowered for k in _ERROR_KEYWORDS):
        return Severity.ERROR
    return Severity.INFO


def _metric_severity(value, threshold, explicit) -> Severity:
    if explicit:
        return Severity.from_string(explicit)
    if value is not None and threshold:
        ratio = value / threshold
        if ratio >= 1.5:
            return Severity.CRITICAL
        if ratio >= 1.0:
            return Severity.ERROR
        if ratio >= 0.85:
            return Severity.WARNING
    return Severity.INFO


def parse_signal(raw: dict, index: int = 0) -> Signal:
    if not isinstance(raw, dict):
        raise TypeError(f"Signal must be a dict, got {type(raw).__name__}")
    type_raw = str(raw.get("type") or raw.get("kind") or "log").lower()
    try:
        sig_type = SignalType(type_raw)
    except ValueError:
        # Heuristic fallback: presence of metric value implies metric.
        sig_type = SignalType.METRIC if "value" in raw else SignalType.LOG

    timestamp = parse_timestamp(
        raw.get("timestamp") or raw.get("time") or raw.get("ts")
        or "2026-01-01T00:00:00+00:00"
    )
    service = str(raw.get("service") or raw.get("app") or raw.get("application") or "unknown")
    source = str(raw.get("source") or raw.get("logger") or raw.get("alert_name")
                 or raw.get("name") or sig_type.value)
    message = str(raw.get("message") or raw.get("msg") or raw.get("description")
                  or raw.get("alert_name") or raw.get("name") or "")

    metric_name = raw.get("metric") or raw.get("metric_name")
    metric_value = raw.get("value")
    metric_threshold = raw.get("threshold")
    if metric_value is not None:
        metric_value = float(metric_value)
    if metric_threshold is not None:
        metric_threshold = float(metric_threshold)

    explicit = raw.get("severity") or raw.get("level") or raw.get("status")
    if sig_type == SignalType.METRIC:
        severity = _metric_severity(metric_value, metric_threshold, raw.get("severity"))
        if not message:
            message = f"Metric {metric_name}={metric_value} (threshold {metric_threshold})"
    else:
        severity = _infer_severity(raw, message, explicit)

    # Metric breach escalates even if the sender labelled it low.
    if sig_type == SignalType.METRIC and metric_value is not None and metric_threshold:
        breach = _metric_severity(metric_value, metric_threshold, None)
        if breach.weight > severity.weight:
            severity = breach

    labels = dict(raw.get("labels") or {})
    # Preserve useful correlation keys as labels when present.
    for key in ("host", "instance", "trace_id", "incident_key", "dependency_group", "region"):
        if key in raw and key not in labels:
            labels[key] = raw[key]

    return Signal(
        id=str(raw.get("id") or f"sig-{index:04d}"),
        type=sig_type,
        source=source,
        service=service,
        timestamp=timestamp,
        severity=severity,
        message=message,
        labels=labels,
        metric_name=str(metric_name) if metric_name else None,
        metric_value=metric_value,
        metric_threshold=metric_threshold,
        host=str(raw.get("host") or labels.get("host") or "") or None,
    )


def parse_signals(raw_list: list[dict]) -> list[Signal]:
    signals = [parse_signal(raw, i) for i, raw in enumerate(raw_list)]
    signals.sort(key=lambda s: s.timestamp)
    return signals


def load_signals_from_json(path: str | Path) -> list[Signal]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("signals") or data.get("events") or []
    return parse_signals(data)
