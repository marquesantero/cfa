# NOTE: This module is internal to CFA — not part of the public API. Use at your own risk.
"""
CFA Catalog Loader — External Catalog Integration
==================================================
Abstract interface for loading catalogs from external sources (DataHub, OpenMetadata, etc.).

Usage:
    from cfa.storage.catalog_loader import DataHubCatalogLoader

    loader = DataHubCatalogLoader(base_url="http://datahub:8080")
    catalog = loader.load()
    # -> {"nfe_bronze": {"type": "delta", "classification": "high_volume", ...}}
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CatalogLoader(ABC):
    """Abstract base for loading catalogs from external sources."""

    @abstractmethod
    def load(self) -> dict[str, Any]:
        """Load and return a CFA-compatible catalog dict.

        Returns a flat dict: {dataset_name: {type, layer, classification, pii, pii_columns, size_gb, ...}}
        """
        ...


class DataHubCatalogLoader(CatalogLoader):
    """Load catalog from a DataHub instance via REST API.

    Requires: pip install requests
    """

    def __init__(self, base_url: str = "http://localhost:8080", token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def load(self) -> dict[str, Any]:
        try:
            import requests
        except ImportError:
            raise ImportError("requests is required for DataHubCatalogLoader. Install: pip install requests")

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        resp = requests.get(
            f"{self.base_url}/api/graphql",
            json={"query": "{ search(input: { type: DATASET, start: 0, count: 100 }) { entities { entity { urn type ... on Dataset { name platform { name } properties { description } } } } } }"},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        catalog: dict[str, Any] = {}
        entities = data.get("data", {}).get("search", {}).get("entities", [])
        for entry in entities:
            entity = entry.get("entity", {})
            name = entity.get("name", "")
            if not name:
                continue
            catalog[name] = {
                "type": entity.get("platform", {}).get("name", "unknown"),
                "layer": "bronze",
                "classification": "internal",
                "pii": False,
                "pii_columns": [],
                "size_gb": 0,
                "description": entity.get("properties", {}).get("description", ""),
            }
        return catalog


class OpenMetadataCatalogLoader(CatalogLoader):
    """Load catalog from an OpenMetadata instance via REST API.

    Requires: pip install requests
    """

    def __init__(self, base_url: str = "http://localhost:8585", token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def load(self) -> dict[str, Any]:
        try:
            import requests
        except ImportError:
            raise ImportError("requests is required for OpenMetadataCatalogLoader. Install: pip install requests")

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        resp = requests.get(
            f"{self.base_url}/api/v1/tables?limit=100",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        catalog: dict[str, Any] = {}
        for table in data.get("data", []):
            name = table.get("fullyQualifiedName", "")
            if not name:
                continue
            catalog[name] = {
                "type": table.get("serviceType", "unknown"),
                "layer": "bronze",
                "classification": "internal",
                "pii": False,
                "pii_columns": [],
                "size_gb": 0,
                "description": table.get("description", ""),
            }
        return catalog
