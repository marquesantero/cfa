"""cfa lifecycle — lifecycle management commands."""

from __future__ import annotations


def cmd_lifecycle_evaluate(args) -> int:
    from cfa.cli.formatters import format_json
    from cfa.observability.promotion import PromotionEngine, PromotionPolicy
    from cfa.storage import SqliteStorage

    store = None
    if args.db:
        store = SqliteStorage(args.db)
        store.ensure_schema()

    engine = PromotionEngine(
        policy=PromotionPolicy(evaluation_window_days=args.window),
        storage=store,
    )

    results = []
    for skill in engine.list_skills():
        _, scores = engine.evaluate(
            skill.signature_hash,
            policy_bundle_version=args.policy_bundle,
        )
        results.append({
            "signature_hash": skill.signature_hash,
            "state": skill.state.value,
            "ifo": round(scores.ifo, 3),
            "ifs": round(scores.ifs, 3),
            "ifg": round(scores.ifg, 3),
            "idi": round(scores.idi, 3),
            "executions": scores.execution_count,
            "promotion_eligible": scores.promotion_eligible,
            "drift_detected": scores.drift_detected,
        })

    if args.format == "json":
        print(format_json(results))
    else:
        print(f"Lifecycle evaluation ({len(results)} skills, {args.window}d window):")
        for r in results:
            flags = []
            if r["promotion_eligible"]:
                flags.append("PROMOTE")
            if r["drift_detected"]:
                flags.append("DRIFT")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  {r['signature_hash'][:12]}  state={r['state']:12}  "
                  f"IFo={r['ifo']:.2f} IFs={r['ifs']:.2f} IFg={r['ifg']:.2f} IDI={r['idi']:.2f}  "
                  f"execs={r['executions']}{flag_str}")

    if store:
        store.close()
    return 0


def cmd_lifecycle_list(args) -> int:
    from cfa.cli.formatters import format_json
    from cfa.observability.promotion import PromotionEngine
    from cfa.storage import SqliteStorage

    store = None
    if args.db:
        store = SqliteStorage(args.db)
        store.ensure_schema()

    engine = PromotionEngine(storage=store)
    skills = engine.list_skills(state=None)

    results = [
        {
            "signature_hash": s.signature_hash,
            "state": s.state.value,
            "demotion_reason": s.demotion_reason,
            "history_count": len(s.history),
        }
        for s in skills
    ]

    if args.format == "json":
        print(format_json(results))
    else:
        print(f"Lifecycle skills ({len(results)}):")
        for r in results:
            print(f"  {r['signature_hash'][:12]}  state={r['state']:12}  "
                  f"transitions={r['history_count']}  {r['demotion_reason']}")

    if store:
        store.close()
    return 0
