#!/usr/bin/env python3
"""Patch Cursor branding in product.json and bundled UI assets."""

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path


FIELD_MAP = {
    "nameShort": "displayName",
    "nameLong": "displayNameLong",
    "applicationName": "applicationName",
    "dataFolderName": "dataFolderName",
    "serverDataFolderName": "serverDataFolderName",
    "serverApplicationName": "serverApplicationName",
    "tunnelApplicationName": "tunnelApplicationName",
    "linuxIconName": "linuxIconName",
    "urlProtocol": "urlProtocol",
    "win32MutexName": "win32MutexName",
    "win32DirName": "win32DirName",
    "win32NameVersion": "win32NameVersion",
    "win32RegValueName": "win32RegValueName",
    "win32AppUserModelId": "win32AppUserModelId",
    "win32ShellNameShort": "win32ShellNameShort",
}


JS_FILES = [
    "resources/app/out/vs/workbench/workbench.desktop.main.js",
    "resources/app/out/vs/workbench/workbench.glass.main.js",
]

EARLY_SPLASH_JS_FILES = [
    "resources/app/out/vs/code/electron-sandbox/workbench/workbench.js",
    "resources/app/out/vs/workbench/workbench.glass.main.js",
]

SPLASH_LOGO_WIDTH = 72
SPLASH_LOGO_HEIGHT = 83

TRAY_ICON_DIR = "resources/app/resources/linux"

LINUX_ICON = "resources/app/resources/linux/code.png"
SPLASH_MEDIA = "resources/app/out/vs/glass/browser/media"
SPLASH_NORMAL = "cursor-splash-logo-normal.png"
SPLASH_GLASS = "cursor-splash-logo-glass.png"
SPLASH_VIDEO_TARGETS = {
    f"{SPLASH_MEDIA}/cursor-logo-for-dark-theme.webm": "dcursor-logo-for-dark-theme.webm",
    f"{SPLASH_MEDIA}/cursor-logo-for-light-theme.webm": "dcursor-logo-for-light-theme.webm",
}

PNG_LOGO_TARGETS = [
    LINUX_ICON,
    "resources/app/out/media/logo.png",
    "resources/app/out/vs/workbench/contrib/onboarding/electron-sandbox/media/logo.png",
    "resources/app/out/vs/workbench/browser/parts/editor/media/logo.png",
]

LOCKUP_TARGETS = {
    "resources/app/out/vs/workbench/browser/parts/editor/media/lockup-horizontal-dark.png": "dcursor-lockup-dark.png",
    "resources/app/out/vs/workbench/browser/parts/editor/media/lockup-horizontal-light.png": "dcursor-lockup-light.png",
}

SVG_LOGO_TARGETS = {
    "resources/app/out/vs/workbench/contrib/onboarding/electron-sandbox/media/logo.svg": "co.anysphere.dcursor.svg",
    "resources/app/out/vs/workbench/services/ai/browser/media/cursor_blame_logo.svg": "dcursor-blame-logo.svg",
}
# Loaded from the app bundle (CSP allows img-src 'self', not file://).
SPLASH_IMG_SRC = (
    'globalThis._VSCODE_FILE_ROOT+"vs/glass/browser/media/cursor-splash-logo-normal.png"'
)

# Bundled JS that hardcodes cursor:// instead of reading product.json urlProtocol.
PROTOCOL_JS_ROOTS = [
    "resources/app/out",
    "resources/app/extensions",
]

PROTOCOL_SKIP_DIRS = {"node_modules", ".git"}


def should_skip_protocol_js(path: Path, app_root: Path) -> bool:
    rel = path.relative_to(app_root).as_posix()
    if any(part in PROTOCOL_SKIP_DIRS for part in path.parts):
        return True
    # Extension dist bundles are integrity-checked at startup; patching them
    # without refreshing embedded hashes breaks profile/auth/agent features.
    if "/extensions/" in rel and "/dist/" in rel:
        return True
    return False


def iter_protocol_js_files(app_root: Path):
    for rel_root in PROTOCOL_JS_ROOTS:
        root = app_root / rel_root
        if not root.exists():
            continue
        for path in root.rglob("*.js"):
            if should_skip_protocol_js(path, app_root):
                continue
            yield path


