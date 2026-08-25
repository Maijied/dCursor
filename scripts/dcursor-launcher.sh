#!/usr/bin/env sh
#
# dCursor launcher - isolated mirror of Cursor IDE and agent.

DCURSOR_APP_ROOT="/usr/share/dcursor"
. "${DCURSOR_APP_ROOT}/bin/dcursor-launch-env.sh"
dcursor_prepare_launch_env
DCURSOR_CONFIG_DIR="${HOME}/.config/dCursor"
DCURSOR_DATA_DIR="${HOME}/.dcursor"
DCURSOR_AGENT_DATA_DIR="${HOME}/.local/share/dcursor-agent"
DCURSOR_AGENT_BIN="${HOME}/.local/bin/dcursor-agent"

ensure_chrome_sandbox() {
	SANDBOX="${DCURSOR_APP_ROOT}/chrome-sandbox"
	[ -f "$SANDBOX" ] || return 0

	# Electron requires root-owned SUID sandbox (mode 4755)
	if [ -u "$SANDBOX" ] && [ "$(stat -c '%u' "$SANDBOX" 2>/dev/null || echo 1)" = "0" ]; then
		return 0
	fi

	if command -v pkexec >/dev/null 2>&1; then
		pkexec /bin/sh -c "chown root:root '$SANDBOX' && chmod 4755 '$SANDBOX'" 2>/dev/null \
			&& [ -u "$SANDBOX" ] && return 0
	fi

	echo "dCursor: chrome-sandbox not configured; launching without sandbox." 1>&2
	echo "Fix permanently: sudo chmod 4755 $SANDBOX" 1>&2
	export ELECTRON_DISABLE_SANDBOX=1
}

find_dcursor_cli() {
	CURSOR_CLI=""
	CURSOR_CLI_MODE=""

	if [ -n "$VSCODE_IPC_HOOK_CLI" ]; then
		REMOTE_CLI="$(which -a 'dcursor' 2>/dev/null | grep /remote-cli/ || true)"
		if [ -n "$REMOTE_CLI" ]; then
			CURSOR_CLI="$REMOTE_CLI"
			CURSOR_CLI_MODE="remote"
			return 0
		fi
	fi

	VSCODE_PATH="$DCURSOR_APP_ROOT"
	ELECTRON="$VSCODE_PATH/dcursor"
	CLI="$VSCODE_PATH/resources/app/out/cli.js"

	if [ -x "$ELECTRON" ] && [ -f "$CLI" ]; then
		CURSOR_CLI_MODE="local"
		return 0
	fi

	return 1
}

use_dcursor_cli() {
	if [ "$CURSOR_CLI_MODE" = "remote" ]; then
		exec "$CURSOR_CLI" "$@"
	fi

	ELECTRON_RUN_AS_NODE=1 exec "$ELECTRON" "$CLI" "$@"
}

launch_dcursor_gui() {
	# Desktop launchers close stdout/stderr; redirect when not a terminal to avoid EPIPE.
	if [ -t 1 ]; then
		exec "$ELECTRON" "$@"
	fi

	LOG="${XDG_CACHE_HOME:-$HOME/.cache}/dcursor-launch.log"
	mkdir -p "$(dirname "$LOG")"
	exec "$ELECTRON" "$@" </dev/null >>"$LOG" 2>&1
}

needs_cli_bridge() {
	case "${1:-}" in
		-v | --version | -h | --help | --list-extensions | --show-versions | \
		--install-extension | --install-builtin-extension | --uninstall-extension | \
		--update-extensions | --locate-extension | --add-mcp | --diff | -d | \
		--merge | -m | status | tunnel | serve-web)
			return 0
			;;
	esac
	return 1
}

