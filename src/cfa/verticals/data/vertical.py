"""The data vertical — governance for writes to a lakehouse.

This vertical is the original CFA use case: declared intent over writes
to a layered (bronze/silver/gold) data store, with PII, partition,
classification, merge-key, and cost-ceiling primitives.

It is shipped inside ``cfa-kernel`` for two reasons:

1. It is the historical default; removing it would break every existing
   user of the library.
2. It serves as the reference implementation of the
   :class:`cfa.core.vertical.Vertical` protocol — third-party vertical
   authors copy this layout. See ``docs/extending.md``.

The vertical wraps the existing data-shaped infrastructure that lives
elsewhere in the package (policy rules in :mod:`cfa.policy.engine`,
backends in :mod:`cfa.backends`, condition factories in
:mod:`cfa.core.conditions`). In 1.2 those modules will move *into* this
vertical, and `cfa.types`/`cfa.policy.engine` will become generic. The
migration is staged to avoid touching every test in a single commit.
"""

from __future__ import annotations

from typing import Any

# ── JSON Schemas ─────────────────────────────────────────────────────────────
# These are the shapes a future generic StateSignature.payload /
# constraints would carry for the data vertical. Today they document the
# current typed dataclasses so consumers can introspect the shape.

_DATASET_SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "classification": {
            "type": "string",
            "enum": ["public", "internal", "sensitive", "high_volume"],
            "default": "internal",
        },
        "size_gb": {"type": "number", "minimum": 0, "default": 0.0},
        "pii_columns": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "partition_column": {"type": ["string", "null"], "default": None},
        "merge_keys": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
    },
}

PAYLOAD_SCHEMA: dict[str, Any] = {
    "$id": "cfa.verticals.data/payload.v1.json",
    "title": "CFA Data Vertical — Signature Payload",
    "type": "object",
    "required": ["target_layer", "datasets"],
    "properties": {
        "target_layer": {
            "type": "string",
            "enum": ["bronze", "silver", "gold"],
        },
        "datasets": {
            "type": "array",
            "items": _DATASET_SCHEMA,
            "minItems": 1,
        },
    },
}


CONSTRAINTS_SCHEMA: dict[str, Any] = {
    "$id": "cfa.verticals.data/constraints.v1.json",
    "title": "CFA Data Vertical — Signature Constraints",
    "type": "object",
    "properties": {
        "no_pii_raw": {"type": "boolean", "default": True},
        "merge_key_required": {"type": "boolean", "default": True},
        "enforce_types": {"type": "boolean", "default": True},
        "partition_by": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "max_cost_dbu": {"type": ["number", "null"], "default": None},
        "custom": {"type": "object", "default": {}},
    },
    "additionalProperties": False,
}


CATALOG_SCHEMA: dict[str, Any] = {
    "$id": "cfa.verticals.data/catalog.v1.json",
    "title": "CFA Data Vertical — Catalog",
    "type": "object",
    "required": ["datasets"],
    "properties": {
        "datasets": {
            "type": "object",
            "additionalProperties": _DATASET_SCHEMA,
        },
    },
}


# ── The vertical ─────────────────────────────────────────────────────────────


class DataVertical:
    """The reference data-writes vertical.

    Implements :class:`cfa.core.vertical.Vertical` structurally. The
    methods delegate to the existing infrastructure shipped in
    ``cfa.policy``, ``cfa.backends``, and ``cfa.core.conditions``;
    nothing in this vertical adds new behavior to the kernel.

    Conditions returned by :meth:`conditions` are auto-prefixed with
    ``"data."`` by the :class:`cfa.core.vertical.VerticalRegistry` so the
    same factories end up registered under both their canonical
    unprefixed names (kept for back-compat through 1.x) and their
    qualified ``data.<name>`` form.
    """

    name = "data"

    def payload_schema(self) -> dict[str, Any]:
        return PAYLOAD_SCHEMA

    def constraints_schema(self) -> dict[str, Any]:
        return CONSTRAINTS_SCHEMA

    def conditions(self) -> dict[str, Any]:
        from cfa.core import conditions as c

        return {
            "pii_in_protected_layer": c._pii_in_protected_layer,
            "missing_merge_key": c._missing_merge_key,
            "missing_partition": c._missing_partition,
            "enforce_types_disabled": c._enforce_types_disabled,
            "pii_without_policy": c._pii_without_policy,
            "sensitive_without_partition": c._sensitive_without_partition,
            "cost_budget_exceeded": c._cost_budget_exceeded,
        }

    def default_rules(self) -> list[Any]:
        from cfa.policy.engine import build_default_ruleset

        return build_default_ruleset()

    def catalog_schema(self) -> dict[str, Any] | None:
        return CATALOG_SCHEMA

    def backends(self) -> dict[str, Any]:
        from cfa.backends import BackendRegistry

        registry = BackendRegistry.singleton()
        return {name: registry.get(name) for name in registry.list()}


__all__ = [
    "CATALOG_SCHEMA",
    "CONSTRAINTS_SCHEMA",
    "PAYLOAD_SCHEMA",
    "DataVertical",
]
