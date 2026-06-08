---
sidebar_position: 9
---

# Extending CFA

CFA is built so that adding a new **vertical** (a new domain to govern —
infrastructure plans, agent tool calls, financial transactions, ML
deploys, anything that follows the *declare intent → decide → execute →
audit* pattern) or a new **integration** (a new way to feed signatures
in and emit decisions out — dbt manifests, GitHub PRs, Slack alerts) is
**a pip-installable package**. You do not need to touch `cfa-kernel`.

This page is the recipe.

The architectural reasoning lives in the ADRs:

- [ADR-0007](https://github.com/marquesantero/cfa/blob/main/docs/adr/0007-layered-architecture.md) — Layered architecture
- [ADR-0008](https://github.com/marquesantero/cfa/blob/main/docs/adr/0008-generic-signature.md) — Generic `StateSignature`
- [ADR-0009](https://github.com/marquesantero/cfa/blob/main/docs/adr/0009-vertical-protocol.md) — Vertical protocol
- [ADR-0010](https://github.com/marquesantero/cfa/blob/main/docs/adr/0010-integration-protocol.md) — Integration + DecisionSink
- [ADR-0011](https://github.com/marquesantero/cfa/blob/main/docs/adr/0011-condition-registry.md) — ConditionRegistry
- [ADR-0012](https://github.com/marquesantero/cfa/blob/main/docs/adr/0012-per-vertical-backends.md) — Per-vertical backends

## The two extension points

### Vertical

Use a vertical when you are introducing a **new domain** that signatures
can talk about: a new kind of `payload` and `constraints`, a new set of
named conditions, optionally a new backend type.

Examples of verticals CFA could host:

- `agent` — LLM tool calls. Payload carries `tool`, `args`,
  `caller_agent`. Constraints carry `allowed_tools`, `rate_limit`.
- `infra` — Terraform plans, Pulumi previews. Payload carries resources
  about to change. Constraints carry blast-radius limits, forbidden
  resource names.
- `finance` — money movements. Payload carries `source`, `destination`,
  `amount`, `currency`. Constraints carry per-country limits, 4-eyes
  flags.
- `notifications` — outbound campaigns. Payload carries `audience_size`,
  `channel`. Constraints carry frequency caps, opt-in requirements.
- `ml-deploy` — model promotions. Payload carries `model_id`,
  `target_env`. Constraints carry holdout-perf gates, drift thresholds.

### Integration

Use an integration when you are introducing a **new way for signatures
to arrive** (and decisions to leave). Integrations target an existing
vertical; they do not introduce new domain concepts.

Examples:

- `cfa-int-dbt` — reads `target/manifest.json`, produces signatures for
  the `data` vertical.
- `cfa-int-airflow` — wraps an Airflow operator, produces signatures for
  whichever vertical the DAG declares.
- `cfa-int-github-pr` — reads a PR diff, produces signatures for one or
  more verticals depending on the files changed.
- `cfa-int-slack` — purely a DecisionSink. Receives decisions, formats
  them as Slack messages.

## Recipe 1 — Build a new vertical

### Step 1: scaffold the package

A vertical is a regular Python package. Layout:

```text
cfa-vertical-myapp/
├── pyproject.toml
└── src/
    └── cfa_vertical_myapp/
        ├── __init__.py
        ├── vertical.py
        ├── conditions.py
        └── schemas.py
```

### Step 2: implement the Vertical protocol

```python
# src/cfa_vertical_myapp/vertical.py
from typing import Any
from cfa.core.vertical import Vertical
from cfa_vertical_myapp.conditions import (
    build_caller_in_allowlist,
    build_payload_under_limit,
)
from cfa_vertical_myapp.schemas import PAYLOAD_SCHEMA, CONSTRAINTS_SCHEMA


class MyappVertical:
    name = "myapp"

    def payload_schema(self) -> dict[str, Any]:
        return PAYLOAD_SCHEMA

    def constraints_schema(self) -> dict[str, Any]:
        return CONSTRAINTS_SCHEMA

    def conditions(self) -> dict[str, Any]:
        # CFA auto-prefixes these with the vertical name:
        # 'caller_in_allowlist' becomes 'myapp.caller_in_allowlist'.
        return {
            "caller_in_allowlist": build_caller_in_allowlist,
            "payload_under_limit": build_payload_under_limit,
        }

    def default_rules(self) -> list:
        return []  # optional — ship YAML policy bundles separately

    def catalog_schema(self) -> dict[str, Any] | None:
        return None  # optional

    def backends(self) -> dict[str, Any]:
        return {}  # optional — empty for "no codegen" verticals
```

### Step 3: write condition factories

A condition factory takes a parameter dict (from YAML) and returns the
actual predicate over a `StateSignature`.

```python
# src/cfa_vertical_myapp/conditions.py
from typing import Any
from cfa.types import StateSignature


def build_caller_in_allowlist(meta: dict[str, Any]):
    allowed = set(meta.get("allow_list", []))

    def check(sig: StateSignature) -> bool:
        caller = sig.payload.get("caller") if isinstance(sig.payload, dict) else None
        return caller not in allowed

    return check


def build_payload_under_limit(meta: dict[str, Any]):
    limit = meta.get("limit", 1000)

    def check(sig: StateSignature) -> bool:
        size = sig.payload.get("size", 0) if isinstance(sig.payload, dict) else 0
        return size > limit

    return check
```

### Step 4: declare an entry point

```toml
# pyproject.toml
[project]
name = "cfa-vertical-myapp"
version = "0.1.0"
dependencies = ["cfa-kernel>=1.1.0"]

[project.entry-points."cfa.verticals"]
myapp = "cfa_vertical_myapp.vertical:MyappVertical"
```

That's all. After `pip install cfa-vertical-myapp`, CFA discovers the
vertical the first time anyone calls `VerticalRegistry.singleton().list()`
or `.get("myapp")`. The vertical's conditions land in the
`ConditionRegistry` under their qualified names
(`myapp.caller_in_allowlist`, `myapp.payload_under_limit`).

### Step 5: write rules

YAML policy bundles reference the conditions by their qualified name:

```yaml
policy_bundle:
  version: "myapp-prod-v1"
  rules:
    - name: caller_must_be_allowed
      condition: myapp.caller_in_allowlist
      condition_params:
        allow_list: ["agent_a", "agent_b"]
      action: block
      fault_code: MYAPP_UNAUTHORIZED_CALLER
      severity: critical
      message: "Caller is not in the configured allow list."
```

## Recipe 2 — Build a new integration

### Step 1: scaffold

```text
cfa-int-mytool/
├── pyproject.toml
└── src/
    └── cfa_int_mytool/
        ├── __init__.py
        └── integration.py
```

### Step 2: implement the Integration protocol

```python
# src/cfa_int_mytool/integration.py
from typing import Any
from cfa.core.integration import Integration, IntegrationInputError
from cfa.types import KernelResult, StateSignature


class MyToolIntegration:
    name = "mytool"
    consumes = ["mytool-output-json"]
    produces = "myapp"

    def build_signatures(self, raw: Any) -> list[StateSignature]:
        if not isinstance(raw, dict) or "calls" not in raw:
            raise IntegrationInputError(
                "$.calls",
                "expected the input to have a 'calls' array",
            )
        return [
            StateSignature(
                # ... build per-call signatures here ...
            )
            for call in raw["calls"]
        ]

    def emit_decisions(self, results: list[KernelResult]) -> None:
        # Surface decisions back into the tool's natural channel.
        # For a CI-style integration, this might be where you set the
        # exit code; for a PR integration, where you post a comment.
        pass
```

### Step 3: declare the entry point

```toml
[project.entry-points."cfa.integrations"]
mytool = "cfa_int_mytool.integration:MyToolIntegration"
```

## Recipe 3 — Build a DecisionSink

Sinks are independent of integrations. The same decision flows into
every registered sink simultaneously — stdout, OTel, Slack, JIRA — without
any of them knowing about the others. Sink failures are logged but never
abort decision processing.

```python
# src/cfa_sink_slack/sink.py
import json
import urllib.request
from cfa.core.integration import DecisionSink
from cfa.types import KernelResult


class SlackWebhookSink:
    name = "slack-webhook"

    def __init__(self, webhook_url: str):
        self._url = webhook_url

    def emit(self, result: KernelResult) -> None:
        if result.state.value not in ("blocked", "replanned"):
            return  # only ping on interesting outcomes
        body = json.dumps({"text": f"CFA {result.state.value}: {result.intent_id}"}).encode()
        urllib.request.urlopen(self._url, data=body, timeout=2.0)

    def flush(self) -> None:
        pass
```

```toml
[project.entry-points."cfa.decision_sinks"]
slack-webhook = "cfa_sink_slack.sink:SlackWebhookSink"
```

## Running the contracts as tests

Every plugin should test its public surface against the CFA contracts.
Minimum coverage:

```python
from cfa.core.vertical import Vertical
from cfa.core.integration import Integration, DecisionSink

def test_vertical_satisfies_protocol():
    from cfa_vertical_myapp import MyappVertical
    assert isinstance(MyappVertical(), Vertical)

def test_integration_satisfies_protocol():
    from cfa_int_mytool import MyToolIntegration
    assert isinstance(MyToolIntegration(), Integration)

def test_sink_satisfies_protocol():
    from cfa_sink_slack import SlackWebhookSink
    assert isinstance(SlackWebhookSink("http://example"), DecisionSink)
```

`Protocol`s are `runtime_checkable`, so `isinstance` works. The CFA test
suite carries reference implementations at
[`tests/contract/`](https://github.com/marquesantero/cfa/tree/main/tests/contract)
that show the full mock vertical, mock integration, and mock sink that
the contracts have to support.

## When in doubt

- If your code needs to import from `cfa.core.kernel`, `cfa.policy.engine`,
  `cfa.audit.trail`, `cfa.types`, `cfa.resolve.base`, or `cfa.validate.*`,
  that is **expected**. Those modules are part of the public Layer 1/2
  API.
- If your code needs to import from `cfa.verticals.data.*` or
  `cfa.integrations.*`, you are **probably depending on an internal
  thing**. Use the public protocols instead, or ship the dependency
  inside your own package.
- If `cfa-kernel` would have to change to make your plugin work, **that
  is a bug in CFA's contracts**. Open an issue.

## Discoverability

CFA exposes a CLI command to list everything it can see:

```bash
cfa status --plugins
```

Sample output:

```text
Verticals:
  data          (built-in)
  myapp         (from cfa-vertical-myapp 0.1.0)

Integrations:
  dbt-check     (from cfa-int-dbt 1.0.0)
  mytool        (from cfa-int-mytool 0.1.0)

Decision sinks:
  stdout-json   (built-in)
  slack-webhook (from cfa-sink-slack 0.1.0)
```

(Built-in versions ship inside `cfa-kernel` starting at 1.2. External
plugins are surfaced as soon as they declare a matching entry point.)
