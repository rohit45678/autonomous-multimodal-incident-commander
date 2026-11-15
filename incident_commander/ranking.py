"""Root-cause ranking.

Each candidate cause is a rule that scans an incident's signals for a
pattern (keywords, metric names, services). A rule's score combines:

* pattern hits (how many signals match)
* severity of the matching signals
* metric breach magnitude for metric-driven causes
* earliness -- the cause whose evidence starts first gets a bonus,
  because root causes precede their symptoms
* blast radius -- evidence on a service that other affected services
  depend on scores higher than evidence on a leaf service

Ranking is deterministic: descending score, then cause name A->Z.
"""
from __future__ import annotations

from .correlation import DEFAULT_DEPENDENCIES
from .models import Incident, ScoredCause, Signal

# cause -> (category, keywords, metric_names, services_hint)
_RULES: dict[str, dict] = {
    "database_connection_pool_exhaustion": {
        "category": "database",
        "keywords": ("connection pool", "too many connections", "pool exhausted",
                     "deadlock", "db connection", "database connection"),
        "metrics": ("db_connections", "db_connection_pool", "active_connections"),
        "services": ("database",),
    },
    "database_slow_queries": {
        "category": "database",
        "keywords": ("slow query", "query timeout", "lock wait"),
        "metrics": ("db_query_latency_ms", "query_latency"),
        "services": ("database",),
    },
    "downstream_service_timeout": {
        "category": "network",
        "keywords": ("timeout", "timed out", "deadline exceeded", "upstream"),
        "metrics": ("request_latency_ms", "p99_latency_ms"),
        "services": (),
    },
    "memory_pressure_oom": {
        "category": "resource",
        "keywords": ("out of memory", "oom", "memory pressure", "killed process"),
        "metrics": ("memory_usage_percent", "memory_percent"),
        "services": (),
    },
    "cpu_saturation": {
        "category": "resource",
        "keywords": ("cpu saturated", "load average", "throttl"),
        "metrics": ("cpu_usage_percent", "cpu_percent"),
        "services": (),
    },
    "disk_pressure": {
        "category": "resource",
        "keywords": ("disk full", "no space left", "disk pressure"),
        "metrics": ("disk_usage_percent", "disk_percent"),
        "services": (),
    },
    "cache_failure": {
        "category": "cache",
        "keywords": ("cache miss", "redis", "memcached", "cache unavailable", "eviction"),
        "metrics": ("cache_hit_ratio",),
        "services": ("cache",),
    },
    "network_connectivity_failure": {
        "category": "network",
        "keywords": ("connection refused", "unreachable", "dns resolution",
                     "network error", "connection reset"),
        "metrics": (),
        "services": (),
    },
    "deployment_regression": {
        "category": "change",
        "keywords": ("deploy", "release", "rollback", "new version", "config change"),
        "metrics": (),
        "services": (),
    },
}


def _dependents_count(service: str, incident_services: set[str],
                      deps: dict[str, set[str]]) -> int:
    """How many other incident services depend (transitively, 1 hop) on this one."""
    return sum(1 for other in incident_services
               if other != service and service in deps.get(other, set()))


def _score_rule(cause: str, rule: dict, incident: Incident,
                deps: dict[str, set[str]]) -> ScoredCause | None:
    evidence: list[str] = []
    score = 0.0
    earliest = None
    matched_services: set[str] = set()

    for sig in incident.signals:
        text = sig.message.lower()
        hit = False
        if any(k in text for k in rule["keywords"]):
            hit = True
        if sig.metric_name and sig.metric_name in rule["metrics"]:
            # Metric counts as a hit when it is breaching, or is a
            # ratio metric (cache_hit_ratio) dropping low.
            if sig.breach_ratio >= 0.85 or sig.metric_name == "cache_hit_ratio":
                hit = True
        if sig.service in rule["services"] and sig.severity.weight >= 3 and hit is False:
            # A severe signal on the hinted service alone is weak evidence.
            if any(k in text for k in ("error", "fail", "latency", "slow")):
                hit = True
        if hit:
            evidence.append(f"[{sig.id}] {sig.service}: {sig.message[:90]}")
            score += sig.severity.weight
            if sig.breach_ratio > 1.0:
                score += min(4.0, sig.breach_ratio)
            matched_services.add(sig.service)
            if earliest is None or sig.timestamp < earliest:
                earliest = sig.timestamp

    if not evidence:
        return None

    # Earliness bonus: evidence at the very start of the incident.
    if incident.started_at and earliest == incident.started_at:
        score += 2.0
    # Blast-radius bonus for causes rooted in depended-upon services.
    for svc in matched_services:
        score += 1.5 * _dependents_count(svc, incident.services, deps)
    # Frequency bonus (capped).
    score += min(3.0, 0.5 * (len(evidence) - 1))

    return ScoredCause(cause=cause, category=rule["category"],
                       score=round(score, 3), evidence=evidence)


def rank_root_causes(incident: Incident,
                     dependencies: dict[str, set[str]] | None = None) -> list[ScoredCause]:
    deps = dependencies if dependencies is not None else DEFAULT_DEPENDENCIES
    scored = []
    for cause, rule in _RULES.items():
        result = _score_rule(cause, rule, incident, deps)
        if result is not None:
            scored.append(result)
    if not scored:
        worst = max(incident.signals, key=lambda s: s.severity.weight) if incident.signals else None
        scored.append(ScoredCause(
            cause="unknown_upstream_failure",
            category="unknown",
            score=1.0,
            evidence=[f"[{worst.id}] {worst.service}: {worst.message[:90]}"] if worst else [],
        ))
    scored.sort(key=lambda c: (-c.score, c.cause))
    return scored
