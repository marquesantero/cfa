---
sidebar_position: 13
---

# Registro de Backends

CFA suporta backends de geração de código plugáveis via sistema de registro. Cada backend gera código governado determinístico a partir de um `ExecutionPlan` aprovado.

## Backends Integrados

| Backend | Linguagem | Merge | Anonimização | Sobrescrita de Partição | Tokens Proibidos |
|---------|----------|-------|-------------|------------------------|-----------------|
| `pyspark` | PySpark + Delta Lake | ✅ | ✅ (sha256, drop, tokenize, mask) | ✅ | `.collect()`, `.toPandas()`, `crossJoin()`, `import os`, `import subprocess` |
| `sql` | ANSI SQL | ✅ (MERGE INTO) | ✅ (sha256, drop, md5) | ✅ (INSERT OVERWRITE) | `DROP TABLE`, `TRUNCATE`, `DELETE FROM`, `ALTER TABLE` |
| `dbt` | modelos dbt + schema.yml | ✅ (unique_key) | ✅ (sha256, drop) | ✅ (partition_by) | `DROP TABLE`, `TRUNCATE`, `DELETE FROM` |

Cada backend declara seus próprios tokens proibidos via `BackendCapabilities.forbidden_tokens`. O `StaticValidator` consulta o backend — sem lista centralizada.

## Listando backends

```bash
cfa backend list
```

```python
from cfa.backends import BackendRegistry

for name in BackendRegistry.singleton().list():
    print(name)
# dbt, pyspark, sql
```

## Backend PySpark

```python
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.getOrCreate()

df_nfe = spark.read.format("delta").load("nfe")
df_nfe = df_nfe.filter(F.col("processing_date") >= F.lit("{{date_param}}"))

df_clientes = df_clientes.withColumn("cpf_hash", F.sha2(F.col("cpf").cast("string"), 256))
df_clientes = df_clientes.drop("cpf")

df_joined = df_nfe.join(df_clientes, on=["nfe_id"], how="inner")

target_table.alias("t").merge(
    df_joined.alias("s"),
    "t.nfe_id = s.nfe_id"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
```

## Backend SQL

```sql
SELECT * FROM "nfe"
WHERE "processing_date" >= '{date_param}'

SELECT nfe_2.*, clien_2.*
FROM "nfe" nfe_2
INNER JOIN "clientes" clien_2
  ON nfe_2."nfe_id" = clien_2."cliente_id"

MERGE INTO "silver_table" AS target
USING (joined_cte) AS source
  ON target."nfe_id" = source."nfe_id"
WHEN MATCHED THEN UPDATE SET "nfe_id" = source."nfe_id"
WHEN NOT MATCHED THEN INSERT (*)
```

## Backend dbt

```sql
{{ config(
    materialized='table',
    partition_by={'field': ['processing_date'], 'data_type': 'date'},
    unique_key=['nfe_id'],
) }}

SELECT * FROM {{ ref('nfe') }}
WHERE "processing_date" >= '{{ var("date_param") }}'
```

Com `schema.yml` gerado automaticamente:

```yaml
version: 2
models:
  - name: silver_fiscal_merge
    columns:
      - name: nfe_id
        tests:
          - not_null
          - unique
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - nfe_id
            - processing_date
```

## Interface BackendAdapter

```python
from cfa.backends import BackendAdapter, BackendCapabilities
from cfa.validation.static import ForbiddenToken
from cfa.types import FaultSeverity

class MeuBackend(BackendAdapter):
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_name="meu_backend",
            supports_merge=True,
            forbidden_tokens=[
                ForbiddenToken("padrao_perigoso", "STATIC_PERIGO",
                               FaultSeverity.CRITICAL, "Padrão perigoso detectado."),
            ],
        )

    def generate(self, plan: ExecutionPlan) -> GeneratedCode:
        ...
```

## Registrando um Backend

```python
from cfa.backends import BackendRegistry

BackendRegistry.singleton().register("meu_backend", lambda: MeuBackend())
```