def patch_data_paths(app_root: Path, identity: dict) -> int:
    """Rewrite hardcoded ~/.cursor paths to dCursor-isolated locations."""
    data_folder = identity.get("dataFolderName", ".dcursor")
    config_name = identity.get("displayNameLong", identity.get("displayName", "dCursor"))

    replacements = [
        (".cursor/sandbox-policies", f"{data_folder}/sandbox-policies"),
        ('(0,i.join)((0,s.homedir)(),".cursor")', f'(0,i.join)((0,s.homedir)(),"{data_folder}")'),
        ('homedir)(),".cursor"', f'homedir)(),"{data_folder}"'),
        ('homedir()),".dcursor",', f'homedir(),"{data_folder}",'),
        ('homedir()),".dcursor")', f'homedir(),"{data_folder}")'),
        ('homedir(),".cursor"', f'homedir(),"{data_folder}"'),
        ('homedir(),".cursor",', f'homedir(),"{data_folder}",'),
        ('homedir(),".cursor")', f'homedir(),"{data_folder}")'),
        ('(0,i.join)(t,"cursor")', f'(0,i.join)(t,"{config_name}")'),
        ('join)(t,"cursor")', f'join)(t,"{config_name}")'),
        ('dataFolderName:".cursor"', f'dataFolderName:"{data_folder}"'),
    ]

    patched = 0
    for path in iter_protocol_js_files(app_root):
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in replacements:
            text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")
            patched += 1
            print(f"Patched data paths in {path}")
    return patched


def patch_url_protocol(app_root: Path, identity: dict) -> int:
    """Rewrite cursor:// deep links to dcursor:// and fix scheme checks."""
    scheme = identity.get("urlProtocol", "dcursor")
    if scheme == "cursor":
        return 0

    patched = 0
    for path in iter_protocol_js_files(app_root):
        text = path.read_text(encoding="utf-8")
        if "cursor://" not in text and 'Gr=["cursor"]' not in text:
            continue

        original = text
        text = text.replace("cursor://", f"{scheme}://")
        text = text.replace('Gr=["cursor"]', f'Gr=["{scheme}"]')
        text = text.replace(
            '"cursor"!==A.scheme||"anysphere.cursor-deeplink"!==A.authority',
            f'"{scheme}"!==A.scheme||"anysphere.cursor-deeplink"!==A.authority',
        )
        text = text.replace(
            "URL must start with cursor://anysphere.cursor-deeplink/",
            f"URL must start with {scheme}://anysphere.cursor-deeplink/",
        )
        text = text.replace(
            'e.g., cursor://anysphere.cursor-deeplink/command/create',
            f'e.g., {scheme}://anysphere.cursor-deeplink/command/create',
        )
        text = text.replace(
            'placeHolder:"cursor://anysphere.cursor-deeplink/',
            f'placeHolder:"{scheme}://anysphere.cursor-deeplink/',
        )
        text = text.replace(
            'urlProtocol:"cursor",reportIssueUrl:',
            f'urlProtocol:"{scheme}",reportIssueUrl:',
        )
        text = text.replace(
            "&source=BACKGROUND_AGENT`}",
            "&source=BACKGROUND_AGENT&url_protocol=" + scheme + "`}",
        )

        if text != original:
            path.write_text(text, encoding="utf-8")
            patched += 1
            print(f"Patched URL protocol in {path}")

    return patched


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).digest()
    return base64.b64encode(digest).decode("ascii").rstrip("=")


def file_sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_braced_object(text: str, start: int) -> tuple[str, int]:
    """Return object literal text starting at text[start] == '{'."""
    if start >= len(text) or text[start] != "{":
        raise ValueError("expected '{' at manifest start")

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1], i + 1
    raise ValueError("unterminated object literal")


