---
sidebar_position: 21
---

# Notas de Arquitetura

Questões em aberto e decisões de design para a maturação do CFA. Estas notas não são razões para descartar o CFA — são as questões que mais valem a pena debater.

---

## 1. Lacuna entre whitepaper e implementação

O whitepaper expressa um contrato arquitetural forte: formalização de intenção, execução governada, projeção de estado, semântica de falha parcial, evidência de ciclo de vida. A implementação já reflete grande parte dessa estrutura, mas a questão real é se os **invariantes são aplicados tão fortemente quanto o whitepaper implica**. Isso deve ser examinado módulo por módulo.

---

## 2. Dependência de metadados

O CFA pressupõe qualidade significativa de metadados: classificação de datasets, marcadores PII, metadados de partição, atualização do catálogo, contexto ambiental. Se essas entradas estiverem erradas, o sistema pode se tornar confiantemente errado de forma disciplinada. A arquitetura é tão boa quanto o estado e o catálogo dos quais depende.

---

## 3. Overhead vs. perfil de risco

O CFA introduz múltiplos estágios de decisão e validação. Isso cria clareza arquitetural, força de governança e melhor recuperabilidade — mas também latência, esforço de integração e carga cognitiva. A questão não resolvida: em quais contextos operacionais esse overhead se justifica pelo perfil de risco?

---

## 4. Modelo de concorrência

Se múltiplas requisições podem interpretar intenções sobrepostas, mirar o mesmo escopo e atualizar estado operacional compartilhado, a arquitetura deve definir como a corretude é preservada sob contenção. Sub-questões:
- O escopo de destino deve ser baseado em lock, fila ou versionamento?
- Como a revalidação deve funcionar sob mudança concorrente?
- Como é uma consistência aceitável?

---

## 5. Riqueza do contrato de merge-key

Atualmente, `merge_key_required` é um sinal booleano de que a semântica de merge importa. A arquitetura deveria evoluir para um contrato explícito mais rico para comportamento de merge, semântica de chave e garantias de escrita? Isso tornaria o contrato de execução mais sério, mas também mais exigente.

---

## 6. Modelagem de escopo de destino

Projeção de estado, ciclo de vida e concorrência dependem de quão claro é o modelo de escopo de destino. Questões-chave:
- O escopo de destino é em nível de dataset, partição ou contrato?
- Como os destinos derivados devem ser nomeados e versionados?
- Como escritas futuras devem raciocinar sobre projeções anteriores?

---

## 7. Evolução de pacotes de políticas

A política em si tem um ciclo de vida. Questões em aberto:
- Como as políticas devem ser versionadas e que garantias de compatibilidade devem existir?
- Quando uma mudança de política deve disparar reavaliação ou demotion?
- Como as equipes evitam que a governança se torne burocrática?

---

## 8. Limites dos adaptadores de runtime

O caminho de runtime atual é orientado a PySpark. O que é genérico no CFA e o que é específico do runtime? Adaptadores futuros candidatos: engines SQL, execução nativa de warehouse, processamento de streaming, runtimes de orquestração não-dados.

---

## 9. Escolha de linguagem de longo prazo

Python é excelente para legibilidade, alinhamento com ferramentas de dados e experimentação. É mais fraco para garantias fortes em tempo de compilação, aplicação profunda de invariantes e algumas classes de isolamento de runtime. O núcleo de longo prazo deveria permanecer inteiramente em Python?

---

## 10. Validação de mercado

Qual é o menor caso de uso real que prova que o CFA cria valor para alguém fora do projeto? O candidato mais forte atualmente é: `cfa.policy` em um pipeline orquestrado existente antes da execução. Essa cunha pode testar fricção de adoção, clareza conceitual, valor real e usabilidade externa.

---

## 11. Critérios de prova significativos

Uma boa prova não seria outra demo interna. Evidência mais forte: uma equipe externa adota uma fatia pequena do CFA, consegue explicar o benefício de forma simples, o esforço de integração é aceitável e eles encontram fricção real e ainda assim veem valor.

---

## 12. Medição de prontidão para produção

Além de listar áreas "fortes" e "fracas", como o projeto deve medir quais partes estão prontas para produção? Critérios possíveis: força de aplicação de invariantes, observabilidade operacional, complexidade de integração, usabilidade externa, semântica de falha, maturidade de runtime.

---

## 13. Próximos marcos concretos

- **Primeira adoção externa**: alguém fora do projeto usa `cfa.policy` em um pipeline real e reporta de volta
- **Endurecimento de invariantes**: verificar sistematicamente quais invariantes do whitepaper são aplicados em runtime vs. apenas por convenção
- **Limite do adaptador de runtime**: definir claramente o que é CFA genérico e o que é específico do PySpark, para que um segundo adaptador possa ser adicionado sem reescrever o kernel
- **Decisão do modelo de concorrência**: escolher e implementar isolamento de escopo de destino baseado em lock, fila ou versionamento
