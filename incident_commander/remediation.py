"""Remediation suggestions: ordered, low-risk-first steps per cause category."""
from __future__ import annotations

from .models import RemediationStep, ScoredCause

_CATALOG: dict[str, list[tuple[str, str, str]]] = {
    # category -> [(action, reason, risk), ...]
    "database": [
        ("Inspect active DB connections and the top waiting queries",
         "Confirms pool pressure / lock waits before changing limits", "low"),
        ("Kill or drain the longest-running blocking queries (with DBA approval)",
         "Frees pool slots for queued application requests", "medium"),
        ("Raise the connection-pool limit temporarily and restart the affected app tier",
         "Restores headroom while the leak / surge is investigated", "medium"),
        ("Add a pool-usage alert at 80% and audit services for unclosed connections",
         "Prevents recurrence from connection leaks", "low"),
    ],
    "network": [
        ("Check reachability and DNS resolution between the affected services",
         "Separates a network fault from an application fault", "low"),
        ("Review load-balancer / proxy health and recent network changes",
         "Unhealthy backends present as downstream timeouts", "low"),
        ("Fail traffic over to a healthy instance / zone if errors persist",
         "Restores service while the faulty path is isolated", "medium"),
    ],
    "resource": [
        ("Capture current CPU / memory / disk usage per host and process",
         "Identifies the process driving saturation", "low"),
        ("Restart or reschedule the leaking / runaway process on one host first",
         "Validates the fix on a canary before a fleet-wide change", "medium"),
        ("Scale the tier out or raise resource limits if demand is legitimate",
         "Adds headroom for a real traffic surge rather than a leak", "medium"),
        ("Add saturation alerts (CPU, memory, disk) with runbook links",
         "Earlier warning next time saturation builds", "low"),
    ],
    "cache": [
        ("Check cache process health, memory and eviction counters",
         "Evictions and OOM in the cache look like app slowness downstream", "low"),
        ("Warm the cache for the hottest keys and verify the hit ratio recovers",
         "A cold / flushed cache overloads the database", "low"),
        ("Fail open to the database with rate limiting if the cache stays down",
         "Keeps reads working at reduced throughput", "medium"),
    ],
    "change": [
        ("Identify the most recent deploy / config change before the first alert",
         "Regressions correlate strongly with change timing", "low"),
        ("Roll back the suspect release on one instance and compare error rates",
         "Canary rollback proves or clears the release quickly", "medium"),
        ("Gate the release behind a feature flag / staged rollout on re-deploy",
         "Limits blast radius if the regression recurs", "low"),
    ],
    "unknown": [
        ("Preserve logs, metrics and traces for the incident window",
         "Evidence is needed for a post-incident review", "low"),
        ("Page the owning service team with the correlated timeline",
         "Owners can spot domain causes automation cannot", "low"),
        ("Declare an incident channel and assign an incident lead",
         "Coordination prevents duplicated / conflicting fixes", "low"),
    ],
}

_GENERAL_FIRST_STEPS = [
    ("Snapshot the correlated timeline and affected services",
     "Everyone works from the same facts before acting", "low"),
]


def suggest_remediation(ranked_causes: list[ScoredCause],
                        max_causes: int = 2) -> list[RemediationStep]:
    steps: list[RemediationStep] = []
    seen_actions: set[str] = set()

    def _add(action: str, reason: str, category: str, risk: str) -> None:
        if action in seen_actions:
            return
        seen_actions.add(action)
        steps.append(RemediationStep(order=len(steps) + 1, action=action,
                                     reason=reason, category=category, risk=risk))

    for action, reason, risk in _GENERAL_FIRST_STEPS:
        _add(action, reason, "general", risk)

    for cause in ranked_causes[:max_causes]:
        for action, reason, risk in _CATALOG.get(cause.category, _CATALOG["unknown"]):
            _add(action, reason, cause.category, risk)

    if not ranked_causes:
        for action, reason, risk in _CATALOG["unknown"]:
            _add(action, reason, "unknown", risk)

    # Re-number after de-duplication to keep orders contiguous.
    for i, step in enumerate(steps, start=1):
        step.order = i
    return steps
