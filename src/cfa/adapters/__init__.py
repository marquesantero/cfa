"""CFA adapter — universal governance guard for any Python callable.

Use `cfa_guard` (or `CFAGuard`) to wrap any function — agent tool, pipeline
step, Airflow task, Lambda handler — with a CFA policy check that runs before
the function executes. The check returns one of three outcomes:

- ``approve`` — the wrapped function runs.
- ``replan`` — in ``mode="block"``, raises ``PermissionError``. In
  ``mode="warn"``/``mode="audit"``, the function runs and the decision is
  recorded.
- ``block`` — same handling as ``replan`` per ``mode``.

This module is framework-agnostic. The 1.0.0 release shipped per-framework
modules (``cfa.adapters.langgraph``, ``crewai``, ``autogen``, ``dspy``,
``openai_agents``) that were all aliases of this same ``cfa_guard``. They
were removed in 1.1.0 — 1.0.0 had no real adopters, so we are renaming the
public surface freely while it still costs nothing. See
``docs/integrations/use-cfa-guard-with-frameworks.md`` for the recommended
usage pattern with each agent framework.
"""

from __future__ import annotations

from collections.abc import Callable  # noqa: F401
from functools import wraps
from typing import Any

from cfa.core.kernel import KernelConfig, KernelOrchestrator


class CFAGuard:
    """Reusable governance guard for any callable.

    A single ``CFAGuard`` instance constructs the underlying
    ``KernelOrchestrator`` lazily on first use and caches it for every
    subsequent guarded call. Use this directly when you want one guard to
    govern multiple functions with the same policy + catalog.

    Usage::

        guard = CFAGuard(policy_bundle="prod-v1", catalog=my_catalog)

        @guard("aggregate sales data")
        def my_pipeline(): ...

        @guard.guard("publish to gold")
        def publish(): ...

        @guard
        def another_pipeline():
            \"\"\"join NFe with Clientes persist Silver\"\"\"
            ...
    """

    def __init__(
        self,
        policy_bundle: str = "v1.0",
        catalog: dict[str, Any] | None = None,
        backend: str = "pyspark",
        mode: str = "block",  # block | warn | audit
        **kernel_kwargs: Any,
    ) -> None:
        self._config = KernelConfig(
            policy_bundle_version=policy_bundle,
            backend=backend,
            warnings_are_blocking=(mode == "block"),
        )
        self._catalog = catalog
        self._mode = mode
        self._kernel_kwargs = kernel_kwargs
        # Lazily constructed on first guarded call, then reused.
        self._kernel: KernelOrchestrator | None = None

    def _get_kernel(self) -> KernelOrchestrator:
        if self._kernel is None:
            self._kernel = KernelOrchestrator(
                catalog=self._catalog,
                config=self._config,
                **self._kernel_kwargs,
            )
        return self._kernel

    def __call__(self, fn_or_intent):
        if isinstance(fn_or_intent, str):
            intent = fn_or_intent

            def decorator(fn):
                @wraps(fn)
                def wrapper(*args, **kwargs):
                    self._check(intent)
                    return fn(*args, **kwargs)
                return wrapper
            return decorator

        fn = fn_or_intent
        intent = (fn.__doc__ or fn.__name__) if hasattr(fn, "__doc__") else str(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            self._check(intent)
            return fn(*args, **kwargs)
        return wrapper

    def guard(self, intent: str):
        """Explicit guard with intent string."""
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                self._check(intent)
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    def _check(self, intent: str) -> None:
        result = self._get_kernel().process(intent)
        if not result.is_executable and self._mode == "block":
            raise PermissionError(
                f"CFA blocked intent '{intent[:80]}': {result.blocked_reason}"
            )


def cfa_guard(
    intent: str | None = None,
    *,
    policy_bundle: str = "v1.0",
    catalog: dict[str, Any] | None = None,
    mode: str = "block",
    **kwargs: Any,
):
    """Universal CFA governance guard for any callable or agent tool.

    Each call to this function constructs a new ``CFAGuard`` (and therefore a
    new ``KernelOrchestrator`` is created lazily on first invocation of the
    wrapped function). For multiple guarded functions sharing the same
    configuration, instantiate ``CFAGuard`` directly so a single kernel is
    reused across all of them.

    Args:
        intent: Intent string to validate. If ``None``, uses the wrapped
            function's docstring (or name as fallback).
        policy_bundle: Policy bundle version or path to a YAML file.
        catalog: Data catalog with dataset metadata.
        mode: ``'block'`` (raise on block/replan), ``'warn'`` (log and
            proceed), or ``'audit'`` (silently record).
    """
    guard = CFAGuard(policy_bundle=policy_bundle, catalog=catalog, mode=mode, **kwargs)
    if intent:
        return guard.guard(intent)
    return guard
