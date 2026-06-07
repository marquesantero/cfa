---
sidebar_position: 16
---

# API Reference

Public classes and functions exported by CFA v0.1.6.

## `cfa.core.kernel`

| Name | Description |
|------|-----------|
| `KernelOrchestrator` | Full 5-phase governed execution flow |
| `KernelOrchestrator.process(intent)` → `KernelResult` | Execute the full pipeline |
| `KernelConfig` | Configuration: policy_bundle_version, backend, strict_normalization, enable_* flags |

## `cfa.policy.engine`

| Name | Description |
|------|-----------|
| `PolicyEngine` | Evaluates `StateSignature` against declarative rules |
| `PolicyEngine.evaluate(signature)` → `PolicyResult` | Run policy evaluation |
| `PolicyEngine.from_bundle(path)` → `PolicyEngine` | Load engine from a YAML policy bundle |
| `PolicyRule` | Individual rule: condition + action + fault_code |

## `cfa.policy.bundle`

| Name | Description |
|------|-----------|
| `PolicyBundle` | Loadable YAML/JSON policy bundle |
| `PolicyBundle.from_yaml(path)` → `PolicyBundle` | Load from YAML |
| `PolicyBundle.rules` | `list[PolicyRule]` — parsed rules |

## `cfa.types`

| Name | Description |
|------|-----------|
| `StateSignature` | Immutable typed execution contract |
| `StateSignature.from_dict(d)` | Construct from dictionary |
| `StateSignature.to_dict()` | Serialize to dictionary |
| `PolicyResult` | Result of policy evaluation |
| `KernelResult` | Complete pipeline result |
| `Fault` | Governed failure event |
| `DatasetRef` | Dataset reference with governance metadata |
| `TargetLayer` | Enum: BRONZE, SILVER, GOLD |
| `DatasetClassification` | Enum: PUBLIC, INTERNAL, SENSITIVE, HIGH_VOLUME |

## `cfa.validation.static`

| Name | Description |
|------|-----------|
| `StaticValidator` | Analyzes generated code before execution |
| `StaticValidator.validate(code, sig, backend)` → `StaticValidationResult` | Run static validation |
| `ForbiddenToken` | Pattern that must not appear in generated code |

## `cfa.validation.signature`

| Name | Description |
|------|-----------|
| `validate_signature_data(data)` → `SignatureValidationResult` | Structural validation of StateSignature |
| `unwrap_signature_data(data)` → `dict` | Accept `{"signature": ...}` wrappers |

## `cfa.validation.runtime`

| Name | Description |
|------|-----------|
| `RuntimeValidator` | Validates execution metrics at runtime |
| `RuntimeThresholds` | Configurable thresholds: max_cost, max_shuffle_mb, max_null_ratio |

## `cfa.normalizer.base`

| Name | Description |
|------|-----------|
| `IntentNormalizer` | Resolves NL intent into `StateSignature` |
| `RuleBasedNormalizerBackend` | Deterministic catalog-grounded backend |
| `MockNormalizerBackend` | Test-only deterministic backend |
| `ConfirmationOrchestrator` | Risk-based confirmation escalation |

## `cfa.normalizer.llm`

| Name | Description |
|------|-----------|
| `LLMNormalizerBackend` | LLM-powered normalization with strict mode |
| `OpenAILMProvider` | OpenAI-compatible provider |

## `cfa.audit.trail`

| Name | Description |
|------|-----------|
| `AuditTrail` | Append-only hash-chained event store |
| `AuditTrail.record(...)` → `AuditEvent` | Record an event |
| `AuditTrail.verify_chain()` → `bool` | Verify SHA-256 hash chain integrity |
| `JsonLinesAuditStorage` | JSONL file backend |

## `cfa.audit.context`

| Name | Description |
|------|-----------|
| `ContextRegistry` | Live model of environment state |
| `ContextRegistry.get_environment_state()` → `dict` | Current state snapshot |

## `cfa.storage`

| Name | Description |
|------|-----------|
| `SqliteStorage(db_path)` | Unified SQLite storage for all CFA data |
| `SqliteStorage.ensure_schema()` | Auto-create migrated schema |
| `SqliteStorage.audit_append(event)` | Record audit event |
| `SqliteStorage.execution_append(dict)` | Record execution for lifecycle |
| `SqliteStorage.skill_upsert(hash, data)` | Persist skill state |

## `cfa.observability.promotion`

| Name | Description |
|------|-----------|
| `PromotionEngine` | Lifecycle management via IFo/IFs/IFg/IDI |
| `PromotionEngine.record_execution(record)` | Record execution for scoring |
| `PromotionEngine.evaluate(hash)` → `(SkillRecord, IndexScores)` | Evaluate a skill |
| `PromotionPolicy` | Thresholds: min_executions, ifo_threshold, ifs_threshold |

## `cfa.observability.indices`

| Name | Description |
|------|-----------|
| `IndexCalculator` | Computes IFo, IFs, IFg, IDI from records |
| `IndexScores` | ifo, ifs, ifg, idi + promotion_eligible, drift_detected |
| `ExecutionRecord` | Single execution data point |

## `cfa.backends`

| Name | Description |
|------|-----------|
| `BackendRegistry.singleton()` | Global registry (pyspark, sql, dbt) |
| `BackendRegistry.list()` → `list[str]` | List registered backends |
| `BackendRegistry.register(name, factory)` | Register a new backend |
| `BackendAdapter` | Abstract base for codegen backends |
| `BackendCapabilities` | Flags + forbidden_tokens |

## `cfa.sandbox`

| Name | Description |
|------|-----------|
| `SandboxRegistry.singleton()` | Global registry (mock, panic) |
| `SandboxBackend` | Pluggable execution backend |
| `MockSandboxBackend` | Deterministic test simulation |
| `SandboxExecutor` | Orchestrates plan execution |

## `cfa.runtime`

| Name | Description |
|------|-----------|
| `RuntimeGate` | Production governance gate |
| `GateConfig` | Configuration: policy_bundle, sandbox, execute |
| `RuntimeGate.validate(intent)` → `GateResult` | Pre-execution validation |

## `cfa.testing`

| Name | Description |
|------|-----------|
| `evaluate(intent, ...)` → `EvaluationResult` | Convenience wrapper for testing |
| `assert_passed(result)` | Assert evaluation passed |
| `assert_blocked(result)` | Assert evaluation blocked |

## `cfa.core.conditions`

| Name | Description |
|------|-----------|
| `build_condition(name)` → `Callable` | Build a named condition |
| `register_condition(name, factory)` | Register a custom condition |
| `list_conditions()` → `list[str]` | List registered conditions |

## `cfa.core.codegen`

| Name | Description |
|------|-----------|
| `CodeGenBackend` | Abstract base for code generation |
| `GeneratedCode` | Code artifact: language, code, metadata |

## `cfa.config`

| Name | Description |
|------|-----------|
| `CfaConfig.from_yaml(path)` → `CfaConfig` | Load configuration |
| `CfaConfig.discover()` → `CfaConfig | None` | Auto-discover cfa.yaml |
