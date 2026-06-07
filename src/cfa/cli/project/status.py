"""cfa status — overall CFA health and state."""

from __future__ import annotations

from datetime import UTC


def _load_config(config_path: str | None):
    from cfa.config import CfaConfig
    if config_path:
        try:
            return CfaConfig.from_yaml(config_path)
        except ImportError:
            try:
                return CfaConfig.from_json(config_path)
            except Exception:
                return None
    return CfaConfig.discover()


def cmd_status(args) -> int:
    from cfa.cli.formatters import format_json
    from cfa.storage import SqliteStorage, _sqlite_storage_stats

    config = _load_config(args.config)

    output = {
        "config_found": config is not None,
    }

    if config is not None:
        output["config"] = config.to_dict()
        output["storage"] = {"backend": config.storage.backend, "path": config.storage.path, "retention_days": config.storage.retention_days}

        if config.storage.backend == "sqlite":
            try:
                from pathlib import Path
                db_path = Path(config.storage.path)
                if db_path.exists():
                    store = SqliteStorage(db_path)
                    store.ensure_schema()
                    stats = _sqlite_storage_stats(store)
                    output["storage_stats"] = stats.to_dict()
                    store.close()
                else:
                    output["storage_stats"] = {"status": "not_found", "path": str(db_path)}
            except Exception as e:
                output["storage_stats"] = {"status": "error", "error": str(e)}
    else:
        output["config"] = {"status": "not_found", "hint": "Run 'cfa init' to create a new project"}

    if args.format == "json":
        print(format_json(output))
    else:
        if config is None:
            print("CFA Status: no config found")
            print("  Run 'cfa init' to create a new CFA project.")
            return 0

        print("CFA Status")
        print(f"  config:       found (v{config.version})")
        print(f"  storage:      {config.storage.backend} @ {config.storage.path}")
        print(f"  retention:    {config.storage.retention_days} days")
        print(f"  catalog:      {config.defaults.catalog}")
        print(f"  policy:       {config.defaults.policy_bundle}")

        stats = output.get("storage_stats", {})
        if stats.get("backend") == "sqlite":
            print(f"  file size:    {stats.get('file_size_bytes', 0):,} bytes")
            print(f"  audit events: {stats.get('audit_events_count', 0)}")
            print(f"  executions:   {stats.get('execution_records_count', 0)}")
            print(f"  skills:       {stats.get('skill_records_count', 0)}")
            if stats.get("newest_record"):
                print(f"  last record:  {stats['newest_record'][:19]}")
            if stats.get("oldest_record") and stats.get("oldest_record"):
                from datetime import datetime, timedelta
                try:
                    oldest = datetime.fromisoformat(stats["oldest_record"])
                    retention = timedelta(days=config.storage.retention_days)
                    overdue = oldest < datetime.now(UTC) - retention
                    if overdue:
                        print(f"  ⚠ retention:   records older than {config.storage.retention_days}d exist. Run 'cfa storage cleanup'")
                except (ValueError, TypeError):
                    pass
        elif stats.get("status") == "not_found":
            print("  storage:      not created yet (will be auto-created on first use)")
    return 0
