import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
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
          Technical Whitepaper &middot; v0.1.6
        </p>
        <h1 className="hero__title" style={{
          fontFamily: "'Syne', sans-serif", fontSize: '3.5rem', fontWeight: 800,
          color: '#fff', lineHeight: 1.1, marginBottom: '1.5rem',
        }}>
          Contextual Flux<br/>Architecture
        </h1>
        <p className="hero__subtitle" style={{
          fontSize: '1.15rem', color: '#8892a4', maxWidth: 700, margin: '0 auto 2.5rem',
        }}>
          Governed execution for AI agents and data systems.
          Formalize intent. Evaluate policy. Control execution.
          Project state. Track lifecycle. Audit everything.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link className="button button--primary button--lg" to="/docs/whitepaper"
            style={{ background: '#3dffa0', color: '#07090f', border: 'none', fontWeight: 600 }}>
            Read the Whitepaper
          </Link>
          <Link className="button button--secondary button--lg" to="/docs/getting-started">
            Get Started
          </Link>
        </div>
      </div>
    </header>
  );
}

function Feature({ title, description }: { title: string; description: string }) {
  return (
    <div style={{
      background: 'rgba(18,21,32,0.8)', border: '1px solid #1a2035',
      borderRadius: 12, padding: '2rem', textAlign: 'center',
    }}>
      <h3 style={{ color: '#3dffa0', marginBottom: '0.75rem' }}>{title}</h3>
      <p style={{ color: '#8892a4', fontSize: '0.9rem' }}>{description}</p>
    </div>
  );
}

export default function Home(): JSX.Element {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout title={siteConfig.title} description={siteConfig.tagline}>
      <HomepageHeader />
      <main style={{ padding: '4rem 2rem', maxWidth: 1100, margin: '0 auto' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1.5rem', marginBottom: '4rem',
        }}>
          <Feature title="StateSignature" description="Formal typed contract for every intent — domain, datasets, constraints, target layer. Immutable, hash-verifiable." />
          <Feature title="Policy Engine" description="Declarative policy rules: APPROVE, REPLAN, or BLOCK. Auto-interventions correct constraints before execution." />
          <Feature title="Audit Trail" description="SHA-256 hash chain — cryptographically verifiable. Every decision, every fault, every remediation, permanently recorded." />
          <Feature title="CLI + MCP" description="cfa evaluate from the terminal. MCP server exposes governance to ChatGPT, Claude, Copilot, and any AI agent." />
          <Feature title="Rich Reports" description="Self-contained HTML reports with Chart.js — execution timeline, audit chain, lifecycle dashboard, compliance summary." />
          <Feature title="Lifecycle Indices" description="IFo, IFs, IFg, IDI — quantitative pipeline health. Promotion, watchlist, demotion based on evidence, not intuition." />
        </div>

        <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
          <h2 style={{ color: '#e2e8f0', marginBottom: '1rem' }}>Zero Runtime Dependencies</h2>
          <p style={{ color: '#8892a4', maxWidth: 600, margin: '0 auto' }}>
            The entire CFA core runs on Python 3.11+ standard library. No mandatory pip installs.
            Optional extras: YAML, OpenTelemetry, MCP protocol.
          </p>
        </div>

        <div style={{
          background: 'rgba(61,255,160,0.04)', border: '1px solid rgba(61,255,160,0.15)',
          borderRadius: 12, padding: '2rem', textAlign: 'center',
        }}>
          <code style={{
            background: 'rgba(0,0,0,0.3)', padding: '0.75rem 1.5rem',
            borderRadius: 8, fontSize: '0.95rem', color: '#3dffa0',
          }}>
            pip install cfa-kernel && cfa evaluate "Join NFe with Clientes persist Silver"
          </code>
          <p style={{ color: '#8892a4', marginTop: '1rem', fontSize: '0.85rem' }}>
            536 tests &middot; MIT License &middot; Python 3.11+
          </p>
        </div>
      </main>
    </Layout>
  );
}
