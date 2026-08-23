#!/usr/bin/env bash
# Install dCursor from a local or downloaded .deb package.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB="${1:-${ROOT_DIR}/dist/dCursor.deb}"

if [ ! -f "$DEB" ]; then
	echo "error: package not found: $DEB" >&2
	echo "Run ./build.sh first or pass a .deb path." >&2
	exit 1
fi

echo "Installing dCursor from: $DEB"
sudo dpkg -i "$DEB"
sudo apt-get install -f -y 2>/dev/null || true

echo ""
echo "dCursor installed. Launch with: dcursor"
