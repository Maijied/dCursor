#!/usr/bin/env bash
# Install or upgrade dCursor from a local .deb package.
# User data (~/.config/dCursor, ~/.dcursor) is preserved across upgrades.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB="${1:-${ROOT_DIR}/dist/dCursor.deb}"

if [ ! -f "$DEB" ]; then
	echo "error: package not found: $DEB" >&2
	echo "Run ./build.sh first or pass a .deb path." >&2
	exit 1
fi

if [ -d "${HOME}/.config/dCursor" ] || [ -d "${HOME}/.dcursor" ]; then
	echo "==> Existing dCursor data found — conversations and settings will be kept"
	bash "${ROOT_DIR}/scripts/dcursor-backup-user-data.sh"
fi

echo "==> Installing dCursor from: $DEB"
pkill -f '/usr/share/dcursor/dcursor' 2>/dev/null || true
sleep 1
sudo dpkg -i "$DEB"
sudo apt-get install -f -y 2>/dev/null || true

echo ""
echo "dCursor upgraded. Your chats are in ~/.config/dCursor (unchanged)."
echo "Launch with: dcursor"
