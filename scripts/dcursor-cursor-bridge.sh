#!/usr/bin/env sh
# Routes cursor:// callbacks to dCursor when a GitHub connect flow is active there,
# otherwise forwards to the original Cursor install.
set -eu

url="${1:-}"
if [ -z "$url" ]; then
	echo "usage: dcursor-cursor-bridge <url>" >&2
	exit 1
fi

DCURSOR_GUI="/usr/share/dcursor/bin/dcursor-gui"
CURSOR_GUI="/usr/share/cursor/bin/cursor"

dcursor_pending_github_connect() {
	local db="${HOME}/.config/dCursor/User/globalStorage/state.vscdb"
	[ -f "$db" ] || return 1
	grep -q 'cursor/glass.githubConnect.pendingFlow' "$db" 2>/dev/null
}

route_to_dcursor() {
	local target="$1"
	case "$target" in
		cursor://*)
			target="dcursor://${target#cursor://}"
			;;
	esac
	if [ -x "$DCURSOR_GUI" ]; then
		exec "$DCURSOR_GUI" --open-url "$target"
	fi
	echo "error: dCursor is not installed (${DCURSOR_GUI})" >&2
	exit 1
}

route_to_cursor() {
	if [ -x "$CURSOR_GUI" ]; then
		exec "$CURSOR_GUI" --open-url "$url"
	fi
	echo "error: Cursor is not installed (${CURSOR_GUI})" >&2
	exit 1
}

if dcursor_pending_github_connect; then
	route_to_dcursor "$url"
fi

route_to_cursor
