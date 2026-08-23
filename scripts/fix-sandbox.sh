#!/usr/bin/env bash
# Fix chrome-sandbox permissions required for dCursor to launch.
set -euo pipefail

SANDBOX="/usr/share/dcursor/chrome-sandbox"

if [ ! -f "$SANDBOX" ]; then
	echo "error: dCursor not installed ($SANDBOX missing)" >&2
	exit 1
fi

echo "Setting SUID sandbox permissions on $SANDBOX"
sudo chown root:root "$SANDBOX"
sudo chmod 4755 "$SANDBOX"
ls -la "$SANDBOX"
echo "Done. Try: dcursor"
