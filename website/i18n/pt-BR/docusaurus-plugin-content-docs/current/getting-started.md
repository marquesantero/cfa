---
sidebar_position: 2
---

# Primeiros Passos

Instale o CFA e execute sua primeira verificação de governança em menos de 5 minutos.

## Pré-requisitos

- Python 3.11 ou superior
- pip

## Instalação

```bash
pip install cfa-kernel
# ou diretamente do GitHub:
# pip install git+https://github.com/marquesantero/cfa.git
```

Funcionalidades opcionais:

```bash
pip install cfa-kernel[yaml]       # Policy bundles YAML
pip install cfa-kernel[llm]        # Normalização de intenção com LLM (OpenAI)
pip install cfa-kernel[otel]       # Tracing OpenTelemetry
pip install cfa-kernel[mcp]        # Protocolo servidor MCP
pip install cfa-kernel[all]        # Tudo
```

## Inicializar um projeto

```bash
cfa init
```

Cria `.cfa/` com:

```text
.cfa/
├── config.yaml              # Configuração CFA
├── catalog.json             # Catálogo de dados de exemplo
├── policies/
│   └── prod-v1.yaml         # Policy bundle de exemplo
└── .gitignore
```

## Sua primeira verificação

### Via linguagem natural

```bash
cfa evaluate "Juntar NFe com Clientes e persistir na Silver" --catalog .cfa/catalog.json
```

### Via contrato estruturado (recomendado para CI/API)

```bash
cfa policy check --signature signature.json --policy-bundle .cfa/policies/prod-v1.yaml --format json
```

### Com validação cruzada estrita

```bash
cfa policy check \
  --signature signature.json \
  --catalog .cfa/catalog.json \
  --policy-bundle .cfa/policies/prod-v1.yaml \
  --strict \
  --audit-log audit.jsonl \
  --exit-code
```

## Validando artefatos

```bash
# Validar um catálogo
cfa catalog validate .cfa/catalog.json --require-datasets --format json

# Validar um policy bundle
cfa policy validate .cfa/policies/prod-v1.yaml --format json

# Validar uma assinatura
cfa signature validate request.json --require-datasets --format json
```

Todos os comandos de validação retornam código de saída 1 em caso de falha — prontos para pipelines de CI.

## Trilha de auditoria

```bash
# Verificar integridade da cadeia
cfa audit verify --file audit.jsonl

# Mostrar eventos de uma intenção
cfa audit show --id <intent_id> --file audit.jsonl --format json
```

## Gestão de armazenamento

```bash
# Verificar estatísticas
cfa storage stats --db cfa.db

# Limpar registros mais antigos que a retenção
cfa storage cleanup --db cfa.db --retention 90

# Compactar banco SQLite
cfa storage vacuum --db cfa.db
```

## Usando a partir do Python

```python
from cfa.testing import evaluate, assert_passed

result = evaluate(
    "Juntar NFe com Clientes e persistir na Silver",
    catalog=MEU_CATALOGO,
    backend="pyspark",
)
assert_passed(result)
```

### Runtime gate

```python
from cfa.runtime import RuntimeGate, GateConfig

gate = RuntimeGate(
    config=GateConfig(policy_bundle="prod_v1.0"),
    catalog=CATALOGO_PRODUCAO,
)

# Validação pré-execução
result = gate.validate("agregar vendas com PII protegido")

# Decorator guard
@gate.guard("agregar vendas")
def meu_pipeline():
    ...
```

### Backend de armazenamento

```python
from cfa.storage import SqliteStorage

store = SqliteStorage("cfa.db")
store.ensure_schema()

# Registrar evento de auditoria
store.audit_append(event)

# Registrar execução para ciclo de vida
store.execution_append(record_dict)

# Consultar skills do ciclo de vida
skills = store.skill_load_all()
```

### Motor de políticas

```python
from cfa.policy.engine import PolicyEngine
from cfa.types import StateSignature

signature = StateSignature.from_dict(signature_dict)
engine = PolicyEngine(policy_bundle_version="prod-v1.0")
result = engine.evaluate(signature)
# result.action → approve / replan / block
```
