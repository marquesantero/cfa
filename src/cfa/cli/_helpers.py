"""Shared helpers for CFA CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_catalog(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    import json
    raw = Path(path).read_text(encoding="utf-8")
    if path.endswith(".yaml") or path.endswith(".yml"):
        try:
            import yaml
            return yaml.safe_load(raw)
        except ImportError:
            import sys
            print("Error: PyYAML required for YAML catalogs. Install: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
    return json.loads(raw)


def load_policy(path_or_version: str) -> tuple[list | None, str]:
    p = Path(path_or_version)
    if p.suffix in (".yaml", ".yml", ".json"):
        from cfa.policy.bundle import PolicyBundle
        bundle = PolicyBundle.from_yaml(str(p)) if p.suffix != ".json" else PolicyBundle.from_json(str(p))
        return bundle.rules, bundle.version
    return None, path_or_version


def load_structured_file(path: str, yaml_error: str) -> dict[str, Any]:
    import json

    raw = Path(path).read_text(encoding="utf-8")
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml
            return yaml.safe_load(raw)
        except ImportError:
            import sys
            print(yaml_error, file=sys.stderr)
            sys.exit(1)
    return json.loads(raw)


def apply_config_defaults(args, config):
    """Apply config defaults to args for fields not explicitly set by user.

    Only fills in None values — never overrides explicit CLI flags.
    """
    if config is None:
        return
    if hasattr(args, "catalog") and args.catalog is None:
        cat = config.defaults.catalog
        if cat and Path(cat).exists():
            args.catalog = cat
    if hasattr(args, "policy_bundle") and args.policy_bundle in ("v1.0", None):
        pol = config.defaults.policy_bundle
        if pol and Path(pol).exists():
            args.policy_bundle = pol
    if hasattr(args, "backend") and args.backend in ("pyspark", None):
        args.backend = config.defaults.backend


def resolve_normalizer(args) -> object:
    import os
    import sys

    if args.normalizer == "mock":
        return None

    has_openai = os.environ.get("OPENAI_API_KEY")
    has_deepseek = os.environ.get("DEEPSEEK_API_KEY")

    if args.normalizer in ("openai", "llm") or (args.normalizer == "auto" and has_openai and not has_deepseek):
        from cfa.resolve.llm import LLMNormalizerBackend, OpenAILMProvider
        provider = OpenAILMProvider(
            model=args.llm_model or "gpt-4o-mini",
            api_key=args.llm_api_key or None,
            base_url=args.llm_base_url or None,
        )
        return LLMNormalizerBackend(provider=provider, strict=args.llm_strict)

    if args.normalizer == "deepseek" or (args.normalizer == "auto" and has_deepseek):
        from cfa.resolve.llm import LLMNormalizerBackend, OpenAILMProvider
        provider = OpenAILMProvider(
            model=args.llm_model or "deepseek-chat",
            base_url=args.llm_base_url or "https://api.deepseek.com",
            api_key=args.llm_api_key or has_deepseek or None,
        )
        return LLMNormalizerBackend(provider=provider, strict=args.llm_strict)

    if args.normalizer == "auto":
        print("Note: No LLM API key found. Using keyword-matching normalizer.", file=sys.stderr)
        print("Set OPENAI_API_KEY or DEEPSEEK_API_KEY for semantic understanding.", file=sys.stderr)

    return None


def resolve_config(args) -> object | None:
    """Discover and return CFA config if --config is provided or auto-detect."""
    from cfa.config import CfaConfig
    if hasattr(args, "config") and args.config:
        if Path(args.config).exists():
            return CfaConfig.from_yaml(args.config)
    return CfaConfig.discover()
