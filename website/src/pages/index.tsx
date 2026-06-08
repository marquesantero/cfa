import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  const version = (siteConfig.customFields as any)?.version ?? '1.1.0';

  return (
    <header className={clsx('hero hero--primary')} style={{
      background: 'linear-gradient(135deg, #07090f 0%, #0d1525 50%, #0a1628 100%)',
      padding: '6rem 2rem',
      textAlign: 'center',
    }}>
      <div className="container">
        <p style={{
          fontFamily: 'monospace', fontSize: '0.75rem', letterSpacing: '0.25em',
          color: '#3dffa0', textTransform: 'uppercase', marginBottom: '1rem',
        }}>
          v{version} · MIT · Python 3.11+
        </p>
        <h1 className="hero__title" style={{
          fontFamily: "'Syne', sans-serif", fontSize: '3.5rem', fontWeight: 800,
          color: '#fff', lineHeight: 1.1, marginBottom: '1.5rem',
        }}>
          Decide before you write.
        </h1>
        <p className="hero__subtitle" style={{
          fontSize: '1.15rem', color: '#8892a4', maxWidth: 740, margin: '0 auto 2.5rem',
        }}>
          CFA is a typed, pre-execution governance gate for AI agents and data
          pipelines. Declare an intent; get back <code style={{color: '#3dffa0'}}>approve</code>,
          {' '}<code style={{color: '#3dffa0'}}>replan(remediations)</code>, or
          {' '}<code style={{color: '#3dffa0'}}>block(reason)</code> — in <strong style={{color: '#3dffa0'}}>under 3 ms p99</strong> —
          {' '}plus a SHA-256 audit event you can verify offline with no network and no keys.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link className="button button--primary button--lg" to="/docs/getting-started"
            style={{ background: '#3dffa0', color: '#07090f', border: 'none', fontWeight: 600 }}>
            Get started in 5 minutes
          </Link>
          <Link className="button button--secondary button--lg" to="/docs/intro">
            Read the docs
          </Link>
          <Link className="button button--secondary button--lg"
            href="https://github.com/marquesantero/cfa">
            GitHub
          </Link>
        </div>
        <p style={{
          marginTop: '1.5rem', fontSize: '0.8rem', color: '#5b6478',
        }}>
          536 tests · 81% coverage · zero core dependencies · p99 2.4 ms · 930 evaluations/sec
        </p>
      </div>
    </header>
  );
}

function Card({ title, description, code }: { title: string; description: string; code?: string }) {
  return (
    <div style={{
      background: 'rgba(18,21,32,0.8)', border: '1px solid #1a2035',
      borderRadius: 12, padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem',
    }}>
      <h3 style={{ color: '#3dffa0', margin: 0, fontSize: '1.05rem' }}>{title}</h3>
      <p style={{ color: '#8892a4', fontSize: '0.9rem', margin: 0, lineHeight: 1.5 }}>{description}</p>
      {code && (
        <pre style={{
          background: 'rgba(0,0,0,0.35)', padding: '0.75rem',
          borderRadius: 8, fontSize: '0.78rem', color: '#cbd5e1',
          margin: 0, overflowX: 'auto', whiteSpace: 'pre',
        }}>{code}</pre>
      )}
    </div>
  );
}

export default function Home(): JSX.Element {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout title={siteConfig.title} description={siteConfig.tagline}>
      <HomepageHeader />
      <main style={{ padding: '4rem 2rem', maxWidth: 1100, margin: '0 auto' }}>

        <section style={{ marginBottom: '4rem' }}>
          <h2 style={{ color: '#e2e8f0', marginBottom: '0.5rem', textAlign: 'center' }}>
            Why CFA exists
          </h2>
          <p style={{ color: '#8892a4', textAlign: 'center', maxWidth: 720, margin: '0 auto 2.5rem' }}>
            Six concrete things CFA does today that no adjacent tool gives you together.
          </p>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.5rem',
          }}>
            <Card
              title="Structured remediation, not yes/no"
              description="When a fixable rule fails, CFA returns the fix as data. The caller — an LLM agent, a CI step, a human — applies it and retries. Bounded at three attempts. Every cycle audited."
              code={`{
  "action": "replan",
  "interventions": [
    "Set constraints.no_pii_raw=True",
    "Apply sha256() on PII columns"
  ]
}`}
            />
            <Card
              title="Offline-verifiable audit chain"
              description="Every decision is a content-hashed event linked into a SHA-256 chain. cfa audit verify replays the chain anywhere — no vendor, no server, no key, no network."
              code={`$ cfa audit verify --file audit.jsonl
OK · 1 274 events verified
last_hash=a4f3…6c01`}
            />
            <Card
              title="Dataset-aware policy primitives"
              description="PII, partition, classification, merge_key, target_layer — first-class primitives, not metadata you re-encode in Rego. A real rule fits in six YAML lines."
              code={`- name: forbid_raw_pii
  condition: pii_in_protected_layer
  action: block
  severity: critical
  remediation:
    - "Apply sha256() before write"`}
            />
            <Card
              title="One signature, three backends"
              description="The same approved StateSignature compiles to PySpark + Delta Lake, ANSI SQL with MERGE INTO, or dbt models with schema.yml. Pluggable through BackendRegistry."
              code={`cfa evaluate "..." --backend pyspark
cfa evaluate "..." --backend sql
cfa evaluate "..." --backend dbt`}
            />
            <Card
              title="MCP server, working today"
              description="Any MCP-compatible agent (Claude Desktop, Cursor, Continue, custom LangGraph nodes) calls CFA before touching production. Five tools, JSON-RPC over stdio."
              code={`{ "mcpServers": {
    "cfa": {
      "command": "python",
      "args": ["-m", "cfa.mcp"]
    }
  }
}`}
            />
            <Card
              title="Deterministic by default; LLM opt-in"
              description="The decision path is a pure function of (signature, policy, catalog). Same inputs → same decision → same hash, no network. LLMs participate only on the front edge, behind the [llm] extra."
              code={`pip install cfa-kernel        # core
pip install cfa-kernel[llm]   # opt-in`}
            />
          </div>
        </section>

        <section style={{
          background: 'rgba(61,255,160,0.04)', border: '1px solid rgba(61,255,160,0.15)',
          borderRadius: 12, padding: '2.5rem', textAlign: 'center', marginBottom: '4rem',
        }}>
          <code style={{
            background: 'rgba(0,0,0,0.3)', padding: '0.75rem 1.5rem',
            borderRadius: 8, fontSize: '0.95rem', color: '#3dffa0', display: 'inline-block',
          }}>
            pip install cfa-kernel &amp;&amp; cfa evaluate "join NFe with Clientes persist Silver"
          </code>
          <p style={{ color: '#8892a4', marginTop: '1rem', fontSize: '0.85rem', maxWidth: 580, margin: '1rem auto 0' }}>
            Pairs with — does not replace — LangSmith, OPA, Unity Catalog, and Great Expectations.{' '}
            <Link to="/docs/compare" style={{ color: '#3dffa0' }}>See the comparison →</Link>
          </p>
        </section>

      </main>
    </Layout>
  );
}
