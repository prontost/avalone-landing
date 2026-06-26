#!/usr/bin/env python3
"""Rotated local backups of SQLite databases.

Configuration: a JSON file with a list of absolute paths (see backup-config.json).
If config is missing, falls back to the main Avalone/Counta/Work DBs.

Run manually:
    python3 infra/backup/backup_db.py --config infra/backup/backup-config.json
Or via launchd/cron every hour.
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_RETENTION_DAYS = 14
BACKUP_ROOT = Path.home() / ".avalone" / "backups" / "auto"
FALLBACK_DBS = [
    Path.home() / ".avalone" / "avalone.db",
    Path.home() / ".counta" / "counta.db",
    Path.home() / ".routa" / "routa.db",
]


def _load_config(config_path: Path) -> list[Path]:
    if not config_path.exists():
        return FALLBACK_DBS
    try:
        with config_path.open("r", encoding="utf-8") as f:
            paths = json.load(f)
        return [Path(p).expanduser().resolve() for p in paths if p]
    except (json.JSONDecodeError, OSError):
        return FALLBACK_DBS


def backup_one(source: Path, retention_days: int) -> Path | None:
    if not source.exists():
        print(f"[skip] source not found: {source}")
        return None

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_ROOT / f"{source.stem}-{ts}{source.suffix}"
    shutil.copy2(str(source), str(dest))
    print(f"[ok] {source} -> {dest}")
    return dest


def _rotate(retention_days: int) -> None:
    if not BACKUP_ROOT.exists():
        return
    cutoff = datetime.now().timestamp() - retention_days * 24 * 3600
    removed = 0
    for f in BACKUP_ROOT.iterdir():
        if not f.is_file():
            continue
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        print(f"[rotate] removed {removed} backup(s) older than {retention_days} days")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotated SQLite database backups")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to JSON config with DB list",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Keep backups for N days (default: {DEFAULT_RETENTION_DAYS})",
    )
    args = parser.parse_args()

    dbs = _load_config(args.config)
    for db_path in dbs:
        backup_one(db_path, args.retention_days)
    _rotate(args.retention_days)


if __name__ == "__main__":
    main()
