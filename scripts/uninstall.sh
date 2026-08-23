#!/usr/bin/env bash
# Remove the dCursor package. User data is kept unless --purge-data is passed.
set -euo pipefail

PURGE_DATA=0
for arg in "$@"; do
	case "$arg" in
		--purge-data) PURGE_DATA=1 ;;
		-h | --help)
			echo "usage: uninstall.sh [--purge-data]"
			echo "  default: remove package only, keep ~/.config/dCursor and ~/.dcursor"
			echo "  --purge-data: also delete all dCursor chats, settings, and agent data"
			exit 0
			;;
	esac
done

echo "==> Stopping dCursor processes"
pkill -f '/usr/share/dcursor/dcursor' 2>/dev/null || true
sleep 1

echo "==> Removing dCursor package"
if dpkg -l dcursor >/dev/null 2>&1; then
	sudo dpkg --purge dcursor
else
	echo "    dcursor package not installed"
fi

if [ "$PURGE_DATA" -eq 1 ]; then
	echo "==> Removing user data"
	rm -rf \
		"${HOME}/.config/dCursor" \
		"${HOME}/.dcursor" \
		"${HOME}/.dcursor-server" \
		"${HOME}/.local/share/dcursor-agent" \
		"${HOME}/.cache/dcursor-launch.log"
	rm -f "${HOME}/.local/bin/dcursor-agent"
else
	echo "==> Keeping user data (~/.config/dCursor, ~/.dcursor)"
	echo "    To delete chats and settings too, run: $0 --purge-data"
fi

echo "==> Cleaning desktop entries (if any remain)"
sudo rm -f \
	/usr/bin/dcursor \
	/usr/share/applications/dcursor.desktop \
	/usr/share/applications/dcursor-url-handler.desktop \
	/usr/share/applications/dcursor-cursor-bridge.desktop \
	/etc/apparmor.d/dcursor-sandbox 2>/dev/null || true

if command -v xdg-mime >/dev/null 2>&1; then
	if [ -f /usr/share/applications/cursor-url-handler.desktop ]; then
		xdg-mime default cursor-url-handler.desktop x-scheme-handler/cursor 2>/dev/null || true
	fi
fi

if hash update-desktop-database 2>/dev/null; then
	update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo ""
echo "dCursor fully removed. Original Cursor is untouched."
