"""cfa audit — audit trail operations."""

from __future__ import annotations

import sys
from pathlib import Path


def cmd_audit_show(args) -> int:
    from cfa.audit.trail import AuditTrail, JsonLinesAuditStorage
    from cfa.cli.formatters import format_audit_table, format_json

    audit_path = args.file or args.data_dir
    storage = JsonLinesAuditStorage(audit_path) if audit_path else None
    trail = AuditTrail(storage=storage)
    events = trail.get_events_for_intent(args.id)
    event_dicts = [
        {
            "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, "isoformat") else str(e.timestamp),
            "phase": e.stage,
            "event_type": e.event_type,
            "outcome": e.outcome,
            "intent_id": e.intent_id,
        }
        for e in events
    ]
    chain_ok = trail.verify_chain()

    fmt = args.format or "table"
    if fmt == "json":
        print(format_json({"intent_id": args.id, "chain_intact": chain_ok, "events": event_dicts}))
    else:
        print(format_audit_table(event_dicts, chain_ok))

    if args.output:
        out = Path(args.output)
        out.write_text(format_json({"intent_id": args.id, "chain_intact": chain_ok, "events": event_dicts}), encoding="utf-8")
        print(f"Saved to {out}")
    return 0


def cmd_audit_verify(args) -> int:
    from cfa.audit.trail import AuditTrail, JsonLinesAuditStorage

    audit_path = args.file or args.data_dir
    storage = JsonLinesAuditStorage(audit_path) if audit_path else None
    trail = AuditTrail(storage=storage)

    if args.id:
        events = trail.get_events_for_intent(args.id)
        chain_ok = trail.verify_chain()
        if chain_ok:
            print(f"[OK] Chain INTACT for intent {args.id} ({len(events)} events)")
            return 0
        else:
            print(f"[FAIL] Chain BROKEN for intent {args.id}", file=sys.stderr)
            return 1
    else:
        all_ok = trail.verify_chain()
        if all_ok:
            print(f"[OK] Chain INTACT ({trail.event_count} events total)")
            return 0
        else:
            print("[FAIL] Chain BROKEN", file=sys.stderr)
            return 1