def refresh_extension_integrity_hashes(app_root: Path) -> int:
    """Recompute embedded extension file hashes after branding patches."""
    ext_host = (
        app_root / "resources/app/out/vs/workbench/api/node/extensionHostProcess.js"
    )
    if not ext_host.exists():
        return 0

    text = ext_host.read_text(encoding="utf-8")
    marker = 'var qne={'
    marker_idx = text.find(marker)
    if marker_idx < 0:
        print("warn: extension integrity manifest not found")
        return 0

    manifest_start = marker_idx + len("var qne=")
    manifest_text, manifest_end = extract_braced_object(text, manifest_start)

    # Evaluate JS object literal with Node (keys are valid JS identifiers / quoted).
    try:
        payload = subprocess.check_output(
            ["node", "-e", f"console.log(JSON.stringify({manifest_text}))"],
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"warn: could not parse extension integrity manifest: {exc}")
        return 0

    manifest = json.loads(payload)
    extensions_root = app_root / "resources/app/extensions"
    replacements = 0

    def walk(ext_dir: str, node: object, parts: tuple[str, ...] = ()) -> None:
        nonlocal replacements, manifest_text
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if (
                isinstance(value, str)
                and len(value) == 64
                and all(ch in "0123456789abcdef" for ch in value)
            ):
                rel = Path(*parts, key)
                target = extensions_root / ext_dir / rel
                if not target.exists():
                    print(f"warn: missing extension file for integrity hash: {target}")
                    continue
                new_hash = file_sha256_hex(target)
                if new_hash == value:
                    continue
                old_token = f'"{key}":"{value}"'
                new_token = f'"{key}":"{new_hash}"'
                if old_token not in manifest_text:
                    print(f"warn: could not update hash for {ext_dir}/{rel}")
                    continue
                manifest_text = manifest_text.replace(old_token, new_token, 1)
                replacements += 1
                print(f"Updated integrity hash for {ext_dir}/{rel}")
            else:
                walk(ext_dir, value, parts + (key,))

    for ext_id, tree in manifest.items():
        if "." not in ext_id:
            continue
        walk(ext_id.split(".", 1)[1], tree)

    if replacements:
        text = text[:manifest_start] + manifest_text + text[manifest_end:]
        ext_host.write_text(text, encoding="utf-8")

    return replacements


def patch_package_json(app_root: Path, identity: dict) -> None:
    package_path = app_root / "resources/app/package.json"
    if not package_path.exists():
        return

    package = json.loads(package_path.read_text(encoding="utf-8"))
    display = identity.get("displayName", "dCursor")
    package["name"] = display
    package["desktopName"] = "dcursor.desktop"
    package_path.write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Patched {package_path}")


def patch_main_js(app_root: Path) -> None:
    main_path = app_root / "resources/app/out/main.js"
    if not main_path.exists():
        return

    text = main_path.read_text(encoding="utf-8")
    replacements = [
        ('desktopName":"cursor.desktop"', 'desktopName":"dcursor.desktop"'),
        ('"name":"Cursor"', '"name":"dCursor"'),
    ]
    original = text
    for old, new in replacements:
        text = text.replace(old, new)

    if text != original:
        main_path.write_text(text, encoding="utf-8")
        print(f"Patched {main_path}")


