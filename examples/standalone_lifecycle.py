"""
cfa.lifecycle -- Uso standalone
================================
Monitora e promove/demove intencoes baseado em metricas.
Funciona sobre qualquer sistema que produza metricas de execucao.

Caso de uso:
  Voce tem pipelines que rodam diariamente.
  Quer saber quais sao estaveis, quais estao degradando,
  e quais deveriam ser "aposentados".

  Antes:
    pipeline roda todo dia -> ninguem sabe se esta bom ou ruim

  Depois:
    engine.record_execution(metricas_do_dia)
    skill, scores = engine.evaluate(pipeline_hash)
    if skill.state == "watchlist":
        alerta("Pipeline degradando!")
"""

from datetime import timedelta, timezone, datetime

from cfa.lifecycle import (
    PromotionEngine,
    PromotionPolicy,
    ExecutionRecord,
    IndexCalculator,
    SkillState,
)

now = datetime.now(timezone.utc)

# ── 1. Configurar engine ────────────────────────────────────────────────────

engine = PromotionEngine(
    policy=PromotionPolicy(
        min_executions=3,            # 3 execucoes para promover
        evaluation_window_days=30,   # janela de 30 dias
        ifo_threshold=0.75,          # fluidity operacional minima
        ifs_threshold=0.90,          # fidelidade semantica minima
    ),
)

# ── 2. Registrar execucoes (simula 5 dias de pipeline) ──────────────────────

pipeline_hash = "fiscal_reconciliation_silver_abc123"

for i in range(5):
    engine.record_execution(ExecutionRecord(
        signature_hash=pipeline_hash,
        timestamp=now - timedelta(days=5 - i),
        success=True,
        cost_dbu=5.0,
        duration_seconds=30.0,
    ))

# ── 3. Avaliar ──────────────────────────────────────────────────────────────

skill, scores = engine.evaluate(pipeline_hash)

print(f"Pipeline: {pipeline_hash[:20]}...")
print(f"Estado:   {skill.state.value}")
print(f"IFo:      {scores.ifo:.2f}  (fluidity operacional)")
print(f"IFs:      {scores.ifs:.2f}  (fidelidade semantica)")
print(f"IFg:      {scores.ifg:.0f}     (governanca - binario)")
print(f"IDI:      {scores.idi:.2f}  (drift index)")
print(f"Elegivel: {scores.promotion_eligible}")

# ── 4. Simular degradacao ───────────────────────────────────────────────────

print("\n--- Simulando drift (replanning frequente) ---")
for i in range(8):
    engine.record_execution(ExecutionRecord(
        signature_hash=pipeline_hash,
        timestamp=now - timedelta(hours=i),
        success=True,
        replanned=True,  # precisou de replanejamento
        cost_dbu=5.0,
        duration_seconds=30.0,
    ))

skill, scores = engine.evaluate(pipeline_hash)
print(f"Estado:   {skill.state.value}")
print(f"IDI:      {scores.idi:.2f}")
print(f"Drift:    {scores.drift_detected}")
print(f"Severo:   {scores.severe_drift}")

# ── 5. Verificar historico ──────────────────────────────────────────────────

print("\nHistorico de transicoes:")
for entry in skill.history:
    print(f"  {entry['from']} -> {entry['to']}: {entry['reason']}")

# ── 6. Usar indices standalone (sem engine) ─────────────────────────────────

print("\n--- IndexCalculator standalone ---")
calc = IndexCalculator(window_days=7)
records = [
    ExecutionRecord(
        signature_hash="outro_pipeline",
        timestamp=now - timedelta(days=i),
        success=True,
        cost_dbu=2.0,
        duration_seconds=15.0,
    )
    for i in range(10)
]
scores = calc.compute("outro_pipeline", records)
print(f"IFo={scores.ifo:.2f} IFs={scores.ifs:.2f} IFg={scores.ifg:.0f} IDI={scores.idi:.2f}")
