#!/usr/bin/env bash
# Post-build audit: dCursor isolation and branding integrity.
set -euo pipefail

APP_ROOT="${1:-}"
if [ -z "$APP_ROOT" ] || [ ! -d "$APP_ROOT" ]; then
	echo "usage: $0 <app_root>" >&2
	echo "  e.g. $0 /tmp/dcursor-build/staging/usr/share/dcursor" >&2
	exit 1
fi

fail() {
	echo "audit FAIL: $*" >&2
	exit 1
}

pass() {
	echo "audit OK: $*"
}

require_cmd() {
	command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

PRODUCT="${APP_ROOT}/resources/app/product.json"
[ -f "$PRODUCT" ] || fail "missing product.json"

require_cmd python3
require_cmd identify

python3 - <<PY || fail "product.json identity fields incorrect"
import json, sys
p = json.load(open("${PRODUCT}"))
assert p.get("dataFolderName") == ".dcursor", p.get("dataFolderName")
assert p.get("urlProtocol") == "dcursor", p.get("urlProtocol")
assert p.get("linuxIconName") == "co.anysphere.dcursor", p.get("linuxIconName")
print("identity fields OK")
PY

SPLASH_MEDIA="${APP_ROOT}/resources/app/out/vs/glass/browser/media"
for f in cursor-splash-logo-normal.png cursor-splash-logo-glass.png; do
	path="${SPLASH_MEDIA}/${f}"
	[ -f "$path" ] || fail "missing splash PNG: $path"
	dims="$(identify -format '%wx%h' "$path" 2>/dev/null || true)"
	[ "$dims" = "421x480" ] || fail "splash PNG $f is $dims, expected 421x480"
	pass "splash PNG $f is 421x480"
done

CODE_PNG="${APP_ROOT}/resources/app/resources/linux/code.png"
[ -f "$CODE_PNG" ] || fail "missing code.png"
code_dims="$(identify -format '%wx%h' "$CODE_PNG" 2>/dev/null || true)"
[ "$code_dims" = "512x512" ] || fail "code.png is $code_dims, expected 512x512"
pass "app icon code.png is 512x512"

EARLY_JS="${APP_ROOT}/resources/app/out/vs/code/electron-sandbox/workbench/workbench.js"
[ -f "$EARLY_JS" ] || fail "missing early splash workbench.js"
grep -q 'width: 72px' "$EARLY_JS" || fail "early splash CSS not patched (expected 72px width)"
pass "early splash CSS patched to 72px"

if command -v ffprobe >/dev/null 2>&1; then
	for theme in dark light; do
		webm="${SPLASH_MEDIA}/cursor-logo-for-${theme}-theme.webm"
		[ -f "$webm" ] || fail "missing splash WEBM: $webm"
		[ "$(stat -c%s "$webm")" -gt 10000 ] || fail "splash WEBM too small: $webm"
		dims="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$webm" 2>/dev/null || true)"
		[ "$dims" = "640,700" ] || fail "WEBM $theme is $dims, expected 640,700"
		pass "splash WEBM $theme is 640x700"
	done
else
	echo "audit WARN: ffprobe not found, skipping WEBM dimension checks"
fi

if command -v rg >/dev/null 2>&1; then
	leaks="$(rg -l 'homedir\(\)\,"\.cursor"' "${APP_ROOT}/resources/app/out" 2>/dev/null || true)"
	if [ -n "$leaks" ]; then
		fail "found unpatched .cursor homedir paths in:\n$leaks"
	fi
	broken="$(rg -l 'homedir\(\)\)\,"\.dcursor"' "${APP_ROOT}/resources/app/out" 2>/dev/null || true)"
	if [ -n "$broken" ]; then
		fail "found broken homedir())),\".dcursor\" patch in:\n$broken"
	fi
	pass "no leaked homedir .cursor paths in bundled JS"
else
	echo "audit WARN: rg not found, skipping JS leak scan"
fi

BRIDGE_BIN="${APP_ROOT}/bin/dcursor-cursor-bridge"
IMPORT_PY="${APP_ROOT}/bin/dcursor-import-cursor-conversations.py"
leaked_bins=0
if [ -d "${APP_ROOT}/bin" ]; then
	for script in "${APP_ROOT}"/bin/*; do
		[ -f "$script" ] || continue
		case "$script" in
			"$BRIDGE_BIN" | "$IMPORT_PY" | *.py) continue ;;
		esac
		if grep -q '/usr/share/cursor' "$script" 2>/dev/null; then
			echo "audit FAIL: $script references /usr/share/cursor" >&2
			leaked_bins=1
		fi
	done
fi
[ "$leaked_bins" -eq 0 ] || exit 1
pass "launcher scripts use dcursor install prefix (bridge/import exempt)"

EXT_HOST="${APP_ROOT}/resources/app/out/vs/workbench/api/node/extensionHostProcess.js"
[ -f "$EXT_HOST" ] || fail "missing extensionHostProcess.js"
python3 - <<PY || fail "extension integrity hashes do not match bundled files"
import hashlib, json, re, subprocess, sys
from pathlib import Path

app_root = Path("${APP_ROOT}")
ext_host = app_root / "resources/app/out/vs/workbench/api/node/extensionHostProcess.js"
text = ext_host.read_text(encoding="utf-8")
marker = "var qne={"
idx = text.find(marker)
if idx < 0:
    raise SystemExit("integrity manifest missing")
start = idx + len("var qne=")
depth = 0
for i in range(start, len(text)):
    ch = text[i]
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            manifest_text = text[start : i + 1]
            break
else:
    raise SystemExit("integrity manifest unterminated")

manifest = json.loads(
    subprocess.check_output(
        ["node", "-e", f"console.log(JSON.stringify({manifest_text}))"],
        text=True,
    )
)
extensions_root = app_root / "resources/app/extensions"
errors = []

def walk(ext_dir, node, parts=()):
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if (
            isinstance(value, str)
            and len(value) == 64
            and all(c in "0123456789abcdef" for c in value)
        ):
            rel = Path(*parts, key)
            target = extensions_root / ext_dir / rel
            if not target.exists():
                errors.append(f"missing {target}")
                continue
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != value:
                errors.append(f"hash mismatch for {ext_dir}/{rel}")
        else:
            walk(ext_dir, value, parts + (key,))

for ext_id, tree in manifest.items():
    if "." not in ext_id:
        continue
    walk(ext_id.split(".", 1)[1], tree)

if errors:
    print("\\n".join(errors[:20]), file=sys.stderr)
    raise SystemExit(1)
print("extension integrity hashes OK")
PY
pass "extension integrity hashes match bundled files"

echo "audit complete: all checks passed"
