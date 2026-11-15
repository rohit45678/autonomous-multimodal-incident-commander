"""Correlation: group related signals into a single incident.

Two signals are linked when they occur inside the time window AND share
at least one correlation dimension:

* same service
* same host
* same explicit incident_key / trace_id / dependency_group label
* a known dependency between their services (e.g. checkout -> api -> db)

Linking is done with union-find, so chains of related signals collapse
into one incident even when the first and last share nothing directly.
Unrelated signals (different services, hosts and groups, far apart in
time, no dependency) stay in separate incidents.
"""
from __future__ import annotations

from .models import Incident, Signal

# service -> services it depends on (downstream). Either direction links.
DEFAULT_DEPENDENCIES: dict[str, set[str]] = {
    "checkout": {"api", "payments"},
    "api": {"database", "cache", "auth"},
    "payments": {"database"},
    "web": {"api"},
    "auth": {"database"},
}


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _services_related(a: str, b: str, deps: dict[str, set[str]]) -> bool:
    return b in deps.get(a, set()) or a in deps.get(b, set())


def _signals_related(a: Signal, b: Signal, window_seconds: int,
                     deps: dict[str, set[str]]) -> bool:
    delta = abs((a.timestamp - b.timestamp).total_seconds())
    if delta > window_seconds:
        return False
    if a.service == b.service:
        return True
    if a.host and b.host and a.host == b.host:
        return True
    for key in ("incident_key", "trace_id", "dependency_group"):
        av, bv = a.labels.get(key), b.labels.get(key)
        if av and bv and av == bv:
            return True
    if _services_related(a.service, b.service, deps):
        return True
    return False


def _title_for(signals: list[Signal]) -> str:
    worst = max(signals, key=lambda s: s.severity.weight)
    services = sorted({s.service for s in signals})
    return f"{worst.severity.value.upper()} on {', '.join(services)}: {worst.message[:80]}"


def correlate(signals: list[Signal], window_seconds: int = 900,
              dependencies: dict[str, set[str]] | None = None) -> list[Incident]:
    deps = dependencies if dependencies is not None else DEFAULT_DEPENDENCIES
    ordered = sorted(signals, key=lambda s: s.timestamp)
    uf = _UnionFind(len(ordered))
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            # Ordered by time, so once we're past the window we can stop.
            if (ordered[j].timestamp - ordered[i].timestamp).total_seconds() > window_seconds:
                break
            if _signals_related(ordered[i], ordered[j], window_seconds, deps):
                uf.union(i, j)

    groups: dict[int, list[Signal]] = {}
    for i, sig in enumerate(ordered):
        groups.setdefault(uf.find(i), []).append(sig)

    incidents: list[Incident] = []
    sorted_groups = sorted(groups.values(), key=lambda g: min(s.timestamp for s in g))
    for n, group in enumerate(sorted_groups, start=1):
        incidents.append(Incident(id=f"INC-{n:03d}", title=_title_for(group), signals=group))
    return incidents
