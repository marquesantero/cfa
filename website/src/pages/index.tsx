import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  const stableVersion = (siteConfig.customFields as any)?.latestStable ?? '1.0.0';
  const devVersion = (siteConfig.customFields as any)?.version ?? '';

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
          v{stableVersion} on PyPI &middot; {devVersion} in dev
        </p>
        <h1 className="hero__title" style={{
          fontFamily: "'Syne', sans-serif", fontSize: '3.5rem', fontWeight: 800,
          color: '#fff', lineHeight: 1.1, marginBottom: '1.5rem',
        }}>
          Decide before you write.
        </h1>
        <p className="hero__subtitle" style={{
          fontSize: '1.15rem', color: '#8892a4', maxWidth: 720, margin: '0 auto 2.5rem',
        }}>
          CFA is a typed, pre-execution governance gate for AI agents and data
          pipelines. Declare an intent; get back <code style={{color: '#3dffa0'}}>approve</code>,
          {' '}<code style={{color: '#3dffa0'}}>replan(remediations)</code>, or
          {' '}<code style={{color: '#3dffa0'}}>block(reason)</code> — deterministically —
          plus a SHA-256 audit event you can verify offline.
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
          MIT licensed &middot; Python 3.11+ &middot; zero core dependencies
        </p>
      </div>
    </header>
  );
}

function Feature({ title, description }: { title: string; description: string }) {
  return (
    <div style={{
      background: 'rgba(18,21,32,0.8)', border: '1px solid #1a2035',
      borderRadius: 12, padding: '2rem',
    }}>
      <h3 style={{ color: '#3dffa0', marginBottom: '0.75rem', fontSize: '1.05rem' }}>{title}</h3>
      <p style={{ color: '#8892a4', fontSize: '0.9rem', margin: 0 }}>{description}</p>
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
          <h2 style={{ color: '#e2e8f0', marginBottom: '1.5rem', textAlign: 'center' }}>
            The five primitives that make CFA distinctive
          </h2>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1.5rem',
          }}>
            <Feature
              title="Typed, content-hashed StateSignature"
              description="Every intent is a frozen dataclass with a deterministic SHA-256 hash. Same content, same hash — cache decisions, replay, prove idempotency."
            />
            <Feature
              title="REPLAN as a first-class outcome"
              description="Decisions are not yes/no. CFA returns structured remediations the caller can apply and resubmit. The recovery loop is part of the contract."
            />
            <Feature
              title="Offline-verifiable audit chain"
              description="SHA-256 hash chain over every decision. cfa audit verify works without network, without server, without keys."
            />
            <Feature
              title="Operational catalog"
              description="PII, partition, classification, and merge key are rule primitives, not search metadata. The catalog drives policy directly."
            />
            <Feature
              title="Deterministic by default"
              description="The decision is a pure function of (signature, policy, catalog). LLM is an optional normalizer — never the decider."
            />
            <Feature
              title="Pluggable everywhere"
              description="Backends (PySpark / SQL / dbt), normalizers, sandboxes, audit storage, and policy bundles are all extension points with stable contracts."
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
        </section>

        <section style={{ marginBottom: '4rem' }}>
          <h2 style={{ color: '#e2e8f0', marginBottom: '1rem', textAlign: 'center' }}>
            What CFA is not
          </h2>
          <p style={{ color: '#8892a4', textAlign: 'center', maxWidth: 700, margin: '0 auto 2rem' }}>
            CFA pairs well with these tools — it does not replace them.
          </p>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '1rem',
          }}>
            <Feature
              title="Not LLM observability"
              description="It runs before execution, not after. Use LangSmith, Phoenix, or Patronus for traces and eval."
            />
            <Feature
              title="Not a generic policy engine"
              description="Use OPA for generic policy-as-code. CFA wins when policies are dataset-aware (PII, partition, classification, merge key)."
            />
            <Feature
              title="Not a data catalog"
              description="Use Unity Catalog, Atlan, or DataHub. CFA reads catalogs — it does not replace them."
            />
            <Feature
              title="Not data quality at rest"
              description="Use Great Expectations or Soda. CFA decides before the write."
            />
          </div>
        </section>

      </main>
    </Layout>
  );
}
