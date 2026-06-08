# ADR-0012: Backends scoped per-vertical

* Status: accepted
* Date: 2026-06-08
* Tags: backends, plugins, contracts

## Context and Problem Statement

CFA 1.1.0 ships three code-generation backends — PySpark, ANSI SQL, dbt
— under a process-wide `BackendRegistry` singleton (`cfa.backends`).
That works while every backend produces *data-write code*. The
horizontal architecture breaks the assumption:

- The agent vertical does not generate code at all. Agents *act*; the
  "backend" for an approved agent intent is whatever tool function gets
  called.
- The infra vertical produces Terraform plans (or rejects existing
  ones). PySpark code is meaningless in that vertical.
- A future financial vertical produces ledger entries / API call
  payloads. SQL and Spark backends are meaningless in that vertical.

If we keep the global `BackendRegistry`, every vertical sees every
backend regardless of relevance. Worse, the kernel cannot tell at runtime
whether a given backend is appropriate for a given signature, so static
validation degrades to "did this backend's output contain a forbidden
token?", which is verticals-leak hidden inside the kernel.

## Decision Drivers

- Backend choice is meaningful only within the context of a vertical.
- Verticals must own which backends are valid for their signatures.
- Backwards compatibility for `cfa evaluate --backend pyspark` so 1.x
  CLI usage keeps working.
- Third-party verticals must be able to ship their own backends without
  going through the global registry.

## Decision

### Each vertical owns its backends

`Vertical.backends()` returns the backend factories valid for signatures
in that vertical:

```python
class DataVertical(Vertical):
    name = "data"
    def backends(self):
        return {
            "pyspark": lambda: PySparkBackend(),
            "sql": lambda: SqlBackend(),
            "dbt": lambda: DbtBackend(),
        }
```

```python
class InfraVertical(Vertical):
    name = "infra"
    def backends(self):
        return {
            "terraform": lambda: TerraformBackend(),
        }
```

```python
class AgentVertical(Vertical):
    name = "agent"
    def backends(self):
        return {}  # agents act; nothing to generate
```

### Backend resolution

The kernel resolves backends via the vertical. `KernelConfig.backend`
remains a string (the backend's short name), but resolution is now:

```python
vertical = VerticalRegistry.singleton().get(signature.vertical)
backend_factory = vertical.backends().get(config.backend)
if backend_factory is None:
    raise BackendNotAvailable(
        vertical=signature.vertical,
        backend=config.backend,
        available=list(vertical.backends().keys()),
    )
```

The CLI surfaces an actionable error:

```
$ cfa evaluate ... --vertical infra --backend pyspark
Error: backend "pyspark" is not available for the "infra" vertical.
Available backends for "infra": terraform.
```

### The legacy global `BackendRegistry`

`cfa.backends.BackendRegistry` is preserved in 1.x for backward
compatibility. On query it now delegates to whichever vertical owns the
requested backend (resolved by walking registered verticals and matching
the short name). Lookups that match in exactly one vertical succeed
silently; lookups that match in multiple verticals emit a deprecation
warning telling the caller to pass `--vertical` explicitly. The legacy
registry is removed in 2.0.

### Static-validation forbidden tokens

`BackendCapabilities.forbidden_tokens` (the static-validation primitive)
is unchanged — it stays a property of the backend itself. What changes
is the *scope* of the lookup: the static validator asks the vertical
which backend was used and applies that backend's forbidden-token list.

## Consequences

Positive:

- Verticals are self-describing. Listing `cfa backend list --vertical data`
  shows exactly what's valid.
- A third-party vertical (`cfa-vertical-finance`) ships its own backend
  for ledger-entry generation without ever touching `cfa.backends`.
- Static validation stays correct in mixed-vertical setups.

Negative:

- The CLI grows a `--vertical` flag for disambiguation. We default it to
  `"data"` for 1.x so existing scripts keep working.
- The legacy `BackendRegistry` becomes a thin compatibility layer with
  delegated lookup. It carries a deprecation note pointing at the
  per-vertical registry going forward.
- Some backends (a future generic "JSON output" backend, for example)
  might be appropriate in every vertical. Verticals can register the
  same backend factory in their own scope; we accept the duplication
  in favor of clarity.

## Alternatives considered

- **Keep global `BackendRegistry`, add a `valid_verticals` field per
  backend.** Works but distributes the per-vertical knowledge across
  the backend code and the registry. The vertical-owning model
  concentrates it.
- **Drop backends entirely and let integrations generate output.**
  Considered. Rejected because the static-validation step is
  meaningfully different from integration emission; static validation
  is part of the governance path.

## See also

- ADR-0007 (Layer 4 placement).
- ADR-0009 (`Vertical.backends()` as the contract).
- `cfa.backends` module (the existing implementation this ADR
  reorganizes).
