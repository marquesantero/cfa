# CFA Strategic Roadmap

## 0. Pre-flight Checks

- [x] 0.1 Run `uv run ruff check src/` — zero warnings
- [x] 0.2 Run `uv run pytest tests -q` — 534/534 passed
- [x] 0.3 Verify `README.md`, `website/docs/`, `website/i18n/` consistent with v1.0
- [x] 0.4 Verify `pyproject.toml` version, classifiers, deps correct
- [x] 0.5 Verify `.github/workflows/ci.yml` passes on push
- [x] 0.6 Verify `.github/workflows/deploy-pypi.yml` ready
- [x] 0.7 Verify `.github/workflows/deploy-docs.yml` deploys to gh-pages
- [x] 0.8 Write `SECURITY.md` — threat model (MCP injection, audit chain replay attacks, YAML parser fuzzing)
- [x] 0.9 Define release contingency plan

**Contingency plan**: Hotfix → branch `hotfix-1.0.x` → cherry-pick → bump patch → release.
Critical bug → GitHub Issue + Discord announcement + `git revert` as fallback.
Nuclear option: `pip install cfa-kernel!=<broken_version>` guidance + yank via PyPI.

- [x] 0.10 Run `pip-audit` and `safety check` — zero critical vulnerabilities in CFA core (41 in dev deps, none direct)

---

## 1. API Freeze — v1.0 Stable Contracts (Week 1-2)

### 1.1 Define the public API surface

- [x] 1.1.1 Audit `src/cfa/__init__.py` — decide what is top-level vs submodule
- [x] 1.1.2 Freeze `StateSignature` constructor (required fields, defaults, types)
- [x] 1.1.3 Freeze `PolicyEngine` constructor + `evaluate()` signature
- [x] 1.1.4 Freeze `PolicyResult` fields (action, faults, reasoning, etc.)
- [x] 1.1.5 Freeze `RuntimeGate` constructor + `validate()`, `guard()`, `scope()`
- [x] 1.1.6 Freeze `GateConfig`, `GateResult` fields
- [x] 1.1.7 Freeze `KernelConfig` fields
- [x] 1.1.8 Freeze `KernelOrchestrator` constructor + `process()`
- [x] 1.1.9 Freeze `KernelResult` fields
- [x] 1.1.10 Freeze `AuditTrail` constructor + `record()`, `verify_chain()`, `events`
- [x] 1.1.11 Freeze `OpenAILMProvider` + `LLMNormalizerBackend` (LLM surface)

**Done**: Added `PolicyResult` to `cfa.policy` lazy loader. Added `KernelResult` to `cfa.core` lazy loader. MCP public API is `serve()`.

### 1.2 Deprecate / hide internal-only modules

- [x] 1.2.1 Audit `core/phases/runner.py` — internal, should not be public
- [x] 1.2.2 Audit `core/planner.py`, `core/codegen.py` — internal helpers
- [x] 1.2.3 Audit `execution/*.py` — sandbox internals
- [x] 1.2.4 Mark all internal modules with header comment
- [ ] 1.2.5 Document public vs internal in `api.md`

### 1.3 v1.0 release

- [x] 1.3.1 Bump version to `1.0.0` everywhere
- [x] 1.3.2 Update `README.md` — remove alpha warnings, emphasize stability
- [x] 1.3.3 Update `website/docs/intro.md` — "production ready" language
- [x] 1.3.4 Write changelog (v0.1.0 → v1.0.0 highlights)
- [x] 1.3.5 Tag `v1.0.0` — build `cfa_kernel-1.0.0.tar.gz` + `.whl` in dist/
- [x] 1.3.6 Publish to PyPI
- [ ] 1.3.7 Write announcement blog post (Medium/Dev.to + website blog)

---

## 2. MCP Server — Production-Ready (Week 1-2, parallel)

### 2.1 Hardening

