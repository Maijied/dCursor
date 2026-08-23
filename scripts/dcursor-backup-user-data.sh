#!/usr/bin/env bash
# Backup dCursor chat/state databases before upgrades.
set -euo pipefail

DCURSOR_CONFIG="${HOME}/.config/dCursor"
DCURSOR_DATA="${HOME}/.dcursor"
BACKUP_ROOT="${DCURSOR_DATA}/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${STAMP}"

backup_file() {
	local src="$1"
	local name="$2"
	if [ -f "$src" ]; then
		cp -a "$src" "${BACKUP_DIR}/${name}"
		echo "  backed up ${name}"
	fi
}

if [ ! -d "$DCURSOR_CONFIG" ] && [ ! -d "$DCURSOR_DATA" ]; then
	echo "No existing dCursor data found; skipping backup."
	exit 0
fi

mkdir -p "$BACKUP_DIR"
echo "==> Backing up dCursor user data to ${BACKUP_DIR}"

backup_file "${DCURSOR_CONFIG}/User/globalStorage/state.vscdb" "state.vscdb"
backup_file "${DCURSOR_CONFIG}/User/globalStorage/state.vscdb-wal" "state.vscdb-wal"
backup_file "${DCURSOR_CONFIG}/User/globalStorage/state.vscdb-shm" "state.vscdb-shm"
backup_file "${DCURSOR_CONFIG}/User/globalStorage/conversation-search.db" "conversation-search.db"
backup_file "${DCURSOR_CONFIG}/User/globalStorage/conversation-search.db-wal" "conversation-search.db-wal"
backup_file "${DCURSOR_CONFIG}/User/globalStorage/conversation-search.db-shm" "conversation-search.db-shm"
backup_file "${DCURSOR_CONFIG}/User/settings.json" "settings.json"

if [ -d "${DCURSOR_CONFIG}/User/workspaceStorage" ]; then
	cp -a "${DCURSOR_CONFIG}/User/workspaceStorage" "${BACKUP_DIR}/workspaceStorage"
	echo "  backed up workspaceStorage/"
fi

# Keep the five most recent backups.
if [ -d "$BACKUP_ROOT" ]; then
	ls -1dt "${BACKUP_ROOT}"/* 2>/dev/null | tail -n +6 | xargs -r rm -rf
fi

echo "Backup complete."
