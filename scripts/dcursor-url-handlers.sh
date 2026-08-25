#!/usr/bin/env bash
# Manage x-scheme-handler defaults for Cursor vs dCursor.
set -euo pipefail

usage() {
	cat <<'EOF'
Usage: dcursor-url-handlers.sh <command>

Commands:
  restore-cursor   Point cursor:// back to main Cursor (recommended default)
  enable-bridge    Route cursor:// through dCursor bridge (GitHub OAuth in dCursor)
  status           Show current cursor:// and dcursor:// handlers
EOF
}

require_xdg() {
	command -v xdg-mime >/dev/null 2>&1 || {
		echo "error: xdg-mime not found" >&2
		exit 1
	}
}

show_status() {
	require_xdg
	echo "cursor:// -> $(xdg-mime query default x-scheme-handler/cursor 2>/dev/null || echo unknown)"
	echo "dcursor:// -> $(xdg-mime query default x-scheme-handler/dcursor 2>/dev/null || echo unknown)"
}

restore_cursor() {
	require_xdg
	if [ -f /usr/share/applications/cursor-url-handler.desktop ]; then
		xdg-mime default cursor-url-handler.desktop x-scheme-handler/cursor
		echo "Restored cursor:// handler to main Cursor."
	else
		echo "error: cursor-url-handler.desktop not found" >&2
		exit 1
	fi
	if [ -f /usr/share/applications/dcursor-url-handler.desktop ]; then
		xdg-mime default dcursor-url-handler.desktop x-scheme-handler/dcursor 2>/dev/null || true
	fi
}

enable_bridge() {
	require_xdg
	if [ ! -f /usr/share/applications/dcursor-cursor-bridge.desktop ]; then
		echo "error: dcursor-cursor-bridge.desktop not found" >&2
		exit 1
	fi
	xdg-mime default dcursor-cursor-bridge.desktop x-scheme-handler/cursor
	xdg-mime default dcursor-url-handler.desktop x-scheme-handler/dcursor 2>/dev/null || true
	echo "Enabled dCursor cursor:// bridge."
	echo "warning: this can break profile/auth when Cursor and dCursor run together."
}

cmd="${1:-status}"
case "$cmd" in
	restore-cursor) restore_cursor ;;
	enable-bridge) enable_bridge ;;
	status) show_status ;;
	-h | --help | help) usage ;;
	*) usage >&2; exit 1 ;;
esac

show_status
