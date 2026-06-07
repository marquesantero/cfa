---
sidebar_position: 20
---

# Perguntas Frequentes

## Qual problema o CFA resolve?

CFA resolve a lacuna de governança em sistemas de dados com IA: quem decide o que um agente de IA ou pipeline de dados pode fazer, sob quais restrições e com qual evidência? Em vez de "qual ferramenta devo chamar?", o CFA pergunta "qual transição de estado está sendo solicitada, sob quais restrições, e pode ser executada com segurança?"

## Como o CFA se diferencia de Great Expectations ou Soda?

Great Expectations e Soda validam **qualidade de dados** — verificam se os dados atendem a expectativas. O CFA valida **governança de execução** — verifica se uma intenção (o que você quer fazer) está em conformidade com a política antes da execução. O CFA opera no nível da intenção, não no nível do dado.

## Como o CFA se diferencia do ACS (Agent Control Specification)?

ACS é um motor de política para agentes de IA — baseado em YAML, licença MIT, apoiado por KPMG/IBM/Zscaler. Como o CFA, atua como gate de governança antes das ações do agente. Diferenças principais:

| Aspecto | ACS | CFA |
|--------|-----|-----|
| Modelo de estado | Stateless (allow/deny) | Stateful (StateSignature + ContextRegistry) |
| Decisão | Binária (pass/fail) | Ternária (approve/replan/block) |
| Trilha de auditoria | Logs padrão | Cadeia hash SHA-256 (tamper-evident) |
| Ciclo de vida | Não possui | Índices IFo/IFs/IFg/IDI |
| Projeção de estado | Não | Sim (pós-execução) |
| Alvos de backend | Ações de agentes | Pipelines de dados + agentes (PySpark, SQL, dbt) |

ACS se destaca em segurança de agentes em ambientes corporativos. CFA adiciona governança stateful para agentes e pipelines de dados com auditabilidade criptográfica.

## O CFA precisa de LLM?

Não. O normalizador baseado em regras (`rule_based`) funciona sem qualquer LLM, usando correspondência de palavras-chave contra o catálogo. O LLM é opcional via `--normalizer openai` ou `--normalizer deepseek` e no modo estrito (`--llm-strict`) valida a saída contra o catálogo.

## O CFA substitui Airflow, dbt ou Dagster?

Não. O CFA é uma camada de governança que funciona **junto** com orquestradores e ferramentas de transformação. É um gate de decisão que você coloca **antes** da execução.

## O CFA suporta bancos de dados específicos?

O CFA é agnóstico de backend. Os backends de geração de código suportam PySpark (Delta Lake), SQL ANSI (Snowflake, BigQuery, Postgres, DuckDB) e dbt. Novos backends podem ser registrados via `BackendRegistry`.

## Os dados de auditoria são realmente imutáveis?

A trilha de auditoria usa uma cadeia de hash SHA-256 — cada evento inclui o hash do evento anterior. A verificação detecta adulteração, exclusão ou reordenação de eventos. O termo correto é **tamper-evident** (evidência de adulteração), não imutável absoluto.

## O CFA funciona em ambientes multi-usuário?

Atualmente o CFA é single-process. O armazenamento SQLite usa WAL mode para leitura concorrente. Ambientes multi-usuário exigiriam um backend de banco de dados compartilhado.

## Como posso contribuir?

Veja [CONTRIBUTING.md](https://github.com/marquesantero/cfa/blob/main/CONTRIBUTING.md) no repositório.
