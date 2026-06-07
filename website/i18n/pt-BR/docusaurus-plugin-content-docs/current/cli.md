---
sidebar_position: 10
---

# Referência CLI

CFA possui uma CLI sem dependências externas construída com `argparse`.

## Governança

### `cfa evaluate`

Executa uma intenção pelo pipeline completo de governança.

```bash
cfa evaluate <intent> [opções]

Opções:
  --config PATH             Caminho para arquivo cfa.yaml
  --catalog, -c PATH        Arquivo de catálogo JSON/YAML
  --policy-bundle, -p VER   Versão ou caminho do policy bundle
  --backend, -b NAME        Backend de geração de código (pyspark, sql, dbt)
  --format, -f FORMAT       Formato de saída: table, json, summary
  --strict                  Bloquear intenções ambíguas
  --exit-code               Sair com código 1 se bloqueado
  --normalizer NAME         Backend normalizador (auto, rule_based, mock, openai, deepseek, llm)
  --llm-strict              Exigir que saída do LLM corresponda exatamente ao catálogo
```

### `cfa policy check`

Avalia uma StateSignature contra um policy bundle (sem linguagem natural).

```bash
cfa policy check --signature sig.json [opções]

Opções:
  --config PATH             Caminho para arquivo cfa.yaml
  --catalog PATH            Caminho do catálogo (habilita catalog_hash + validação cruzada)
  --policy-bundle, -p VER   Versão ou caminho do policy bundle
  --format, -f FORMAT       Saída: summary, json
  --exit-code               Sair com 1 quando a ação não for approve
  --strict                  Validar datasets da assinatura contra o catálogo
  --require-datasets        Exigir pelo menos um dataset
  --audit-log FILE          Anexar decisão ao arquivo JSONL de auditoria
```

## Validação (pronto para CI)

### `cfa catalog validate`

```bash
cfa catalog validate catalog.json --require-datasets --format json
```

### `cfa signature validate`

```bash
cfa signature validate request.json --require-datasets --format json
```

### `cfa policy validate`

```bash
cfa policy validate policies/prod.yaml --format json
```

Todos retornam JSON com `valid`, `issue_count` e `issues[]`. Código de saída 1 se inválido.

### `cfa validate`

Valida uma intenção contra uma especificação de comportamento.

```bash
cfa validate --spec governanca_fiscal.yaml --intent "agregar vendas" --exit-code
```

## Regras de política

```bash
cfa rules list                          # Listar todas as regras ativas
cfa rules explain CODIGO_FAULT          # Explicar uma fault específica
```

## Auditoria

```bash
cfa audit show --id INTENT_ID --file audit.jsonl --format json
cfa audit verify --file audit.jsonl
```

## Gestão de armazenamento

```bash
cfa storage stats --db cfa.db --format json
cfa storage cleanup --db cfa.db --retention 90
cfa storage cleanup --db cfa.db --before 2025-01-01T00:00:00
cfa storage vacuum --db cfa.db

# Backend JSONL (zero dependências)
cfa storage stats --dir ./dados_auditoria/
cfa storage cleanup --dir ./dados_auditoria/ --retention 90
```

## Ciclo de vida

```bash
cfa lifecycle evaluate --db cfa.db --window 30 --format json
cfa lifecycle list --db cfa.db --format json
```

## Projeto

```bash
cfa init                                # Inicializar projeto (.cfa/)
cfa init --dir ./meu-projeto            # Diretório personalizado
cfa status                              # Saúde do projeto + estatísticas
cfa status --config .cfa/config.yaml    # Caminho explícito do config
cfa status --format json                # Saída para máquina
```

## Backends

```bash
cfa backend list                        # Listar backends registrados (pyspark, sql, dbt)
```

## Taxonomia

```bash
cfa taxonomy generate --spec ARQUIVO    # Gerar taxonomia da especificação
cfa taxonomy test-intents --spec ARQUIVO # Gerar intenções de teste
```

## Relatórios

```bash
cfa report execution --intent "..." --output relatorio.html
cfa report audit --intent-id ID --output auditoria.html
cfa report lifecycle --period 90 --audit-file audit.jsonl --output dashboard.html
cfa report compliance --audit-file audit.jsonl --output compliance.html
cfa report dashboard --period 90 --audit-file audit.jsonl --output dashboard.html
```

## Servir

```bash
cfa serve --port 8765 --metrics-port 9090
```

Serve endpoints `/health` e `/metrics`. Sem dados sintéticos — usa apenas métricas reais.
