#!/usr/bin/env python3
"""Import conversations from main Cursor into dCursor (read-only source)."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_CURSOR_CONFIG = Path.home() / ".config/Cursor"
DEFAULT_DCURSOR_CONFIG = Path.home() / ".config/dCursor"
DEFAULT_CURSOR_DATA = Path.home() / ".cursor"
DEFAULT_DCURSOR_DATA = Path.home() / ".dcursor"

READ_ONLY_SOURCE_ROOTS = (
    DEFAULT_CURSOR_CONFIG,
    DEFAULT_CURSOR_DATA,
)

PROTECTED_KEY_PREFIXES = (
    "cursorAuth/",
    "adminSettings.",
    "secret://",
)

MERGE_JSON_KEYS = (
    "glass.localAgentProjects.v1",
    "glass.localAgentProjectMembership.v1",
    "composer.planRegistry",
    "composer.planRedirects",
    "conversationClassificationScoredConversations",
)

GLASS_KEY_PREFIXES = (
    "cursor/glass.tabs.v2/",
    "cursor/glass.editorPanelVisibility.agent/",
    "cursor/glass.editorPanelFullscreen/",
)

WORKSPACE_MERGE_KEYS = (
    "composer.composerData",
    "workbench.parts.embeddedAuxBarEditor.state",
)


def log(msg: str) -> None:
    print(msg, flush=True)


def resolve_path(path: Path) -> Path:
    return path.expanduser().resolve()


def assert_readonly_source(path: Path) -> None:
    """Guarantee we only read from Cursor-owned locations."""
    resolved = resolve_path(path)
    allowed = any(
        resolved == root or root in resolved.parents
        for root in (resolve_path(p) for p in READ_ONLY_SOURCE_ROOTS)
    )
    if not allowed:
        raise RuntimeError(
            f"refusing to read non-Cursor path: {resolved} "
            "(dCursor only reads ~/.config/Cursor and ~/.cursor)"
        )


def assert_write_target(path: Path, dcursor_config: Path, dcursor_data: Path) -> None:
    """Guarantee we never write into main Cursor data."""
    resolved = resolve_path(path)
    forbidden = (
        resolve_path(DEFAULT_CURSOR_CONFIG),
        resolve_path(DEFAULT_CURSOR_DATA),
    )
    for root in forbidden:
        if resolved == root or root in resolved.parents:
            raise RuntimeError(
                f"refusing to write into main Cursor path: {resolved}"
            )

    allowed = (
        resolve_path(dcursor_config),
        resolve_path(dcursor_data),
    )
    if not any(resolved == root or root in resolved.parents for root in allowed):
        raise RuntimeError(
            f"refusing to write outside dCursor paths: {resolved}"
        )


def is_protected_key(key: str) -> bool:
    return key.startswith(PROTECTED_KEY_PREFIXES)


def load_json(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def merge_lists(existing, incoming, id_field: str = "id"):
    if not isinstance(existing, list):
        existing = []
    if not isinstance(incoming, list):
        return existing

    by_id = {}
    order = []
    for item in existing:
        if isinstance(item, dict) and id_field in item:
            item_id = item[id_field]
            by_id[item_id] = item
            order.append(item_id)
        else:
            order.append(id(item))
            by_id[id(item)] = item

    added = 0
    for item in incoming:
        if not isinstance(item, dict) or id_field not in item:
            continue
        item_id = item[id_field]
        if item_id not in by_id:
            order.append(item_id)
            added += 1
        by_id[item_id] = item

    merged = [by_id[item_id] for item_id in order if item_id in by_id]
    return merged, added


def merge_dicts(existing, incoming):
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(incoming, dict):
        return existing, 0

    added = 0
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged:
            added += 1
        merged[key] = value
    return merged, added


def open_db(path: Path, *, write: bool = False) -> sqlite3.Connection:
    if write:
        mode = "rwc"
    else:
        mode = "ro"
    return sqlite3.connect(f"file:{path}?mode={mode}", uri=True)


def open_source_db(path: Path) -> sqlite3.Connection:
    assert_readonly_source(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return open_db(path, write=False)


def open_dest_db(path: Path, *, write: bool) -> sqlite3.Connection:
    if write:
        assert_write_target(path, DEFAULT_DCURSOR_CONFIG, DEFAULT_DCURSOR_DATA)
    return open_db(path, write=write)


def merge_conversation_search(
    src_db: Path,
    dst_db: Path,
    dry_run: bool,
    dcursor_config: Path,
    dcursor_data: Path,
) -> dict[str, int]:
    stats = {
        "conversations_added": 0,
        "candidates_added": 0,
        "fts_rows_added": 0,
    }
    if not src_db.exists():
        return stats

    src = open_source_db(src_db)
    src.row_factory = sqlite3.Row

    if dry_run:
        dst = open_db(dst_db) if dst_db.exists() else None
    else:
        dst_path = dst_db
        assert_write_target(dst_path, dcursor_config, dcursor_data)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if not dst_path.exists():
            shutil.copy2(src_db, dst_path)
            log(f"Created {dst_path} from Cursor conversation index (read-only copy)")
            src.close()
            dst = open_dest_db(dst_path, write=True)
            dst.execute("SELECT COUNT(*) FROM conversations")
            stats["conversations_added"] = dst.fetchone()[0]
            dst.close()
            return stats
        dst = open_dest_db(dst_path, write=True)

    src_cur = src.cursor()
    dst_cur = dst.cursor()

    dst_cur.execute("SELECT id FROM conversations")
    existing_ids = {row[0] for row in dst_cur.fetchall()}

    src_cur.execute(
        "SELECT fts_rowid, source, scope, id, title, branches, updated_at, "
        "is_archived, root_fingerprint, cache_fingerprint FROM conversations"
    )
    for row in src_cur.fetchall():
        if row["id"] in existing_ids:
            continue
        stats["conversations_added"] += 1
        if dry_run:
            continue

        src_cur.execute(
            "SELECT title, body, branches FROM conversation_fts WHERE rowid=?",
            (row["fts_rowid"],),
        )
        fts_row = src_cur.fetchone()
        if fts_row:
            dst_cur.execute(
                "INSERT INTO conversation_fts(title, body, branches) "
                "VALUES (?, ?, ?)",
                (fts_row["title"], fts_row["body"], fts_row["branches"]),
            )
            fts_rowid = dst_cur.lastrowid
            stats["fts_rows_added"] += 1
        else:
            dst_cur.execute("SELECT COALESCE(MAX(fts_rowid), 0) + 1 FROM conversations")
            fts_rowid = int(dst_cur.fetchone()[0])

        dst_cur.execute(
            "INSERT INTO conversations "
            "(fts_rowid, source, scope, id, title, branches, updated_at, "
            "is_archived, root_fingerprint, cache_fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fts_rowid,
                row["source"],
                row["scope"],
                row["id"],
                row["title"],
                row["branches"],
                row["updated_at"],
                row["is_archived"],
                row["root_fingerprint"],
                row["cache_fingerprint"],
            ),
        )

    src_cur.execute("SELECT id, updated_at FROM conversation_search_candidates")
    dst_cur.execute("SELECT id FROM conversation_search_candidates")
    existing_candidates = {row[0] for row in dst_cur.fetchall()}
    for row in src_cur.fetchall():
        if row["id"] in existing_candidates:
            continue
        stats["candidates_added"] += 1
        if dry_run:
            continue
        dst_cur.execute(
            "INSERT INTO conversation_search_candidates(id, updated_at) VALUES (?, ?)",
            (row["id"], row["updated_at"]),
        )

    if not dry_run:
        dst.commit()
    src.close()
    dst.close()
    return stats


def merge_state_db(
    src_db: Path,
    dst_db: Path,
    dry_run: bool,
    dcursor_config: Path,
    dcursor_data: Path,
) -> dict[str, int]:
    stats = {
        "json_keys_merged": 0,
        "glass_keys_copied": 0,
        "items_added": 0,
    }
    if not src_db.exists() or not dst_db.exists():
        return stats

    src = open_source_db(src_db)
    dst = open_dest_db(dst_db, write=not dry_run)
    src_cur = src.cursor()
    dst_cur = dst.cursor()

    dst_cur.execute("SELECT key, value FROM ItemTable")
    dest_items = {row[0]: row[1] for row in dst_cur.fetchall()}

    for key in MERGE_JSON_KEYS:
        src_cur.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
        row = src_cur.fetchone()
        if not row:
            continue

        incoming = load_json(row[0])
        existing = load_json(dest_items.get(key, "null"))
        if key == "glass.localAgentProjects.v1":
            merged, added = merge_lists(existing, incoming, "id")
        else:
            merged, added = merge_dicts(existing, incoming)
        if added:
            stats["json_keys_merged"] += 1
            stats["items_added"] += added
            if not dry_run:
                dst_cur.execute(
                    "INSERT OR REPLACE INTO ItemTable(key, value) VALUES (?, ?)",
                    (key, dump_json(merged)),
                )

    for prefix in GLASS_KEY_PREFIXES:
        src_cur.execute(
            "SELECT key, value FROM ItemTable WHERE key LIKE ?",
            (prefix + "%",),
        )
        for key, value in src_cur.fetchall():
            if is_protected_key(key) or key in dest_items:
                continue
            stats["glass_keys_copied"] += 1
            if not dry_run:
                dst_cur.execute(
                    "INSERT OR REPLACE INTO ItemTable(key, value) VALUES (?, ?)",
                    (key, value),
                )

    if not dry_run:
        dst.commit()
    src.close()
    dst.close()
    return stats


def merge_workspace_storage(
    src_root: Path,
    dst_root: Path,
    dry_run: bool,
    dcursor_config: Path,
    dcursor_data: Path,
) -> dict[str, int]:
    stats = {"workspaces_merged": 0, "workspace_keys_added": 0}
    if not src_root.exists():
        return stats

    assert_readonly_source(src_root)

    for src_ws in src_root.iterdir():
        if not src_ws.is_dir():
            continue
        src_db = src_ws / "state.vscdb"
        if not src_db.exists():
            continue

        dst_ws = dst_root / src_ws.name
        dst_db = dst_ws / "state.vscdb"
        if not dst_db.exists():
            if dry_run:
                stats["workspaces_merged"] += 1
                continue
            assert_write_target(dst_ws, dcursor_config, dcursor_data)
            dst_ws.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_db, dst_db)
            stats["workspaces_merged"] += 1
            continue

        src = open_source_db(src_db)
        dst = open_dest_db(dst_db, write=not dry_run)
        src_cur = src.cursor()
        dst_cur = dst.cursor()
        dst_cur.execute("SELECT key FROM ItemTable")
        existing_keys = {row[0] for row in dst_cur.fetchall()}
        added_here = 0

        for key in WORKSPACE_MERGE_KEYS:
            src_cur.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
            row = src_cur.fetchone()
            if not row or key in existing_keys:
                continue
            added_here += 1
            if not dry_run:
                dst_cur.execute(
                    "INSERT OR REPLACE INTO ItemTable(key, value) VALUES (?, ?)",
                    (key, row[0]),
                )

        if added_here:
            stats["workspaces_merged"] += 1
            stats["workspace_keys_added"] += added_here
            if not dry_run:
                dst.commit()
        src.close()
        dst.close()

    return stats


def copy_agent_transcripts(
    src_root: Path,
    dst_root: Path,
    dry_run: bool,
    dcursor_config: Path,
    dcursor_data: Path,
) -> dict[str, int]:
    stats = {"projects_seen": 0, "transcript_files_copied": 0}
    if not src_root.exists():
        return stats

    assert_readonly_source(src_root)

    for src_project in src_root.iterdir():
        if not src_project.is_dir():
            continue
        src_transcripts = src_project / "agent-transcripts"
        if not src_transcripts.exists():
            continue
        stats["projects_seen"] += 1
        dst_transcripts = dst_root / src_project.name / "agent-transcripts"
        for src_file in src_transcripts.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(src_transcripts)
            dst_file = dst_transcripts / rel
            if dst_file.exists():
                continue
            stats["transcript_files_copied"] += 1
            if dry_run:
                continue
            assert_write_target(dst_file, dcursor_config, dcursor_data)
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

    return stats


def backup_dcursor(config_dir: Path, data_dir: Path) -> Path:
    assert_write_target(config_dir, config_dir, data_dir)
    assert_write_target(data_dir, config_dir, data_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = data_dir / "backups" / f"pre-import-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    gs = config_dir / "User/globalStorage"
    for name in (
        "state.vscdb",
        "conversation-search.db",
        "state.vscdb-wal",
        "state.vscdb-shm",
        "conversation-search.db-wal",
        "conversation-search.db-shm",
    ):
        src = gs / name
        if src.exists():
            shutil.copy2(src, backup_dir / name)

    ws = config_dir / "User/workspaceStorage"
    if ws.exists():
        shutil.copytree(ws, backup_dir / "workspaceStorage", dirs_exist_ok=True)

    return backup_dir


def process_running(pattern: str) -> bool:
    try:
        import subprocess

        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import conversations from main Cursor into dCursor. "
            "Cursor is read-only; only dCursor data is modified."
        ),
    )
    parser.add_argument(
        "--cursor-config",
        type=Path,
        default=DEFAULT_CURSOR_CONFIG,
        help="Cursor config directory (default: ~/.config/Cursor)",
    )
    parser.add_argument(
        "--dcursor-config",
        type=Path,
        default=DEFAULT_DCURSOR_CONFIG,
        help="dCursor config directory (default: ~/.config/dCursor)",
    )
    parser.add_argument(
        "--cursor-data",
        type=Path,
        default=DEFAULT_CURSOR_DATA,
        help="Cursor data directory (default: ~/.cursor)",
    )
    parser.add_argument(
        "--dcursor-data",
        type=Path,
        default=DEFAULT_DCURSOR_DATA,
        help="dCursor data directory (default: ~/.dcursor)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without writing changes",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Do not create a dCursor backup before importing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Continue even if Cursor or dCursor appears to be running",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.cursor_config.exists():
        log(f"error: Cursor config not found at {args.cursor_config}")
        return 1

    try:
        assert_readonly_source(args.cursor_config)
        assert_readonly_source(args.cursor_data)
    except RuntimeError as exc:
        log(f"error: {exc}")
        return 1

    if not args.force:
        if process_running("/usr/share/cursor/cursor"):
            log("error: Cursor appears to be running. Close it first or use --force.")
            return 1
        if process_running("/usr/share/dcursor/dcursor"):
            log("error: dCursor appears to be running. Close it first or use --force.")
            return 1

    src_gs = args.cursor_config / "User/globalStorage"
    dst_gs = args.dcursor_config / "User/globalStorage"
    src_ws = args.cursor_config / "User/workspaceStorage"
    dst_ws = args.dcursor_config / "User/workspaceStorage"
    src_projects = args.cursor_data / "projects"
    dst_projects = args.dcursor_data / "projects"

    log("==> Importing conversations from Cursor into dCursor (read-only source)")
    log(f"    source config: {args.cursor_config}")
    log(f"    target config: {args.dcursor_config}")
    log("    main Cursor will NOT be modified")
    if args.dry_run:
        log("    mode: dry-run")

    if not args.dry_run and not args.skip_backup:
        backup_dir = backup_dcursor(args.dcursor_config, args.dcursor_data)
        log(f"==> Backup saved to {backup_dir}")

    conv_stats = merge_conversation_search(
        src_gs / "conversation-search.db",
        dst_gs / "conversation-search.db",
        args.dry_run,
        args.dcursor_config,
        args.dcursor_data,
    )
    state_stats = merge_state_db(
        src_gs / "state.vscdb",
        dst_gs / "state.vscdb",
        args.dry_run,
        args.dcursor_config,
        args.dcursor_data,
    )
    ws_stats = merge_workspace_storage(
        src_ws,
        dst_ws,
        args.dry_run,
        args.dcursor_config,
        args.dcursor_data,
    )
    transcript_stats = copy_agent_transcripts(
        src_projects,
        dst_projects,
        args.dry_run,
        args.dcursor_config,
        args.dcursor_data,
    )

    log("")
    log("Import summary:")
    log(f"  conversations added:      {conv_stats['conversations_added']}")
    log(f"  search candidates added:  {conv_stats['candidates_added']}")
    log(f"  glass/state items added:  {state_stats['items_added']}")
    log(f"  glass keys copied:        {state_stats['glass_keys_copied']}")
    log(f"  workspaces merged:        {ws_stats['workspaces_merged']}")
    log(f"  workspace keys added:     {ws_stats['workspace_keys_added']}")
    log(f"  transcript files copied:  {transcript_stats['transcript_files_copied']}")

    if args.dry_run:
        log("")
        log("Dry-run complete. Re-run without --dry-run to apply changes.")
    else:
        log("")
        log("Done. Restart dCursor to see imported conversations.")
        log("Main Cursor was not modified. Your dCursor login/account data was not modified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
