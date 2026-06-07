"""Deterministic content-addressable hashing for CFA governance artifacts.

Every artifact that participates in a governed decision (catalog, policy bundle,
signature) MUST be hashable so the audit trail can cryptographically bind a
decision to its exact inputs.

Hashes are computed on canonical JSON serializations of the artifact data,
ensuring the same content always produces the same hash regardless of formatting
or field order in the original YAML/JSON file.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_governance_artifact(data: dict[str, Any] | None) -> str:
    """Return a deterministic SHA-256 hash for a governance artifact.

    The artifact is serialized to JSON with sorted keys so that the same logical
    content always produces the same hash.

    Returns an empty string when data is None.
    """
    if data is None:
        return ""
    canonical = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_file_content(path: str) -> str:
    """Return the SHA-256 hash of a file's raw content.

    Unlike ``hash_governance_artifact`` this hashes the bytes on disk, which is
    useful for verifying that a file has not changed even if its logical content
    (after parsing) is identical.
    """
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