- [x] 2.1.1 Add authentication (API key / token) — `CFA_MCP_API_KEY` env var
- [x] 2.1.2 Add rate limiting per tool — token bucket, `CFA_MCP_RATE_LIMIT` env var
- [ ] 2.1.3 Add request/response logging to audit trail
- [x] 2.1.4 Add health check endpoint — `ping` already supported
- [x] 2.1.5 Add tool: `cfa_verify_chain` — already covered by `cfa_audit_check`
- [x] 2.1.6 Add tool: `cfa_lifecycle_status` — expose IFo/IFs/IFg/IDI
- [x] 2.1.7 Add tool: `cfa_compliance_check` — evaluate intent against bundle
- [ ] 2.1.8 Define SLOs: tool call latency p99 < 500ms, uptime > 99%
- [ ] 2.1.9 Load test: 100 req/s sustained for 10 minutes
- [ ] 2.1.10 Fuzz test MCP tool inputs (property-based testing with Hypothesis)
- [ ] 2.1.11 Test with Claude Desktop, Cursor, Windsurf

### 2.2 Distribution

- [ ] 2.2.1 Package MCP server as standalone entry point (`cfa-mcp` or `uvx cfa`)
- [ ] 2.2.2 Write install guide for Claude Desktop config JSON
- [ ] 2.2.3 Submit to Smithery marketplace
- [ ] 2.2.4 Submit to Glama marketplace
- [ ] 2.2.5 Submit to mcp.run marketplace
- [ ] 2.2.6 Write blog post: "CFA MCP: Governance as Native Tool for AI Agents"

### 2.3 Documentation

- [ ] 2.3.1 Update `website/docs/mcp-server.md` with auth + all tools
- [ ] 2.3.2 Add MCP quickstart video (2 min)
- [ ] 2.3.3 Add "CFA + Claude" end-to-end example

---

## 3. Developer Experience — `cfa init --template` (Week 3)

### 3.1 Template system

- [x] 3.1.1 Design template directory structure (`cfa/templates/`)
- [x] 3.1.2 Implement `cfa init --template <name>` CLI command
- [x] 3.1.3 Template: `fastapi-cfa` — FastAPI + RuntimeGate guard
- [x] 3.1.4 Template: `langgraph-cfa` — LangGraph agent + cfa_guard
- [x] 3.1.5 Template: `dbt-cfa` — dbt models + CFA validation step
- [x] 3.1.6 Template: `mcp-cfa` — MCP server skeleton with CFA tools
- [x] 3.1.7 Template: `streaming-placeholder` — Structured Streaming stub with explicit README: "Experimental — streaming governance coming in v1.3"

### 3.2 Onboarding flow

- [x] 3.2.1 `cfa init` without args = classic init (backward compatible)
- [x] 3.2.2 `cfa init --list` shows available templates
- [x] 3.2.3 Each template generates: cfa.yaml, catalog stub, policy stub, framework code, test
- [x] 3.2.4 Generated project has cfa.yaml + catalog.json + policy.yaml out of the box

### 3.3 Documentation

- [ ] 3.3.1 Update `website/docs/getting-started.md` with templates
- [ ] 3.3.2 Write "5 Minute Quickstart" with template
- [ ] 3.3.3 Write "From Zero to Governed Pipeline" tutorial

---

## 4. Documentation as Product (Week 3-4)

### 4.1 Quickstart

- [x] 4.1.1 Write 5-minute quickstart with templates, LLM, MCP sections
- [ ] 4.1.2 Embed on website landing page above the fold
- [ ] 4.1.3 Test quickstart on clean Ubuntu, macOS, Windows (PowerShell)

### 4.2 Tutorials

- [ ] 4.2.1 "Governed PySpark Pipeline" end-to-end tutorial
- [ ] 4.2.2 "LLM Agent with CFA Guardrails" tutorial
- [ ] 4.2.3 "Multi-Agent Governance" tutorial (3+ agents)
- [ ] 4.2.4 "Compliance Passport" tutorial (EU AI Act → CFA rules)

### 4.3 Visuals

