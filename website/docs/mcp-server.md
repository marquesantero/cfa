---
sidebar_position: 12
---

# MCP Server

CFA exposes its governance tools via the **Model Context Protocol** (MCP), allowing any MCP-compatible AI agent (ChatGPT, Claude, Copilot, Cursor, Windsurf) to query and enforce CFA policies in real time.

## Quick Start

```bash
pip install cfa-kernel[mcp]
cfa-mcp
```

Or:
```bash
python -m cfa.mcp
```

## Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cfa": {
      "command": "python",
      "args": ["-m", "cfa.mcp"]
    }
  }
}
```

## Exposed Tools

### 1. `cfa_evaluate_signature`

Evaluate a StateSignature JSON against the active policy bundle.

```json
{
  "name": "cfa_evaluate_signature",
  "arguments": {
    "signature": {
      "domain": "fiscal",
      "intent": "reconciliation",
      "target_layer": "silver",
      "datasets": [...],
      "constraints": {...}
    }
  }
}
```

Returns: `APPROVE`, `REPLAN`, or `BLOCK` with faults and remediation steps.

### 2. `cfa_describe_rules`

List all active policy rules with descriptions and severities.

### 3. `cfa_explain_fault`

Explain a fault code — what it means, why it occurs, and how to fix it.

```json
{ "fault_code": "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER" }
```

### 4. `cfa_audit_check`

Verify the integrity of the audit trail hash chain.

### 5. `cfa_list_backends`

List registered codegen backends with capabilities.

## Protocol

CFA MCP server uses JSON-RPC 2.0 over stdin/stdout. Zero external dependencies — pure Python standard library.

```
Client (stdin)  →  JSON-RPC request  →  Server
Server (stdout) →  JSON-RPC response →  Client
```
