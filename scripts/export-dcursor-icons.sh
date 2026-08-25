#!/usr/bin/env bash
# Export dCursor PNG assets from Lorapok Instar SVG sources.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="${ROOT_DIR}/assets"
OUT_DIR="${1:-${ASSETS}}"

render_png() {
	local svg="$1"
	local width="$2"
	local height="$3"
	local dest="$4"
	if command -v rsvg-convert >/dev/null 2>&1; then
		rsvg-convert -w "$width" -h "$height" "$svg" -o "$dest"
	elif command -v inkscape >/dev/null 2>&1; then
		inkscape "$svg" --export-type=png --export-filename="$dest" -w "$width" -h "$height"
	elif command -v convert >/dev/null 2>&1; then
		convert -background none "$svg" -resize "${width}x${height}" "$dest"
	else
		echo "error: need rsvg-convert, inkscape, or imagemagick" >&2
		exit 1
	fi
}

mkdir -p "$OUT_DIR"

render_png "${ASSETS}/co.anysphere.dcursor.svg" 512 512 "${OUT_DIR}/co.anysphere.dcursor.png"
render_png "${ASSETS}/co.anysphere.dcursor.svg" 421 480 "${OUT_DIR}/co.anysphere.dcursor-splash.png"
render_png "${ASSETS}/dcursor-logo-mark.svg" 512 512 "${OUT_DIR}/dcursor-logo-mark.png"
render_png "${ASSETS}/dcursor-lockup-dark.svg" 640 160 "${OUT_DIR}/dcursor-lockup-dark.png"
render_png "${ASSETS}/dcursor-lockup-light.svg" 640 160 "${OUT_DIR}/dcursor-lockup-light.png"
render_png "${ASSETS}/co.anysphere.dcursor.svg" 256 256 "${OUT_DIR}/dcursor-logo-256.png"
render_png "${ASSETS}/co.anysphere.dcursor.svg" 128 128 "${OUT_DIR}/dcursor-logo-128.png"
render_png "${ASSETS}/co.anysphere.dcursor.svg" 96 96 "${OUT_DIR}/dcursor-logo-96.png"
render_png "${ASSETS}/co.anysphere.dcursor.svg" 64 64 "${OUT_DIR}/dcursor-logo-64.png"
render_png "${ASSETS}/co.anysphere.dcursor.svg" 32 32 "${OUT_DIR}/dcursor-logo-32.png"

echo "Exported dCursor icons to ${OUT_DIR}"