- [ ] 4.3.1 Architecture diagram (SVG, light + dark mode)
- [ ] 4.3.2 5-phase pipeline flowchart
- [ ] 4.3.3 Decision tree: APPROVE vs REPLAN vs BLOCK
- [ ] 4.3.4 Hero animation / logo

### 4.4 Voice & Tone

- [ ] 4.4.1 Define writing guidelines (professional, not academic; confident, not salesy)
- [ ] 4.4.2 Audit all docs for consistency
- [ ] 4.4.3 Sync EN and PT-BR docs for all critical pages

### 4.5 PT-BR Critical Sync (MANDATORY — Brazilian market is primary target)

- [x] 4.5.1 Rewrite `guide.md` PT-BR (39 -> full translation matching EN)
- [x] 4.5.2 Complete `architecture-notes.md` PT-BR (7 missing sections)
- [x] 4.5.3 Complete `policy-bundles.md` PT-BR (3 missing conditions + programmatic section)
- [x] 4.5.4 Complete `behavior-spec.md` PT-BR (add Python code examples)
- [x] 4.5.5 Complete `reporting.md` PT-BR (add `generate_report()` API examples)
- [ ] 4.5.6 Verify LGPD terminology consistency across all PT-BR docs

---

## 5. Compliance Pack — EU AI Act + LGPD (Week 4)

### 5.1 EU AI Act mapping

- [ ] 5.1.1 Read EU AI Act articles relevant to data/AI governance
- [ ] 5.1.2 Map Article 9 (risk management) → CFA policy rules
- [ ] 5.1.3 Map Article 10 (data governance) → CFA catalog constraints
- [ ] 5.1.4 Map Article 12 (record-keeping) → CFA audit trail
- [ ] 5.1.5 Map Article 13 (transparency) → CFA reporting
- [ ] 5.1.6 Map Article 15 (accuracy, robustness) → CFA validation
- [ ] 5.1.7 Map Article 17 (quality management) → CFA lifecycle (IFo/IFs/IFg/IDI)
- [ ] 5.1.8 Create `policies/eu-ai-act-v1.yaml` policy bundle

### 5.2 LGPD mapping

- [ ] 5.2.1 Map Art. 6 (consent/legitimate interest) → CFA domain constraints
- [ ] 5.2.2 Map Art. 11-13 (anonymization, pseudonymization) → CFA PII rules
- [ ] 5.2.3 Map Art. 16 (security) → CFA audit + hash chain
- [ ] 5.2.4 Map Art. 18 (portability) → CFA data contracts
- [ ] 5.2.5 Map Art. 37-38 (DPO, impact assessment) → CFA reports
- [ ] 5.2.6 Create `policies/lgpd-v1.yaml` policy bundle

### 5.3 Compliance reporting

- [ ] 5.3.1 Generate compliance report: `cfa report compliance --bundle eu-ai-act-v1`
- [ ] 5.3.2 Export audit trail as signed PDF (for DPO/auditor)
- [ ] 5.3.3 Document: "How CFA Demonstrates EU AI Act Compliance" (white paper)

---

## 6. Observability — OTel + Prometheus + Grafana (Week 5)

### 6.1 OpenTelemetry integration

- [ ] 6.1.1 Export spans for: normalize, evaluate, generate, execute, validate phases
- [ ] 6.1.2 Export span attributes: intent, domain, target_layer, decision, duration_ms
- [ ] 6.1.3 Export metrics: evaluations_total, blocks_total, replans_total, latency_p99
- [ ] 6.1.4 Export traces: end-to-end trace_id from intent → decision

### 6.2 Dashboards

- [ ] 6.2.1 Grafana dashboard JSON: governance overview (decisions pie, latency heatmap)
- [ ] 6.2.2 Grafana dashboard JSON: lifecycle indices over time (IFo/IFs/IFg/IDI)
- [ ] 6.2.3 Grafana dashboard JSON: compliance posture (rules fired, remediations)
- [ ] 6.2.4 Add to docs: "Monitoring CFA with Grafana"

### 6.3 Benchmarks

