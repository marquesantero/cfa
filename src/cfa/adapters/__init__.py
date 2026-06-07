from __future__ import annotations

from collections.abc import Callable  # noqa: F401
from functools import wraps
from typing import Any

from cfa.core.kernel import KernelConfig, KernelOrchestrator


class CFAGuard:
    """Base governance guard for any callable.

    Wraps a function with CFA policy validation before execution.
    The function's first argument or a provided intent string is
    evaluated against the policy engine.

    Usage:
        guard = CFAGuard(policy_bundle="prod-v1", catalog=my_catalog)

        @guard("aggregate sales data")
        def my_pipeline(): ...

        @guard  # uses function name/docstring as intent
        def another_pipeline(): ...
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
        intent = fn.__doc__ or fn.__name__ if hasattr(fn, "__doc__") else str(fn)

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
        kernel = KernelOrchestrator(
            catalog=self._catalog, config=self._config, **self._kernel_kwargs
        )
        result = kernel.process(intent)
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

    Args:
        intent: Intent string to validate. If None, uses function docstring/name.
        policy_bundle: Policy bundle version or path to YAML file.
        catalog: Data catalog with dataset metadata.
        mode: 'block' (raise), 'warn' (log), or 'audit' (silent record).
    """
    guard = CFAGuard(policy_bundle=policy_bundle, catalog=catalog, mode=mode, **kwargs)
    if intent:
        return guard.guard(intent)
    return guard
