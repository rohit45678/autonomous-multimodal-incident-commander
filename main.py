#!/usr/bin/env python3
"""Runnable entry point.

Usage:
    python main.py                      # run on bundled sample data
    python main.py data/sample_signals.json
    python main.py --json data/sample_signals.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from incident_commander.ingestion import load_signals_from_json  # noqa: E402
from incident_commander.pipeline import format_report, run_pipeline  # noqa: E402
from incident_commander.sample_data import load_sample_signals  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Autonomous Multimodal Incident Commander for Root-Cause Infrastructure Triage")
    parser.add_argument("input", nargs="?", help="JSON file of signals (default: bundled sample)")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--window", type=int, default=900,
                        help="Correlation window in seconds (default 900)")
    args = parser.parse_args(argv)

    if args.input:
        signals = load_signals_from_json(args.input)
        raw = [{"id": s.id, "type": s.type.value, "service": s.service,
                "timestamp": s.timestamp.isoformat(), "severity": s.severity.value,
                "message": s.message, "host": s.host, "labels": s.labels,
                "metric": s.metric_name, "value": s.metric_value,
                "threshold": s.metric_threshold} for s in signals]
    else:
        raw = load_sample_signals()

    report = run_pipeline(raw, window_seconds=args.window)
    print(json.dumps(report, indent=2) if args.json else format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
