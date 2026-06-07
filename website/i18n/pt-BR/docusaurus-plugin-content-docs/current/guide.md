---
sidebar_position: 4
---

# Guia de Uso

Fluxo completo de trabalho, da intenção à auditoria usando CFA.

## Níveis de Adoção

CFA suporta adoção progressiva. Você não precisa adotar tudo de uma vez.

| Nível | O que você usa | O que você obtém |
|-------|-------------|--------------|
| Apenas governança | `PolicyEngine` + `StateSignature` | Gate de decisão formal antes da execução |
| Governança + Resolução | Acima + `IntentNormalizer` | Solicitações em linguagem natural convertidas em contratos |
| Kernel parcial | Acima + codegen + sandbox | Validação, execução controlada e projeção de estado |
| Kernel completo | `KernelOrchestrator` | Fluxo completo de execução governada |

## Fluxo de Trabalho Típico

1. **Definir catálogo**: Criar `catalog.json` com datasets, classificações e colunas PII
2. **Definir políticas**: Criar `policies/prod-v1.yaml` com regras declarativas
3. **Inicializar projeto**: `cfa init`
4. **Executar intenções**: `cfa evaluate` ou `cfa policy check`
5. **Auditar decisões**: `cfa audit verify`
6. **Gerenciar ciclo de vida**: `cfa lifecycle evaluate`
7. **Limpar dados antigos**: `cfa storage cleanup`

## Superfícies de Uso

| Superfície | Para | Exemplo |
|---------|-----|---------|
| `cfa` CLI | Todos | `cfa evaluate "intent" --exit-code` |
| `cfa policy check` | CI/API | `cfa policy check --signature sig.json` |
| `cfa.testing` | Testes pytest | `evaluate("intent", catalog=catalog)` |
| `cfa.runtime` | Produção | `RuntimeGate` como decorator/context-manager |
| `cfa.mcp` | Agentes IA | Servidor MCP para ChatGPT, Claude, Copilot |
| `cfa.adapters` | Frameworks | LangGraph, OpenAI Agents, CrewAI, AutoGen, DSPy |
