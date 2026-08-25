#!/usr/bin/env bash
# Import conversations from main Cursor into dCursor.
set -euo pipefail

APP_ROOT="/usr/share/dcursor"
SCRIPT="${APP_ROOT}/bin/dcursor-import-cursor-conversations.py"

if [ ! -f "$SCRIPT" ]; then
	ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
	SCRIPT="${ROOT_DIR}/scripts/dcursor-import-cursor-conversations.py"
fi

exec python3 "$SCRIPT" "$@"
