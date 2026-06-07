---
sidebar_position: 21
---

# Notas de Arquitetura

Questões em aberto e decisões de design para amadurecimento do CFA.

## 1. Lacuna entre whitepaper e implementação

O whitepaper expressa um contrato arquitetural forte: formalização de intenção, execução governada, projeção de estado, semântica de falha parcial, evidência de ciclo de vida. A implementação já reflete grande parte dessa estrutura, mas a questão real é se os **invariantes são aplicados tão fortemente quanto o whitepaper implica**.

## 2. Dependência de metadados

CFA assume qualidade significativa de metadados: classificação de datasets, marcadores PII, metadados de partição, atualização do catálogo, contexto ambiental. Se essas entradas estiverem erradas, o sistema pode se tornar confiantemente errado de forma disciplinada.

## 3. Overhead vs perfil de risco

CFA introduz múltiplos estágios de decisão e validação. Isso cria clareza arquitetural, força de governança e melhor recuperabilidade — mas também latência, esforço de integração e carga cognitiva.

## 4. Modelo de concorrência

Se múltiplas requisições podem interpretar intenções sobrepostas, mirar o mesmo escopo e atualizar estado operacional compartilhado, a arquitetura precisa definir como a corretude é preservada sob contenção.

## 5. Evolução de policy bundles

Política possui ciclo de vida. Questões em aberto: como versionar e quais garantias de compatibilidade devem existir, quando mudanças de política devem disparar reavaliação ou demotion, como evitar que governança se torne burocrática.

## 6. Escolha de linguagem de longo prazo

Python é excelente para legibilidade, alinhamento com ferramentas de dados e experimentação. É mais fraco para garantias fortes em tempo de compilação e algumas classes de isolamento de runtime.

## 7. Validação de mercado

Qual é o menor caso de uso real que prova que CFA cria valor para alguém fora do projeto? O candidato mais forte atual é: `cfa.governance` em um pipeline orquestrado existente antes da execução.