- [ ] 6.3.1 Measure `PolicyEngine.evaluate()` latency (p50, p95, p99)
- [ ] 6.3.2 Measure `KernelOrchestrator.process()` end-to-end latency
- [ ] 6.3.3 Measure throughput (evaluations/second) on commodity hardware
- [ ] 6.3.4 Measure SQLite storage performance (writes/second, query latency)
- [ ] 6.3.5 Publish benchmark page on website

---

## 7. Integration with Catalogs (Week 6-7)

### 7.1 DataHub connector

- [ ] 7.1.1 Implement `CatalogLoader` abstract base class
- [ ] 7.1.2 Implement `DataHubCatalogLoader` (read-only via DataHub REST API)
- [ ] 7.1.3 Map DataHub dataset entities → CFA catalog dict
- [ ] 7.1.4 Support: `cfa evaluate --catalog datahub://instance:8080`
- [ ] 7.1.5 Document DataHub integration

### 7.2 OpenMetadata connector

- [ ] 7.2.1 Implement `OpenMetadataCatalogLoader` (read-only via REST API)
- [ ] 7.2.2 Map OpenMetadata entities → CFA catalog dict
- [ ] 7.2.3 Support: `cfa evaluate --catalog openmetadata://instance:8585`
- [ ] 7.2.4 Document OpenMetadata integration

---

## 8. Lifecycle Dashboards — CDO-Ready Reports (Week 6-7)

### 8.1 Live dashboard

- [ ] 8.1.1 Upgrade `cfa serve` to serve lifecycle HTML dashboard
- [ ] 8.1.2 Dashboard: pipeline health cards (IFo, IFs, IFg, IDI per skill)
- [ ] 8.1.3 Dashboard: trend charts (30-day window, Chart.js)
- [ ] 8.1.4 Dashboard: promotion recommendations (CANDIDATE → ACTIVE → WATCHLIST)
- [ ] 8.1.5 Dashboard: cost DBU tracker per pipeline

### 8.2 Export

- [ ] 8.2.1 `cfa report lifecycle --format pdf` — signed PDF for auditors
- [ ] 8.2.2 `cfa report lifecycle --format csv` — raw data for analysts
- [ ] 8.2.3 PDF includes: SHA-256 hash, timestamp, auditor signature block

### 8.3 Alerts

- [ ] 8.3.1 IFg drop below 1.0 → send notification
- [ ] 8.3.2 IDI > 0.25 drift → send notification
- [ ] 8.3.3 Integrate with Slack/Teams webhooks

---

## 9. Public Launch — v1.0 (Week 8-10)

### 9.1 Launch assets

- [ ] 9.1.1 Landing page refresh (hero, value prop, quickstart above fold)
- [ ] 9.1.2 Launch blog post: "CFA v1.0: Governance Kernel for the Agent Era"
- [ ] 9.1.3 Demo video (5 min): full pipeline + LLM + MCP + compliance report
- [ ] 9.1.4 Social cards (Open Graph, Twitter) for sharing

### 9.2 Distribution

- [ ] 9.2.1 PyPI: `cfa-kernel` v1.0.0 published
- [ ] 9.2.2 Smithery/Glama/MCP.run: CFA MCP server listed
- [ ] 9.2.3 GitHub: README badges all green, 534 tests
- [ ] 9.2.4 Website: docs clean, no broken links, version 1.0.0 everywhere

### 9.3 Outreach

- [ ] 9.3.1 Dev.to / Medium post: "Why Every AI Agent Needs a Governance Kernel"
- [ ] 9.3.2 Hacker News Show HN: CFA
- [ ] 9.3.3 r/MachineLearning, r/dataengineering, r/Python cross-posts
- [ ] 9.3.4 LinkedIn article + video (personal brand: Antero Marques)
- [ ] 9.3.5 Reach out to 20 early adopters (personal DMs, data/AI communities)

### 9.4 Community

- [ ] 9.4.1 Create Discord server
- [ ] 9.4.2 Create "CFA Ambassadors" program (3-5 initial members)
- [ ] 9.4.3 GitHub Discussions enabled + seeded with FAQ
- [ ] 9.4.4 CONTRIBUTING.md + good-first-issue labels

