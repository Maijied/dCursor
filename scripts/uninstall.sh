#!/usr/bin/env bash
# Completely remove dCursor system package and all user data.
set -euo pipefail

echo "==> Stopping dCursor processes"
pkill -f '/usr/share/dcursor/dcursor' 2>/dev/null || true
sleep 1

echo "==> Removing dCursor package"
if dpkg -l dcursor >/dev/null 2>&1; then
	sudo dpkg --purge dcursor
else
	echo "    dcursor package not installed"
fi

echo "==> Removing user data"
rm -rf \
	"${HOME}/.config/dCursor" \
	"${HOME}/.dcursor" \
	"${HOME}/.dcursor-server" \
	"${HOME}/.local/share/dcursor-agent" \
	"${HOME}/.cache/dcursor-launch.log"

rm -f "${HOME}/.local/bin/dcursor-agent"

echo "==> Cleaning desktop entries (if any remain)"
sudo rm -f \
	/usr/bin/dcursor \
	/usr/share/applications/dcursor.desktop \
	/usr/share/applications/dcursor-url-handler.desktop \
	/etc/apparmor.d/dcursor-sandbox 2>/dev/null || true

if hash update-desktop-database 2>/dev/null; then
	update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo ""
echo "dCursor fully removed. Original Cursor is untouched."
