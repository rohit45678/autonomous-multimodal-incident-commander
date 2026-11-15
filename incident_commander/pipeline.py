"""Pipeline orchestration: ingest -> correlate -> rank -> remediate."""
from __future__ import annotations

from .correlation import correlate
from .ingestion import parse_signals
from .ranking import rank_root_causes
from .remediation import suggest_remediation


def run_pipeline(raw_signals: list[dict], window_seconds: int = 900) -> dict:
    signals = parse_signals(raw_signals)
    incidents = correlate(signals, window_seconds=window_seconds)
    report_incidents = []
    for incident in incidents:
        causes = rank_root_causes(incident)
        steps = suggest_remediation(causes)
        report_incidents.append({
            "id": incident.id,
            "title": incident.title,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "services": sorted(incident.services),
            "signal_count": len(incident.signals),
            "max_severity": incident.max_severity.value,
            "signals": [
                {"id": s.id, "type": s.type.value, "service": s.service,
                 "severity": s.severity.value, "message": s.message,
                 "timestamp": s.timestamp.isoformat()}
                for s in incident.signals
            ],
            "root_causes": [
                {"cause": c.cause, "category": c.category, "score": c.score,
                 "confidence": c.confidence, "evidence": c.evidence}
                for c in causes
            ],
            "remediation": [
                {"order": st.order, "action": st.action, "reason": st.reason,
                 "category": st.category, "risk": st.risk}
                for st in steps
            ],
        })
    return {"incident_count": len(report_incidents), "signal_count": len(signals),
            "incidents": report_incidents}


def format_report(report: dict) -> str:
    lines = [
        "Autonomous Multimodal Incident Commander",
        f"Signals ingested: {report['signal_count']}  |  Incidents correlated: {report['incident_count']}",
        "=" * 72,
    ]
    for inc in report["incidents"]:
        lines.append(f"\n{inc['id']}: {inc['title']}")
        lines.append(f"  Started: {inc['started_at']}  Services: {', '.join(inc['services'])}  "
                     f"Signals: {inc['signal_count']}  Max severity: {inc['max_severity']}")
        lines.append("  Ranked root causes:")
        for c in inc["root_causes"]:
            lines.append(f"    - {c['cause']} (category={c['category']}, score={c['score']}, "
                         f"confidence={c['confidence']})")
            for ev in c["evidence"][:3]:
                lines.append(f"        evidence: {ev}")
        lines.append("  Remediation plan:")
        for st in inc["remediation"]:
            lines.append(f"    {st['order']}. [{st['risk']}] {st['action']} -- {st['reason']}")
    return "\n".join(lines)
