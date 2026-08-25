# Shared launch environment for dCursor GUI/CLI entrypoints.

dcursor_prepare_launch_env() {
	: "${HOME:=$(getent passwd "${USER:-$(id -un)}" 2>/dev/null | cut -d: -f6)}"

	# Keep dCursor fully isolated from ~/.cursor and ~/.config/Cursor.
	export CURSOR_DATA_DIR="${CURSOR_DATA_DIR:-${HOME}/.dcursor}"
	export CURSOR_CONFIG_DIR="${CURSOR_CONFIG_DIR:-${HOME}/.config/dCursor}"
	mkdir -p "${CURSOR_DATA_DIR}" "${CURSOR_DATA_DIR}/sandbox-policies" "${CURSOR_CONFIG_DIR}"

	# GNOME uses WM_CLASS + .desktop to pick the running app icon.
	export GTK_APPLICATION_ID="${GTK_APPLICATION_ID:-co.anysphere.dcursor}"
	export CHROME_DESKTOP="${CHROME_DESKTOP:-dcursor.desktop}"
	export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-}}"
	: "${USER:=$(id -un)}"
	: "${LOGNAME:=$USER}"
	: "${SHELL:=$(command -v bash 2>/dev/null || command -v zsh 2>/dev/null || echo /bin/sh)}"
	if [ -z "${PATH:-}" ]; then
		export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
	fi
	if [ -z "${LANG:-}" ] && [ -r /etc/default/locale ]; then
		# shellcheck disable=SC1091
		. /etc/default/locale 2>/dev/null || true
	fi

	# Electron probes $SHELL to build the integrated terminal environment.
	# Slow interactive zsh configs often time out when launched from a .desktop file.
	if [ -z "${DCURSOR_KEEP_SHELL:-}" ] && [ -x /bin/bash ] && [ "${SHELL##*/}" = "zsh" ]; then
		export SHELL=/bin/bash
	fi

	DCURSOR_ARGV="${HOME}/.dcursor/argv.json"
	if [ ! -f "$DCURSOR_ARGV" ]; then
		mkdir -p "${HOME}/.dcursor"
		cat >"$DCURSOR_ARGV" <<'EOF'
{
	"enable-crash-reporter": false
}
EOF
	fi
}
