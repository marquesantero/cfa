---
sidebar_position: 10
---

# CLI Reference

CFA ships with a zero-dependency CLI built on `argparse`.

## Governance

### `cfa evaluate`

Run an intent through the full governance pipeline.

```bash
cfa evaluate <intent> [options]

Options:
  --config PATH             Path to cfa.yaml config file
  --catalog, -c PATH        Catalog JSON/YAML file
  --policy-bundle, -p VER   Policy bundle version or path
  --backend, -b NAME        Codegen backend (pyspark, sql, dbt)
  --format, -f FORMAT       Output format: table, json, summary
  --strict                  Block ambiguous intents
  --exit-code               Exit 1 if blocked
  --normalizer NAME         Normalizer backend (auto, rule_based, mock, openai, deepseek, llm)
  --llm-strict              Require LLM output to match catalog exactly
```

### `cfa policy check`

Evaluate a StateSignature against a policy bundle (no natural language).

```bash
cfa policy check --signature sig.json [options]

Options:
  --config PATH             Path to cfa.yaml config file
  --catalog PATH            Path to catalog (enables catalog_hash + cross-validation)
  --policy-bundle, -p VER   Policy bundle version or path
  --format, -f FORMAT       Output: summary, json
  --exit-code               Exit 1 when action is not approve
  --strict                  Validate signature datasets against catalog
  --require-datasets        Require at least one dataset
  --audit-log FILE          Append decision to audit JSONL file
```

## Validation (CI-ready)

### `cfa catalog validate`

```bash
cfa catalog validate catalog.json --require-datasets --format json
```

### `cfa signature validate`

```bash
cfa signature validate request.json --require-datasets --format json
```

### `cfa policy validate`

```bash
cfa policy validate policies/prod.yaml --format json
```

All validation commands return JSON with `valid`, `issue_count`, and `issues[]`. Exit code 1 on invalid.

### `cfa validate`

Validate an intent against a behavior spec.

```bash
cfa validate --spec fiscal_governance.yaml --intent "aggregate sales" --exit-code
```

## Policy rules

```bash
cfa rules list                          # List all active rules
cfa rules explain FAULT_CODE            # Explain a specific fault
```

## Audit

```bash
cfa audit show --id INTENT_ID --file audit.jsonl --format json
cfa audit verify --file audit.jsonl
cfa audit verify --file audit.jsonl --id INTENT_ID
```

## Storage management

```bash
cfa storage stats --db cfa.db --format json
cfa storage cleanup --db cfa.db --retention 90
cfa storage cleanup --db cfa.db --before 2025-01-01T00:00:00
cfa storage vacuum --db cfa.db

# JSONL backend (zero-dependency)
cfa storage stats --dir ./audit_data/
cfa storage cleanup --dir ./audit_data/ --retention 90
```

## Lifecycle

```bash
cfa lifecycle evaluate --db cfa.db --window 30 --format json
cfa lifecycle list --db cfa.db --format json
```

## Project

```bash
cfa init                                # Bootstrap project (.cfa/)
cfa init --dir ./my-project             # Custom directory
cfa status                              # Project health + storage stats
cfa status --config .cfa/config.yaml    # Explicit config path
cfa status --format json                # Machine-readable
```

## Backends

```bash
cfa backend list                        # List registered backends (pyspark, sql, dbt)
```

## Taxonomy

```bash
cfa taxonomy generate --spec FILE       # Generate taxonomy from spec
cfa taxonomy test-intents --spec FILE   # Generate test intents
```

## Reports

```bash
cfa report execution --intent "..." --output report.html
cfa report audit --intent-id ID --output audit.html
cfa report lifecycle --period 90 --audit-file audit.jsonl --output dashboard.html
cfa report compliance --audit-file audit.jsonl --output compliance.html
cfa report dashboard --period 90 --audit-file audit.jsonl --output dashboard.html
```

## Serve

```bash
cfa serve --port 8765 --metrics-port 9090
```

Serves `/health` and `/metrics` endpoints. No synthetic data — uses live metrics only.
