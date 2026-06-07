"""cfa storage — manage CFA storage (stats, cleanup, vacuum)."""

from __future__ import annotations

import sys
from datetime import UTC


def cmd_storage_stats(args) -> int:
    from cfa.cli.formatters import format_json
    from cfa.storage import JsonLinesStorage, SqliteStorage, _sqlite_storage_stats

    if args.db:
        store = SqliteStorage(args.db)
        store.ensure_schema()
        stats = _sqlite_storage_stats(store)
        store.close()
    elif args.dir:
        store = JsonLinesStorage(args.dir)
        stats = store.stats()
    else:
        print("Error: --db or --dir required", file=sys.stderr)
        return 1

    if args.format == "json":
        print(format_json(stats.to_dict()))
    else:
        print(f"CFA Storage: {stats.backend} @ {stats.path}")
        print(f"  file size:        {stats.file_size_bytes:,} bytes")
        print(f"  audit events:     {stats.audit_events_count}")
        print(f"  execution records:{stats.execution_records_count}")
        print(f"  skill records:    {stats.skill_records_count}")
        print(f"  metrics:          {stats.metrics_count}")
        if stats.oldest_record:
            print(f"  oldest record:    {stats.oldest_record[:19]}")
        if stats.newest_record:
            print(f"  newest record:    {stats.newest_record[:19]}")
    return 0


def cmd_storage_cleanup(args) -> int:
    from datetime import datetime, timedelta

    from cfa.config import CfaConfig
    from cfa.storage import JsonLinesStorage, SqliteStorage, _sqlite_storage_cleanup

    if args.retention_days:
        before = (datetime.now(UTC) - timedelta(days=args.retention_days)).isoformat()
    elif args.before:
        before = args.before
    else:
        config = CfaConfig.discover()
        if config and config.storage.retention_days:
            before = (datetime.now(UTC) - timedelta(days=config.storage.retention_days)).isoformat()
        else:
            print("Error: --retention or --before required (or set retention_days in cfa.yaml)", file=sys.stderr)
            return 1

    if args.db:
        store = SqliteStorage(args.db)
        store.ensure_schema()
        deleted = _sqlite_storage_cleanup(store, before)
        store.close()
    elif args.dir:
        store = JsonLinesStorage(args.dir)
        deleted = store.cleanup(before)
    else:
        print("Error: --db or --dir required", file=sys.stderr)
        return 1

    print(f"Cleaned up {deleted} records before {before[:19]}")
    return 0


def cmd_storage_vacuum(args) -> int:
    from cfa.storage import SqliteStorage

    if args.db:
        store = SqliteStorage(args.db)
        store.ensure_schema()
        store.vacuum()
        store.close()
        print(f"Vacuumed {args.db}")
    else:
        print("Error: --db required for vacuum", file=sys.stderr)
        return 1
    return 0
