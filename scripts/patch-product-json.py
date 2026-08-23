#!/usr/bin/env python3
"""Patch Cursor product.json for dCursor identity."""

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


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <identity.json> <product.json>", file=sys.stderr)
        return 1

    identity_path = Path(sys.argv[1])
    product_path = Path(sys.argv[2])

    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    product = json.loads(product_path.read_text(encoding="utf-8"))

    for product_key, identity_key in FIELD_MAP.items():
        if identity_key in identity:
            product[product_key] = identity[identity_key]

    product_path.write_text(
        json.dumps(product, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Patched {product_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
