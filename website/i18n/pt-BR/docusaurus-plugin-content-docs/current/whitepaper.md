---
sidebar_position: 3
---

# Notas de arquitetura do CFA (Whitepaper)

Contextual Flux Architecture — Gate de governança pré-execução para agentes de IA e sistemas de dados.

> Este documento é descritivo, não prescritivo. Captura como o kernel está
> estruturado hoje; as páginas voltadas para o usuário usam linguagem
> operacional. Leia esta seção se quiser entender as decisões internas.

## 1. Introdução

CFA é um **kernel de governança** que insere uma camada formal de decisão entre a intenção do usuário e a execução operacional. Em vez de ir diretamente do prompt à ação, o CFA exige que cada solicitação de execução seja formalizada, validada contra políticas declarativas, planejada, gerada, executada em sandbox e auditada antes que qualquer efeito colateral ocorra.

O kernel é organizado em cinco fases:

1. **Formalizar** — resolver uma intenção em linguagem natural em uma `StateSignature` tipada.
2. **Governar** — avaliar a assinatura contra regras de política declarativas via `PolicyEngine`.
3. **Planejar e Gerar** — produzir código determinístico a partir de planos aprovados.
4. **Executar e Validar** — rodar em sandbox isolado; validar métricas de runtime.
5. **Estado e Auditoria** — projetar estado no `ContextRegistry`; registrar eventos de auditoria imutáveis; computar índices de ciclo de vida.

## 2. Invariantes

1. **I1 — Tipagem**: Toda intenção deve ser formalizada como `StateSignature` antes da execução
2. **I2 — Governança**: Nenhuma execução sem aprovação do `PolicyEngine`
3. **I3 — Contexto**: `ContextRegistry` deve ser consultado antes de cada intenção
4. **I4 — Projeção**: `ContextRegistry` deve ser atualizado após cada execução
5. **I5 — Auditoria**: Todo evento de decisão é registrado em trilha imutável
6. **I6 — Segurança**: Código passa por validação estática antes da execução
7. **I7 — Reprodutibilidade**: Cada execução está vinculada a versões de catálogo e política
8. **I8 — Evidência**: Decisões de ciclo de vida são baseadas em índices quantitativos

## 3. Pipeline de Execução

O pipeline completo executa 5 fases canônicas:

1. **Formalize**: NL → contrato tipado `StateSignature` → confirmação
2. **Govern**: Verificação de política com ciclo REPLAN (approve / replan / block)
3. **Generate**: Plano de execução + código + validação estática
4. **Execute**: Sandbox + validação de runtime
5. **Validate**: Projeção de estado + auditoria + ciclo de vida

## 4. Índices de Ciclo de Vida

Quatro índices quantitativos rastreiam a saúde de cada pipeline:

- **IFo** (Fluidez Operacional): latência normalizada × custo × estabilidade
- **IFs** (Fidelidade Semântica): aderência ao schema × ausência de drift × preservação de invariantes
- **IFg** (Governança): binário — 1.0 ou falha sistêmica
- **IDI** (Intent Drift): 1 - (execuções replanejadas / total)

## 5. Modelo de Ameaças

CFA protege contra:
- Escrita de PII bruto em camadas protegidas
- Full scan sem filtro de partição
- Escrita sem merge key em Silver/Gold
- Custo acima do orçamento
- Deriva silenciosa de schema
- Execução não autorizada por agentes de IA
