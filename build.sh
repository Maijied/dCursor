#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDENTITY_FILE="${ROOT_DIR}/config/identity.json"
BUILD_DIR="${DCURSOR_BUILD_DIR:-/tmp/dcursor-build.$$}"
STAGING_DIR="${BUILD_DIR}/staging"
DIST_DIR="${ROOT_DIR}/dist"
CURSOR_SOURCE="${CURSOR_SOURCE:-/usr/share/cursor}"

die() {
	echo "error: $*" >&2
	exit 1
}

require_cmd() {
	command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

read_identity() {
	python3 -c "import json; print(json.load(open('${IDENTITY_FILE}'))['$1'])"
}

get_cursor_version() {
	if [ -n "${CURSOR_VERSION:-}" ]; then
		echo "$CURSOR_VERSION"
	elif dpkg -s cursor >/dev/null 2>&1; then
		dpkg-query -W -f='${Version}' cursor
	elif [ -n "${CURSOR_DEB:-}" ] && [ -f "$CURSOR_DEB" ]; then
		dpkg-deb -f "$CURSOR_DEB" Version
	else
		die "set CURSOR_VERSION or install cursor, or set CURSOR_DEB"
	fi
}

get_cursor_depends() {
	if [ -n "${CURSOR_DEPENDS:-}" ]; then
		echo "$CURSOR_DEPENDS"
	elif dpkg -s cursor >/dev/null 2>&1; then
		dpkg-query -W -f='${Depends}' cursor
	elif [ -n "${CURSOR_DEB:-}" ] && [ -f "$CURSOR_DEB" ]; then
		dpkg-deb -f "$CURSOR_DEB" Depends
	else
		die "set CURSOR_DEPENDS or install cursor, or set CURSOR_DEB"
	fi
}

export_icon_png() {
	local svg="${ROOT_DIR}/assets/co.anysphere.dcursor.svg"
	local out="${STAGING_DIR}/usr/share/pixmaps/co.anysphere.dcursor.png"

	if command -v rsvg-convert >/dev/null 2>&1; then
		rsvg-convert -w 512 -h 512 "$svg" -o "$out"
	elif command -v inkscape >/dev/null 2>&1; then
		inkscape "$svg" --export-type=png --export-filename="$out" -w 512 -h 512
	elif command -v convert >/dev/null 2>&1; then
		convert -background none "$svg" -resize 512x512 "$out"
	else
		die "need rsvg-convert, inkscape, or imagemagick to export icon PNG"
	fi
}

preflight() {
	require_cmd python3
	require_cmd dpkg-deb
	require_cmd cp
	require_cmd sed

	if [ ! -d "$CURSOR_SOURCE" ]; then
		die "cursor source not found at ${CURSOR_SOURCE}"
	fi

	if ! dpkg -s cursor >/dev/null 2>&1 && [ -z "${CURSOR_VERSION:-}" ]; then
		if [ -n "${CURSOR_DEB:-}" ] && [ -f "$CURSOR_DEB" ]; then
			export CURSOR_VERSION="$(dpkg-deb -f "$CURSOR_DEB" Version)"
			export CURSOR_DEPENDS="$(dpkg-deb -f "$CURSOR_DEB" Depends)"
		else
			die "cursor package is not installed; run scripts/ci-fetch-cursor.sh or install Cursor"
		fi
	fi
}

stage_cursor_tree() {
	echo "==> Staging Cursor tree"
	rm -rf "$STAGING_DIR"
	mkdir -p "${STAGING_DIR}/usr/share/dcursor"

	if cp -al "$CURSOR_SOURCE"/. "${STAGING_DIR}/usr/share/dcursor/" 2>/dev/null; then
		echo "    used hardlink copy (cp -al)"
	else
		echo "    hardlink copy unavailable (cross-device), using full copy (cp -a)"
		rm -rf "${STAGING_DIR}/usr/share/dcursor"
		mkdir -p "${STAGING_DIR}/usr/share/dcursor"
		cp -a "$CURSOR_SOURCE"/. "${STAGING_DIR}/usr/share/dcursor/"
	fi

	if [ -f "${STAGING_DIR}/usr/share/dcursor/cursor" ]; then
		mv "${STAGING_DIR}/usr/share/dcursor/cursor" "${STAGING_DIR}/usr/share/dcursor/dcursor"
	fi
}

patch_product_json() {
	echo "==> Patching product.json"
	python3 "${ROOT_DIR}/scripts/patch-product-json.py" \
		"$IDENTITY_FILE" \
		"${STAGING_DIR}/usr/share/dcursor/resources/app/product.json"
}

rewrite_paths_in_tree() {
	echo "==> Rewriting paths in bin scripts"
	local bin_dir="${STAGING_DIR}/usr/share/dcursor/bin"
	if [ -d "$bin_dir" ]; then
		for script in "$bin_dir"/*; do
			[ -f "$script" ] || continue
			if head -1 "$script" | grep -q '^#!'; then
				sed -i \
					-e 's|/usr/share/cursor|/usr/share/dcursor|g' \
					-e 's|\$VSCODE_PATH/cursor|\$VSCODE_PATH/dcursor|g' \
					"$script" 2>/dev/null || true
			fi
		done
	fi
}

install_launcher_and_bins() {
	echo "==> Installing launcher and bin scripts"
	mkdir -p "${STAGING_DIR}/usr/share/dcursor/bin"
	install -m 755 "${ROOT_DIR}/scripts/dcursor-launcher.sh" "${STAGING_DIR}/usr/share/dcursor/bin/dcursor"

	rm -f "${STAGING_DIR}/usr/share/dcursor/bin/cursor"

	if [ -f "${STAGING_DIR}/usr/share/dcursor/bin/cursor-tunnel" ]; then
		sed \
			-e 's|/usr/share/cursor|/usr/share/dcursor|g' \
			-e 's|cursor-tunnel|dcursor-tunnel|g' \
			-e 's|\$VSCODE_PATH/cursor|\$VSCODE_PATH/dcursor|g' \
			"${STAGING_DIR}/usr/share/dcursor/bin/cursor-tunnel" \
			> "${STAGING_DIR}/usr/share/dcursor/bin/dcursor-tunnel"
		chmod 755 "${STAGING_DIR}/usr/share/dcursor/bin/dcursor-tunnel"
		rm -f "${STAGING_DIR}/usr/share/dcursor/bin/cursor-tunnel" \
			"${STAGING_DIR}/usr/share/dcursor/bin/code-tunnel"
	fi
}

install_system_files() {
	echo "==> Installing desktop, apparmor, mime, and icon files"
	mkdir -p \
		"${STAGING_DIR}/usr/share/applications" \
		"${STAGING_DIR}/usr/share/pixmaps" \
		"${STAGING_DIR}/usr/share/appdata" \
		"${STAGING_DIR}/usr/share/mime/packages" \
		"${STAGING_DIR}/usr/share/bash-completion/completions" \
		"${STAGING_DIR}/etc/apparmor.d"

	install -m 644 "${ROOT_DIR}/assets/dcursor.desktop" "${STAGING_DIR}/usr/share/applications/dcursor.desktop"
	install -m 644 "${ROOT_DIR}/assets/dcursor-url-handler.desktop" "${STAGING_DIR}/usr/share/applications/dcursor-url-handler.desktop"
	install -m 644 "${ROOT_DIR}/assets/dcursor.appdata.xml" "${STAGING_DIR}/usr/share/appdata/dcursor.appdata.xml"
	install -m 644 "${ROOT_DIR}/assets/dcursor-workspace.xml" "${STAGING_DIR}/usr/share/mime/packages/dcursor-workspace.xml"
	install -m 644 "${ROOT_DIR}/assets/dcursor-sandbox" "${STAGING_DIR}/etc/apparmor.d/dcursor-sandbox"
	install -m 644 "${ROOT_DIR}/assets/dcursor.bash-completion" "${STAGING_DIR}/usr/share/bash-completion/completions/dcursor"

	if [ -f "${STAGING_DIR}/usr/share/dcursor/chrome-sandbox" ]; then
		chmod 4755 "${STAGING_DIR}/usr/share/dcursor/chrome-sandbox"
	fi

	export_icon_png
}

write_control_file() {
	echo "==> Writing DEBIAN/control"
	local cursor_version cursor_depends package_name version_suffix dcursor_version
	package_name="$(read_identity packageName)"
	version_suffix="$(read_identity versionSuffix)"
	cursor_version="$(get_cursor_version)"
	cursor_depends="$(get_cursor_depends)"
	dcursor_version="${cursor_version}.${version_suffix}"

	mkdir -p "${STAGING_DIR}/DEBIAN"
	cat > "${STAGING_DIR}/DEBIAN/control" <<EOF
Package: ${package_name}
Version: ${dcursor_version}
Section: editors
Priority: optional
Architecture: amd64
Depends: ${cursor_depends}
Maintainer: Lorapok Labs <mdshuvo40@gmail.com>
Homepage: https://github.com/Maijied/dCursor
Description: dCursor - isolated mirror of Cursor IDE
 Standalone mirror of Cursor for running a separate account alongside
 the original install. Uses ~/.dcursor and ~/.config/dCursor for data.
EOF

	install -m 755 "${ROOT_DIR}/debian/postinst" "${STAGING_DIR}/DEBIAN/postinst"
	install -m 755 "${ROOT_DIR}/debian/prerm" "${STAGING_DIR}/DEBIAN/prerm"
	install -m 755 "${ROOT_DIR}/debian/postrm" "${STAGING_DIR}/DEBIAN/postrm"
	chmod 755 "${STAGING_DIR}/DEBIAN"
	chmod 644 "${STAGING_DIR}/DEBIAN/control"
}

build_deb() {
	echo "==> Building .deb package"
	mkdir -p "$DIST_DIR"

	local package_name version_suffix dcursor_version deb_name
	package_name="$(read_identity packageName)"
	version_suffix="$(read_identity versionSuffix)"
	cursor_version="$(get_cursor_version)"
	dcursor_version="${cursor_version}.${version_suffix}"
	deb_name="dCursor_${dcursor_version}_amd64.deb"

	dpkg-deb --root-owner-group --build "$STAGING_DIR" "${DIST_DIR}/${deb_name}"
	ln -sf "${deb_name}" "${DIST_DIR}/dCursor.deb"

	echo ""
	echo "Built: ${DIST_DIR}/${deb_name}"
	echo "Symlink: ${DIST_DIR}/dCursor.deb"
	echo "Install: sudo dpkg -i ${DIST_DIR}/dCursor.deb"
}

cleanup() {
	if [ -n "${BUILD_DIR:-}" ] && [ "${BUILD_DIR#${ROOT_DIR}/build}" = "$BUILD_DIR" ]; then
		rm -rf "$BUILD_DIR"
	fi
}

main() {
	trap cleanup EXIT
	preflight
	stage_cursor_tree
	patch_product_json
	rewrite_paths_in_tree
	install_launcher_and_bins
	install_system_files
	write_control_file
	build_deb
}

main "$@"
