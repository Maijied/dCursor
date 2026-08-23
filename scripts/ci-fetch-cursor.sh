#!/usr/bin/env bash
# Fetch the latest Cursor .deb for CI builds.
set -euo pipefail

OUTPUT_DEB="${1:-/tmp/cursor.deb}"
EXTRACT_DIR="${2:-/tmp/cursor-extract}"

require_cmd() {
	command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }
}

require_cmd curl
require_cmd jq
require_cmd dpkg-deb

echo "==> Resolving latest Cursor .deb download URL"
RESPONSE="$(curl -fsSL "https://www.cursor.com/api/download?platform=linux-x64&releaseTrack=stable")"
DEB_URL="$(echo "$RESPONSE" | jq -r '.debUrl // empty')"

if [ -z "$DEB_URL" ] || [ "$DEB_URL" = "null" ]; then
	APP_URL="$(echo "$RESPONSE" | jq -r '.downloadUrl')"
	DEB_URL="${APP_URL/\/appimage\//\/deb\/amd64\/deb\/}"
	DEB_URL="${DEB_URL/appimage/deb}"
fi

echo "    Deb URL: $DEB_URL"
curl -fsSL "$DEB_URL" -o "$OUTPUT_DEB"
echo "==> Downloaded Cursor package to $OUTPUT_DEB"

rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
dpkg-deb -x "$OUTPUT_DEB" "$EXTRACT_DIR"

if [ ! -d "$EXTRACT_DIR/usr/share/cursor" ]; then
	echo "error: extracted package missing usr/share/cursor" >&2
	exit 1
fi

PKG_VERSION="$(dpkg-deb -f "$OUTPUT_DEB" Version)"
PKG_DEPENDS="$(dpkg-deb -f "$OUTPUT_DEB" Depends)"

echo "==> Cursor version: $PKG_VERSION"

if [ -n "${GITHUB_ENV:-}" ]; then
	{
		echo "CURSOR_SOURCE=$EXTRACT_DIR/usr/share/cursor"
		echo "CURSOR_DEB=$OUTPUT_DEB"
		echo "CURSOR_VERSION=$PKG_VERSION"
		echo "CURSOR_DEPENDS<<EOF"
		echo "$PKG_DEPENDS"
		echo "EOF"
	} >> "$GITHUB_ENV"
fi

export CURSOR_SOURCE="$EXTRACT_DIR/usr/share/cursor"
export CURSOR_DEB="$OUTPUT_DEB"
export CURSOR_VERSION="$PKG_VERSION"
export CURSOR_DEPENDS="$PKG_DEPENDS"
