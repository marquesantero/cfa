---
sidebar_position: 16
---

# Referência da API

Classes e funções públicas exportadas pelo CFA v1.0.0.

## `cfa.core.kernel`

| Nome | Descrição |
|------|-----------|
| `KernelOrchestrator` | Fluxo completo de execução governada em 5 fases |
| `KernelOrchestrator.process(intent)` → `KernelResult` | Executar o pipeline completo |
| `KernelConfig` | Configuração: policy_bundle_version, backend, strict_normalization, flags enable_* |

## `cfa.policy.engine`

| Nome | Descrição |
|------|-----------|
| `PolicyEngine` | Avalia `StateSignature` contra regras declarativas |
| `PolicyEngine.evaluate(signature)` → `PolicyResult` | Executar avaliação de política |
| `PolicyEngine.from_bundle(path)` → `PolicyEngine` | Carregar de um policy bundle YAML |
| `PolicyRule` | Regra individual: condição + ação + fault_code |

## `cfa.policy.bundle`

| Nome | Descrição |
|------|-----------|
| `PolicyBundle` | Policy bundle YAML/JSON carregável |
| `PolicyBundle.from_yaml(path)` → `PolicyBundle` | Carregar de YAML |
| `PolicyBundle.rules` | `list[PolicyRule]` — regras analisadas |

## `cfa.types`

| Nome | Descrição |
|------|-----------|
| `StateSignature` | Contrato de execução tipado imutável |
| `StateSignature.from_dict(d)` | Construir a partir de dicionário |
| `StateSignature.to_dict()` | Serializar para dicionário |
| `PolicyResult` | Resultado da avaliação de política |
| `KernelResult` | Resultado completo do pipeline |
| `Fault` | Evento de falha governada |
| `DatasetRef` | Referência a dataset com metadados de governança |
| `TargetLayer` | Enum: BRONZE, SILVER, GOLD |
| `DatasetClassification` | Enum: PUBLIC, INTERNAL, SENSITIVE, HIGH_VOLUME |

## `cfa.validation.static`

| Nome | Descrição |
|------|-----------|
| `StaticValidator` | Analisa código gerado antes da execução |
| `StaticValidator.validate(code, sig, backend)` → `StaticValidationResult` | Executar validação estática |
| `ForbiddenToken` | Padrão que não deve aparecer no código |

## `cfa.validation.signature`

| Nome | Descrição |
|------|-----------|
| `validate_signature_data(data)` → `SignatureValidationResult` | Validação estrutural de StateSignature |
| `unwrap_signature_data(data)` → `dict` | Aceita wrappers `{"signature": ...}` |

## `cfa.normalizer.base`

| Nome | Descrição |
|------|-----------|
| `IntentNormalizer` | Resolve intenção NL em `StateSignature` |
| `RuleBasedNormalizerBackend` | Backend determinístico baseado no catálogo |
| `MockNormalizerBackend` | Backend determinístico apenas para testes |
| `ConfirmationOrchestrator` | Escalonamento de confirmação baseado em risco |

## `cfa.normalizer.llm`

| Nome | Descrição |
|------|-----------|
| `LLMNormalizerBackend` | Normalização via LLM com modo estrito |
| `OpenAILMProvider` | Provider compatível com OpenAI |

## `cfa.audit.trail`

| Nome | Descrição |
|------|-----------|
| `AuditTrail` | Armazenamento de eventos com cadeia de hash |
| `AuditTrail.record(...)` → `AuditEvent` | Registrar um evento |
| `AuditTrail.verify_chain()` → `bool` | Verificar integridade da cadeia SHA-256 |
| `JsonLinesAuditStorage` | Backend de arquivo JSONL |

## `cfa.audit.context`

| Nome | Descrição |
|------|-----------|
| `ContextRegistry` | Modelo vivo do estado do ambiente |
| `ContextRegistry.get_environment_state()` → `dict` | Snapshot do estado atual |

## `cfa.storage`

| Nome | Descrição |
|------|-----------|
| `SqliteStorage(db_path)` | Armazenamento SQLite unificado para todos os dados CFA |
| `SqliteStorage.ensure_schema()` | Criar schema com migração automática |
| `SqliteStorage.audit_append(event)` | Registrar evento de auditoria |
| `SqliteStorage.execution_append(dict)` | Registrar execução para ciclo de vida |
| `SqliteStorage.skill_upsert(hash, data)` | Persistir estado de skill |

## `cfa.observability.promotion`

| Nome | Descrição |
|------|-----------|
| `PromotionEngine` | Gestão de ciclo de vida via IFo/IFs/IFg/IDI |
| `PromotionEngine.record_execution(record)` | Registrar execução para pontuação |
| `PromotionEngine.evaluate(hash)` → `(SkillRecord, IndexScores)` | Avaliar um skill |
| `PromotionPolicy` | Limiares: min_executions, ifo_threshold, ifs_threshold |

## `cfa.observability.indices`

| Nome | Descrição |
|------|-----------|
| `IndexCalculator` | Calcula IFo, IFs, IFg, IDI a partir de registros |
| `IndexScores` | ifo, ifs, ifg, idi + promotion_eligible, drift_detected |
| `ExecutionRecord` | Ponto de dados único de execução |

## `cfa.backends`

| Nome | Descrição |
|------|-----------|
| `BackendRegistry.singleton()` | Registry global (pyspark, sql, dbt) |
| `BackendRegistry.list()` → `list[str]` | Listar backends registrados |
| `BackendRegistry.register(name, factory)` | Registrar novo backend |
| `BackendAdapter` | Base abstrata para backends de codegen |
| `BackendCapabilities` | Flags + forbidden_tokens |

## `cfa.sandbox`

| Nome | Descrição |
|------|-----------|
| `SandboxRegistry.singleton()` | Registry global (mock, panic) |
| `SandboxBackend` | Backend de execução plugável |
| `MockSandboxBackend` | Simulação determinística para testes |
| `SandboxExecutor` | Orquestra execução do plano |

## `cfa.runtime`

| Nome | Descrição |
|------|-----------|
| `RuntimeGate` | Gate de governança para produção |
| `GateConfig` | Configuração: policy_bundle, sandbox, execute |
| `RuntimeGate.validate(intent)` → `GateResult` | Validação pré-execução |

## `cfa.testing`

| Nome | Descrição |
|------|-----------|
| `evaluate(intent, ...)` → `EvaluationResult` | Wrapper de conveniência para testes |
| `assert_passed(result)` | Afirma que avaliação passou |
| `assert_blocked(result)` | Afirma que avaliação foi bloqueada |

## `cfa.core.conditions`

| Nome | Descrição |
|------|-----------|
| `build_condition(name)` → `Callable` | Construir uma condição nomeada |
| `register_condition(name, factory)` | Registrar condição personalizada |
| `list_conditions()` → `list[str]` | Listar condições registradas |

## `cfa.config`

| Nome | Descrição |
|------|-----------|
| `CfaConfig.from_yaml(path)` → `CfaConfig` | Carregar configuração |
| `CfaConfig.discover()` → `CfaConfig | None` | Auto-descoberta do cfa.yaml |
