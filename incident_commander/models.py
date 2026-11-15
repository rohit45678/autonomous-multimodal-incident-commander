"""Core data models for the Incident Commander."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    ALERT = "alert"
    LOG = "log"
    METRIC = "metric"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        return {"info": 1, "warning": 2, "error": 3, "critical": 4}[self.value]

    @classmethod
    def from_string(cls, value: str | None, default: "Severity" = None) -> "Severity":
        if value is None:
            return default or cls.INFO
        v = str(value).strip().lower()
        aliases = {
            "warn": cls.WARNING,
            "warning": cls.WARNING,
            "err": cls.ERROR,
            "error": cls.ERROR,
            "crit": cls.CRITICAL,
            "critical": cls.CRITICAL,
            "fatal": cls.CRITICAL,
            "info": cls.INFO,
            "information": cls.INFO,
            "debug": cls.INFO,
            "high": cls.CRITICAL,
            "medium": cls.WARNING,
            "low": cls.INFO,
            "firing": cls.CRITICAL,
            "resolved": cls.INFO,
        }
        return aliases.get(v, default or cls.INFO)


@dataclass
class Signal:
    id: str
    type: SignalType
    source: str
    service: str
    timestamp: datetime
    severity: Severity
    message: str
    labels: dict = field(default_factory=dict)
    metric_name: str | None = None
    metric_value: float | None = None
    metric_threshold: float | None = None
    host: str | None = None

    @property
    def breach_ratio(self) -> float:
        if self.metric_value is not None and self.metric_threshold:
            return self.metric_value / self.metric_threshold
        return 0.0


@dataclass
class Incident:
    id: str
    title: str
    signals: list[Signal] = field(default_factory=list)

    @property
    def services(self) -> set[str]:
        return {s.service for s in self.signals}

    @property
    def hosts(self) -> set[str]:
        return {s.host for s in self.signals if s.host}

    @property
    def started_at(self) -> datetime | None:
        return min((s.timestamp for s in self.signals), default=None)

    @property
    def ended_at(self) -> datetime | None:
        return max((s.timestamp for s in self.signals), default=None)

    @property
    def max_severity(self) -> Severity:
        if not self.signals:
            return Severity.INFO
        return max(self.signals, key=lambda s: s.severity.weight).severity

    @property
    def severity_score(self) -> int:
        return sum(s.severity.weight for s in self.signals)


@dataclass
class ScoredCause:
    cause: str
    category: str
    score: float
    evidence: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        # Squash score into 0..0.99 range for a readable confidence.
        return round(min(0.99, self.score / (self.score + 10.0)) if self.score > 0 else 0.0, 3)


@dataclass
class RemediationStep:
    order: int
    action: str
    reason: str
    category: str
    risk: str = "low"  # low | medium | high
