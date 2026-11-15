# Autonomous Multimodal Incident Commander for Root-Cause Infrastructure Triage

An autonomous incident-triage system that ingests heterogeneous infrastructure
signals — **alerts, logs, and metrics** — correlates them into coherent incidents,
ranks the most likely root causes with evidence, and proposes an ordered,
low-risk-first remediation plan.

Built by Rohit Garapati as a portfolio project demonstrating production-style
incident response automation: multimodal signal normalization, dependency-aware
correlation, heuristic root-cause analysis, and runbook-style remediation.

## What it does

1. **Ingestion** (`incident_commander/ingestion.py`) — Parses alert, log, and metric
   payloads in their different native shapes into one normalized `Signal` model.
   Severity is taken from explicit fields when present and otherwise inferred:
   log keywords (OOM, connection refused, timeout), and metric breach ratios
   (value vs. threshold escalates severity automatically).
2. **Correlation** (`incident_commander/correlation.py`) — Groups signals that
   belong to the same failure using union-find over a time window plus shared
   dimensions: same service, same host, same `incident_key`/`trace_id`/
   `dependency_group`, or a known service dependency (e.g. `checkout → api → database`).
   A database failure and the API/checkout timeouts it causes collapse into
   **one** incident; an unrelated signal hours later stays separate.
3. **Root-cause ranking** (`incident_commander/ranking.py`) — Nine candidate-cause
   rules (database pool exhaustion, slow queries, downstream timeouts, OOM /
   memory pressure, CPU saturation, disk pressure, cache failure, network
   connectivity, deployment regression) score evidence by pattern hits, signal
   severity, metric breach magnitude, earliness (causes precede symptoms), and
   blast radius (evidence on a service others depend on counts more). Output is
   deterministic: descending score, each cause with its supporting evidence and
   a confidence value.
4. **Remediation** (`incident_commander/remediation.py`) — Turns the top ranked
   causes into a deduplicated, contiguously numbered plan from a per-category
   runbook catalog (database, network, resource, cache, change, unknown),
   starting with a general evidence-snapshot step and labelling each step's risk.

## Stack

- **Python 3.10+** — pure standard library only; no network calls, no credentials
- **pytest** — test runner only

## Project layout

```
incident_commander/
    models.py        # Signal, Incident, ScoredCause, RemediationStep dataclasses
    ingestion.py     # alert/log/metric parsing and severity inference
    correlation.py   # union-find correlation with dependency map
    ranking.py       # root-cause rules, scoring, deterministic ranking
    remediation.py   # runbook catalog -> ordered remediation plan
    pipeline.py      # ingest -> correlate -> rank -> remediate + text report
    sample_data.py   # loader for the bundled sample scenario
data/
    sample_signals.json   # DB pool exhaustion cascade + separate cache OOM incident
tests/               # ingestion, correlation, ranking, remediation, pipeline
main.py              # CLI entry point
```

## How to run

```bash
cd autonomous-multimodal-incident-commander
python main.py                              # bundled sample data, text report
python main.py --json                       # same, as JSON
python main.py data/sample_signals.json     # your own signals file
python main.py --window 600 data/sample_signals.json   # custom correlation window (seconds)
```

Sample output (abridged):

```
INC-001: CRITICAL on api, checkout, database: ...
  Ranked root causes:
    - database_connection_pool_exhaustion (category=database, score=..., confidence=...)
  Remediation plan:
    1. [low] Snapshot the correlated timeline and affected services -- ...
    2. [low] Inspect active DB connections and the top waiting queries -- ...
```

Input format: a JSON list, or `{"signals": [...]}`. Each signal needs at minimum
a `type` (`alert` | `log` | `metric`), a `service`, a `timestamp`
(ISO-8601 or epoch), and a `message` — or, for metrics, `metric` / `value` / `threshold`.

## How to test

```bash
cd autonomous-multimodal-incident-commander
python -m pytest
```

The suite covers ingestion parsing and severity inference, correlation grouping
(related signals → one incident, unrelated → separate), root-cause ranking order
and determinism, remediation output, and an end-to-end pipeline run.

## Author

Rohit Garapati — Network Operations Engineer (data center & network support,
Cloudflare client via Tavas Systems). Authorized to work in the US. No sponsorship required.