def patch_product(identity: dict, product_path: Path, app_root: Path) -> None:
    product = json.loads(product_path.read_text(encoding="utf-8"))
    for product_key, identity_key in FIELD_MAP.items():
        if identity_key in identity:
            product[product_key] = identity[identity_key]

    checksums = product.get("checksums")
    if isinstance(checksums, dict):
        out_root = app_root / "resources/app/out"
        updated = 0
        for rel_path in checksums:
            target = out_root / rel_path
            if target.exists():
                checksums[rel_path] = file_checksum(target)
                updated += 1
        if updated:
            print(f"Updated {updated} integrity checksum(s) in product.json")

    product_path.write_text(
        json.dumps(product, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def patch_js_file(path: Path, identity: dict) -> int:
    text = path.read_text(encoding="utf-8")
    original = text

    title = identity.get("loginTitle", identity.get("displayName", "dCursor"))
    subtitle = identity.get(
        "loginSubtitle",
        "Lorapok Labs — duplicate Cursor instance",
    )
    display = identity.get("displayName", "dCursor")

    img_decoration = (
        f'{{src:{SPLASH_IMG_SRC},width:28,height:28,'
        f'style:{{"border-radius":"6px","object-fit":"contain"}}}}'
    )
    splash_logo = (
        f'{{src:{SPLASH_IMG_SRC},width:96,height:96,'
        f'style:{{"object-fit":"contain"}}}}'
    )
    title_icon = (
        f'u6("img",{{src:{SPLASH_IMG_SRC},width:16,height:16,'
        f'style:{{borderRadius:"4px",objectFit:"contain"}}}})'
    )

    replacements = [
        (
            'src:"file:///usr/share/pixmaps/co.anysphere.dcursor.png"',
            f"src:{SPLASH_IMG_SRC}",
        ),
        (
            'title:"Cursor",subtitle:"The best way to code with AI"',
            f'title:"{title}",subtitle:"{subtitle}"',
        ),
        (
            'size:"3xl",children:"The best way to code with AI"',
            f'size:"3xl",children:"{subtitle}"',
        ),
        (
            'G4e(KR0,{color:"primary"})',
            f'G4e("img",{splash_logo})',
        ),
        (
            "Cursor is the best way to code with agents.",
            f"{display} — Lorapok Labs duplicate instance.",
        ),
        (
            ',get decoration(){return te(tX_,{fill:"var(--cursor-text-primary)",size:28})}',
            f',get decoration(){{return te("img",{img_decoration})}}',
        ),
        (
            ',get decoration(){return oe(zq0,{fill:"var(--cursor-text-primary)",size:28})}',
            f',get decoration(){{return oe("img",{img_decoration})}}',
        ),
        (
            'u6(Ci,{name:"cursor-logo",variant:"filled",size:"sm",color:"primary"})',
            title_icon,
        ),
        (
            '}),name:"Cursor"}):null,t[19]=m',
            f'}}),name:"{display}"}}):null,t[19]=m',
        ),
        (
            'name:"Cursor",icon:xe.infinity',
            f'name:"{display}",icon:xe.infinity',
        ),
    ]

    count = 0
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            count += 1

    if text != original:
        path.write_text(text, encoding="utf-8")
    return count


def patch_early_splash_css(path: Path) -> bool:
    """Enlarge the early startup splash logo container (+20% vs upstream Cursor)."""
    text = path.read_text(encoding="utf-8")
    original = text

    replacements = [
        (
            "width: 60px;\n\theight: 69px;",
            f"width: {SPLASH_LOGO_WIDTH}px;\n\theight: {SPLASH_LOGO_HEIGHT}px;",
        ),
        ("min-width: 60px;", f"min-width: {SPLASH_LOGO_WIDTH}px;"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def install_splash_logos(app_root: Path, assets_dir: Path) -> None:
    """Replace Cursor early-splash PNGs with the dCursor icon."""
    media_dir = app_root / SPLASH_MEDIA
    splash_png = assets_dir / "co.anysphere.dcursor-splash.png"
    fallback_png = assets_dir / "co.anysphere.dcursor.png"
    icon_png = splash_png if splash_png.exists() else fallback_png

    if not icon_png.exists() or not media_dir.exists():
        return

    data = icon_png.read_bytes()
    for name in (SPLASH_NORMAL, SPLASH_GLASS):
        target = media_dir / name
        target.write_bytes(data)
        print(f"Installed splash logo {target}")


def install_all_logos(app_root: Path, assets_dir: Path) -> int:
    """Replace bundled Cursor logos with Lorapok Instar dCursor artwork."""
    installed = 0
    icon_png = assets_dir / "co.anysphere.dcursor.png"
    splash_png = assets_dir / "co.anysphere.dcursor-splash.png"
    source_png = icon_png if icon_png.exists() else splash_png

    if source_png.exists():
        data = source_png.read_bytes()
        for rel in PNG_LOGO_TARGETS:
            target = app_root / rel
            if not target.parent.exists():
                continue
            target.write_bytes(data)
            installed += 1
            print(f"Installed logo {target}")

    for rel, asset_name in LOCKUP_TARGETS.items():
        lockup = assets_dir / asset_name
        target = app_root / rel
        if lockup.exists() and target.parent.exists():
            target.write_bytes(lockup.read_bytes())
            installed += 1
            print(f"Installed lockup {target}")

    for rel, asset_name in SVG_LOGO_TARGETS.items():
        svg = assets_dir / asset_name
        target = app_root / rel
        if svg.exists() and target.parent.exists():
            target.write_text(svg.read_text(encoding="utf-8"), encoding="utf-8")
            installed += 1
            print(f"Installed SVG logo {target}")

    return installed


def install_splash_videos(app_root: Path, assets_dir: Path) -> int:
    """Replace animated splash WEBM logos with dCursor larva animations."""
    installed = 0
    for rel, asset_name in SPLASH_VIDEO_TARGETS.items():
        src = assets_dir / asset_name
        target = app_root / rel
        if src.exists() and target.parent.exists():
            target.write_bytes(src.read_bytes())
            installed += 1
            print(f"Installed splash video {target}")
    return installed


def install_tray_icons(app_root: Path, assets_dir: Path) -> int:
    """Replace Linux tray template PNGs with the dCursor icon."""
    tray_dir = app_root / TRAY_ICON_DIR
    icon_png = assets_dir / "dcursor-logo-32.png"
    if not icon_png.exists():
        icon_png = assets_dir / "co.anysphere.dcursor.png"
    if not tray_dir.exists() or not icon_png.exists():
        return 0

    data = icon_png.read_bytes()
    installed = 0
    for target in tray_dir.glob("tray*.png"):
        target.write_bytes(data)
        installed += 1
    if installed:
        print(f"Installed {installed} tray icon(s) in {tray_dir}")
    return installed


def copy_brand_icon(identity_path: Path, app_root: Path, assets_dir: Path) -> None:
    icon_png = assets_dir / "co.anysphere.dcursor.png"
    linux_code = app_root / LINUX_ICON

    if icon_png.exists() and linux_code.parent.exists():
        linux_code.write_bytes(icon_png.read_bytes())

    pixmaps = app_root.parent / "pixmaps" / "co.anysphere.dcursor.png"
    if icon_png.exists() and pixmaps.parent.exists():
        pixmaps.write_bytes(icon_png.read_bytes())
        print(f"Installed pixmap {pixmaps}")


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <identity.json> <app_root>", file=sys.stderr)
        return 1

    identity_path = Path(sys.argv[1])
    app_root = Path(sys.argv[2])
    assets_dir = identity_path.parent.parent / "assets"

    identity = json.loads(identity_path.read_text(encoding="utf-8"))

    patched_files = 0
    for rel in JS_FILES:
        js_path = app_root / rel
        if js_path.exists() and patch_js_file(js_path, identity):
            patched_files += 1
            print(f"Patched branding in {js_path}")

    splash_css_files = 0
    for rel in dict.fromkeys(EARLY_SPLASH_JS_FILES):
        js_path = app_root / rel
        if js_path.exists() and patch_early_splash_css(js_path):
            splash_css_files += 1
            print(f"Patched early splash CSS in {js_path}")

    png_path = assets_dir / "co.anysphere.dcursor.png"
    if not png_path.exists() and (assets_dir / "co.anysphere.dcursor.svg").exists():
        print(
            "warn: co.anysphere.dcursor.png missing; run icon export in build.sh first",
            file=sys.stderr,
        )

    logo_files = 0
    if png_path.exists() or (assets_dir / "co.anysphere.dcursor-splash.png").exists():
        copy_brand_icon(identity_path, app_root, assets_dir)
        logo_files = install_all_logos(app_root, assets_dir)
        logo_files += install_tray_icons(app_root, assets_dir)
        install_splash_logos(app_root, assets_dir)
        logo_files += install_splash_videos(app_root, assets_dir)

    patch_package_json(app_root, identity)
    patch_main_js(app_root)
    path_files = patch_data_paths(app_root, identity)
    protocol_files = patch_url_protocol(app_root, identity)
    integrity_hashes = refresh_extension_integrity_hashes(app_root)

    product_path = app_root / "resources/app/product.json"
    if product_path.exists():
        patch_product(identity, product_path, app_root)
        print(f"Patched {product_path}")

    print(
        f"Branding patch complete ({patched_files} JS bundles, "
        f"{splash_css_files} splash CSS files, "
        f"{path_files} path files, {protocol_files} protocol files, "
        f"{integrity_hashes} integrity hashes, "
        f"{logo_files} logo files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