---

## 10. Metrics & Iteration (Week 11-12)

### 10.1 Success metrics (6-month targets — conservative / stretch)

- [ ] 10.1.1 GitHub: 300 stars conservative / 1,000 stretch
- [ ] 10.1.2 PyPI: 30 downloads/day conservative / 100 stretch
- [ ] 10.1.3 MCP: listed in 3+ marketplaces
- [ ] 10.1.4 Community: 50 Discord members conservative / 100 stretch
- [ ] 10.1.5 Case studies: 1 public conservative / 3 stretch
- [ ] 10.1.6 Blog: 12 posts published

### 10.2 Feedback loop

- [ ] 10.2.1 Survey 20 early adopters (what worked, what's missing, what's confusing)
- [ ] 10.2.2 Analyze GitHub issues: top 3 pain points
- [ ] 10.2.3 Analyze MCP usage: which tools are used most
- [ ] 10.2.4 Prioritize Horizon 2 items based on feedback

---

## 11. Sustainability Plan

### 11.1 Funding

- [ ] 11.1.1 Identify 3 potential enterprise sponsors (month 3)
- [ ] 11.1.2 Apply for 1 open-source grant (CNCF, Linux Foundation AI, NLnet)
- [ ] 11.1.3 Explore GitHub Sponsors setup

### 11.2 Bus factor mitigation

- [ ] 11.2.1 Document architecture for external contributors (`ARCHITECTURE.md`)
- [ ] 11.2.2 Record 3 codebase walkthrough videos (kernel, policy engine, MCP)
- [ ] 11.2.3 Tag 10+ "good first issue" tickets

### 11.3 Maintainer health

- [ ] 11.3.1 Define maintainer vacation policy (who covers PR review?)
- [ ] 11.3.2 Set up CODEOWNERS file
- [ ] 11.3.3 Plan burnout checkpoints (monthly retro: how am I doing?)

---

## Appendix A — i18n Sync Status

| Page | EN | PT-BR | Delta |
|------|----|-------|-------|
| intro.md | ✅ | ✅ | ~sync |
| api.md | ✅ | ✅ | ~sync |
| faq.md | ✅ | ⚠️ | minor |
| guide.md | ✅ | ❌ | 39 vs 299 lines — needs complete rewrite |
| architecture-notes.md | ✅ | ❌ | 7 vs 13 sections missing |
| behavior-spec.md | ✅ | ❌ | missing Python examples |
| policy-bundles.md | ✅ | ❌ | missing 3 conditions + programmatic section |
| reporting.md | ✅ | ❌ | missing generate_report() API |
| mcp-server.md | ✅ | ⚠️ | simplified structure |
| integrations/langgraph.md | ✅ | ⚠️ | needs verification |
| integrations/openai-agents.md | ✅ | ⚠️ | needs verification |
| whitepaper.md | ✅ | ✅ | ~sync |

---

## Appendix B — Horizon 2 & 3 (Future)

### B.1 Great Expectations integration (Horizon 2)
- `backend="great_expectations"` → generates `expectation_suite` from `StateSignature`
- CFA as "governance upstream", GE as "quality downstream"

### B.2 Backends enterprise (Horizon 3)
- Snowflake (via Snowpark Python)
- BigQuery (via `google-cloud-bigquery`)
- Databricks SQL (via `databricks-sql-connector`)
- Each as pluggable `CodeGenBackend`

### B.3 Streaming governance (Horizon 3)
- Spark Structured Streaming micro-batch governance
- Kafka Connect governance hooks
- Stateful exactly-once audit for streaming

### B.4 CFA Cloud SaaS (Horizon 3)
- Managed kernel with web console
- Team policies, shared catalogs
- Pay-per-API-key or per-seat pricing

### B.5 Certified Agent marketplace (Horizon 3)
- "CFA-Certified Agent" badge
- Registry of agents that run on CFA
- Network effects: more agents → more CFA adoption
