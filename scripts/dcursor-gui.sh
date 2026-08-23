#!/usr/bin/env sh
# GUI launcher for dCursor — prevents EPIPE when stdout/stderr are closed (desktop launch).
DCURSOR_APP_ROOT="/usr/share/dcursor"
ELECTRON="${DCURSOR_APP_ROOT}/dcursor"
SANDBOX="${DCURSOR_APP_ROOT}/chrome-sandbox"
LOG="${XDG_CACHE_HOME:-$HOME/.cache}/dcursor-launch.log"

if [ -f "$SANDBOX" ] && { [ ! -u "$SANDBOX" ] || [ "$(stat -c '%u' "$SANDBOX" 2>/dev/null || echo 1)" != "0" ]; }; then
	if command -v pkexec >/dev/null 2>&1; then
		pkexec /bin/sh -c "chown root:root '$SANDBOX' && chmod 4755 '$SANDBOX'" 2>/dev/null || true
	fi
fi

if [ -f "$SANDBOX" ] && { [ ! -u "$SANDBOX" ] || [ "$(stat -c '%u' "$SANDBOX" 2>/dev/null || echo 1)" != "0" ]; }; then
	export ELECTRON_DISABLE_SANDBOX=1
fi

mkdir -p "$(dirname "$LOG")"

# Desktop launchers close stdout/stderr; redirect to avoid write EPIPE in main process.
if [ -t 1 ]; then
	exec "$ELECTRON" "$@"
else
	exec "$ELECTRON" "$@" </dev/null >>"$LOG" 2>&1
fi