ensure_dcursor_agent() {
	if [ -x "$DCURSOR_AGENT_BIN" ]; then
		return 0
	fi

	mkdir -p "${HOME}/.local/bin" "${DCURSOR_AGENT_DATA_DIR}"

	seed_agent_from_cursor() {
		if [ "${DCURSOR_SEED_AGENT_FROM_CURSOR:-0}" != "1" ]; then
			return 1
		fi
		if [ ! -d "${HOME}/.local/share/cursor-agent/versions" ]; then
			return 1
		fi
		echo "Seeding dcursor-agent from cursor-agent (opt-in copy)..."
		cp -a "${HOME}/.local/share/cursor-agent/." "${DCURSOR_AGENT_DATA_DIR}/"
		return 0
	}

	if seed_agent_from_cursor; then
		:
	elif command -v bash >/dev/null 2>&1 && command -v curl >/dev/null 2>&1; then
		echo "Installing dcursor-agent (isolated)..."
		CURSOR_DATA_DIR="$DCURSOR_AGENT_DATA_DIR" \
			CURSOR_CONFIG_DIR="$DCURSOR_CONFIG_DIR" \
			curl -sS https://cursor.com/install | bash >/dev/null 2>&1
		if command -v tput >/dev/null 2>&1; then
			tput cuu1 && tput el
		fi
	fi

	AGENT_VERSION_DIR=""
	if [ -d "${DCURSOR_AGENT_DATA_DIR}/versions" ]; then
		AGENT_VERSION_DIR="$(ls -1 "${DCURSOR_AGENT_DATA_DIR}/versions" 2>/dev/null | tail -1)"
	fi

	if [ -n "$AGENT_VERSION_DIR" ] && [ -x "${DCURSOR_AGENT_DATA_DIR}/versions/${AGENT_VERSION_DIR}/cursor-agent" ]; then
		ln -sf "${DCURSOR_AGENT_DATA_DIR}/versions/${AGENT_VERSION_DIR}/cursor-agent" "$DCURSOR_AGENT_BIN"
		return 0
	fi

	return 1
}

run_dcursor_agent() {
	export CURSOR_CONFIG_DIR="$DCURSOR_CONFIG_DIR"
	export CURSOR_DATA_DIR="$DCURSOR_DATA_DIR"
	export CURSOR_AGENT_DATA_DIR="$DCURSOR_AGENT_DATA_DIR"
	export CURSOR_INVOKED_AS="dcursor-agent"
	unset CURSOR_CLI
	unset CURSOR_CLI_MODE

	if ! ensure_dcursor_agent; then
		echo "Error: Could not install dcursor-agent." 1>&2
		echo "Install cursor-agent first with 'cursor agent', or run:" 1>&2
		echo "  curl -sS https://cursor.com/install | bash" 1>&2
		exit 1
	fi

	OUTPUT=$({ "$DCURSOR_AGENT_BIN" --min-version=2025.10.01 status; } 2>&1)
	EXIT_CODE=$?

	if { [ "$EXIT_CODE" -eq 2 ] || { [ "$EXIT_CODE" -eq 1 ] && echo "$OUTPUT" | grep -qi "unknown option"; }; }; then
		echo "dcursor-agent version is outdated, updating..."
		"$DCURSOR_AGENT_BIN" update >/dev/null 2>&1
		if command -v tput >/dev/null 2>&1; then
			tput cuu1 && tput el
		fi
	fi

	export CURSOR_CLI_COMPAT=1
	exec "$DCURSOR_AGENT_BIN" "$@"
}

if grep -qi Microsoft /proc/version 2>/dev/null && [ -z "$DONT_PROMPT_WSL_INSTALL" ]; then
	echo "To use dCursor with WSL, install dCursor in Windows." 1>&2
	printf "Continue anyway? [y/N] " 1>&2
	read -r YN
	YN=$(printf '%s' "$YN" | tr '[:upper:]' '[:lower:]')
	case "$YN" in
		y | yes) ;;
		*) exit 1 ;;
	esac
fi

if [ "$(id -u)" = "0" ]; then
	for i in "$@"; do
		case "$i" in
			--user-data-dir | --user-data-dir=* | --file-write | tunnel)
				CAN_LAUNCH_AS_ROOT=1
				;;
		esac
	done
	if [ -z "$CAN_LAUNCH_AS_ROOT" ]; then
		echo "Do not run dCursor as root without --user-data-dir." 1>&2
		exit 1
	fi
fi

export VSCODE_NODE_OPTIONS=$NODE_OPTIONS
export VSCODE_NODE_REPL_EXTERNAL_MODULE=$NODE_REPL_EXTERNAL_MODULE
unset NODE_OPTIONS
unset NODE_REPL_EXTERNAL_MODULE
unset CURSOR_CLI
unset CURSOR_CLI_MODE

if [ "$1" = "agent" ] && [ "$CURSOR_CLI_BLOCK_CURSOR_AGENT" != "true" ]; then
	shift
	run_dcursor_agent "$@"
fi

if [ "$1" = "import-conversations" ] || [ "$1" = "import-from-cursor" ]; then
	shift
	exec "${DCURSOR_APP_ROOT}/bin/dcursor-import-cursor-conversations.sh" "$@"
fi

if ! find_dcursor_cli; then
	echo "Error: dCursor CLI not found. Is dcursor installed?" 1>&2
	exit 1
fi

ensure_chrome_sandbox

if [ "$1" = "editor" ]; then
	shift
fi

if needs_cli_bridge "$@"; then
	use_dcursor_cli "$@"
else
	launch_dcursor_gui "$@"
fi
