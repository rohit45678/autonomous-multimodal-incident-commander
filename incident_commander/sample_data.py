"""Bundled sample signals (same scenario as data/sample_signals.json)."""
import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data" / "sample_signals.json"


def load_sample_signals() -> list[dict]:
    return json.loads(_DATA.read_text(encoding="utf-8"))["signals"]
