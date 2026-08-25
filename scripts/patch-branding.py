#!/usr/bin/env python3
"""Patch Cursor branding in product.json and bundled UI assets."""

import base64
import hashlib
import json
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

LINUX_ICON = "resources/app/resources/linux/code.png"
SPLASH_MEDIA = "resources/app/out/vs/glass/browser/media"
SPLASH_NORMAL = "cursor-splash-logo-normal.png"
SPLASH_GLASS = "cursor-splash-logo-glass.png"
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


def iter_protocol_js_files(app_root: Path):
    for rel_root in PROTOCOL_JS_ROOTS:
        root = app_root / rel_root
        if not root.exists():
            continue
        for path in root.rglob("*.js"):
            if any(part in PROTOCOL_SKIP_DIRS for part in path.parts):
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
    ]

    count = 0
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            count += 1

    if text != original:
        path.write_text(text, encoding="utf-8")
    return count


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


def copy_brand_icon(identity_path: Path, app_root: Path, assets_dir: Path) -> None:
    icon_png = assets_dir / "co.anysphere.dcursor.png"
    linux_code = app_root / LINUX_ICON

    if icon_png.exists() and linux_code.parent.exists():
        linux_code.write_bytes(icon_png.read_bytes())

    pixmaps = app_root.parent.parent.parent / "pixmaps" / "co.anysphere.dcursor.png"
    if icon_png.exists() and pixmaps.parent.exists():
        pixmaps.write_bytes(icon_png.read_bytes())


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

    png_path = assets_dir / "co.anysphere.dcursor.png"
    if not png_path.exists() and (assets_dir / "co.anysphere.dcursor.svg").exists():
        print(
            "warn: co.anysphere.dcursor.png missing; run icon export in build.sh first",
            file=sys.stderr,
        )

    if png_path.exists() or (assets_dir / "co.anysphere.dcursor-splash.png").exists():
        copy_brand_icon(identity_path, app_root, assets_dir)
        install_splash_logos(app_root, assets_dir)

    patch_package_json(app_root, identity)
    patch_main_js(app_root)
    path_files = patch_data_paths(app_root, identity)
    protocol_files = patch_url_protocol(app_root, identity)

    product_path = app_root / "resources/app/product.json"
    if product_path.exists():
        patch_product(identity, product_path, app_root)
        print(f"Patched {product_path}")

    print(
        f"Branding patch complete ({patched_files} JS bundles, "
        f"{path_files} path files, {protocol_files} protocol files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
