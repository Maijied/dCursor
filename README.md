# dCursor

<p align="center">
  <img src="assets/co.anysphere.dcursor.svg" alt="dCursor logo" width="128" height="128" />
</p>

<p align="center">
  <strong>A Lorapok Labs product — run two Cursor accounts on one Linux machine</strong>
</p>

<p align="center">
  <a href="https://github.com/Maijied/dCursor/releases/latest/download/dCursor.deb">
    <img src="https://img.shields.io/badge/Download-dCursor.deb-00e5c7?style=for-the-badge&logo=debian&logoColor=white" alt="Download dCursor.deb" />
  </a>
  <a href="https://github.com/Maijied/dCursor/actions/workflows/build.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Maijied/dCursor/build.yml?branch=main&style=for-the-badge&label=CI%2FCD" alt="CI/CD" />
  </a>
  <a href="https://github.com/Maijied/dCursor/releases">
    <img src="https://img.shields.io/github/v/release/Maijied/dCursor?style=for-the-badge&color=73d928" alt="Latest release" />
  </a>
</p>

---

## What is dCursor?

**dCursor** stands for **duplicate Cursor** — a fully isolated mirror of the [Cursor](https://cursor.com) AI IDE, packaged as a standalone Debian app. It lets you run a **second Cursor instance** with its own account, extensions, agent, MCP servers, and settings — side by side with your original Cursor install.

Built by **[Lorapok Labs](https://github.com/Maijied)** as a developer productivity tool for multi-account workflows (work/personal, client projects, testing, etc.).

| | **Cursor** | **dCursor** |
|---|-----------|------------|
| **Command** | `cursor` | `dcursor` |
| **Config** | `~/.config/Cursor` | `~/.config/dCursor` |
| **Data** | `~/.cursor` | `~/.dcursor` |
| **Agent** | `~/.local/share/cursor-agent` | `~/.local/share/dcursor-agent` |
| **URL scheme** | `cursor://` | `dcursor://` |
| **Taskbar** | `Cursor` | `dCursor` |

Both apps can run **at the same time** with **different accounts**.

---

## Download

### One-click install (recommended)

```bash
# Download latest .deb
wget -O dCursor.deb "https://github.com/Maijied/dCursor/releases/latest/download/dCursor.deb"

# Install
sudo dpkg -i dCursor.deb
sudo apt-get install -f -y
```

Or use the **[Download dCursor.deb](https://github.com/Maijied/dCursor/releases/latest/download/dCursor.deb)** button above.

### From a local build

```bash
git clone https://github.com/Maijied/dCursor.git
cd dCursor
./build.sh
sudo ./scripts/install.sh
```

---

## Quick start

```bash
dcursor              # Launch IDE (sign in with a separate account)
dcursor agent        # Launch isolated CLI agent
dcursor --version    # Check version
```

Launch from your app menu: **dCursor** (Lorapok Larvae × Cursor hybrid icon).

---

## Architecture

```mermaid
flowchart TB
  subgraph lorapok [Lorapok Labs dCursor]
    Build["build.sh\nhardlink/copy + patch"]
    Deb["dCursor.deb"]
    Build --> Deb
  end

  subgraph install [Installed on Linux]
    DC["/usr/share/dcursor"]
    CLI["/usr/bin/dcursor"]
    Deb --> DC
    Deb --> CLI
  end

  subgraph isolation [Runtime isolation]
    IDE["dCursor IDE"]
    Agent["dcursor agent"]
    D1["~/.dcursor"]
    D2["~/.config/dCursor"]
    D3["~/.local/share/dcursor-agent"]
    CLI --> IDE
    CLI --> Agent
    IDE --> D1
    IDE --> D2
    Agent --> D1
    Agent --> D3
  end

  subgraph original [Original Cursor - untouched]
    C1["~/.cursor"]
    C2["~/.config/Cursor"]
  end
```

### How it works

1. **Mirror** — Copies the installed Cursor app tree (`/usr/share/cursor` → `/usr/share/dcursor`) using hardlinks when possible for fast builds.
2. **Rebrand** — Patches `product.json` identity fields (`dataFolderName`, `urlProtocol`, `linuxIconName`, etc.) so dCursor uses separate paths.
3. **Isolate** — Custom launcher routes IDE and agent to `~/.dcursor` / `~/.config/dCursor` with `CURSOR_CONFIG_DIR` and `CURSOR_DATA_DIR`.
4. **Package** — Ships as a standalone `.deb` (~200 MB compressed) with desktop entry, AppArmor profile, and bash completion.

---

## Plans and roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **v1.0** | ✅ Done | Standalone amd64 `.deb`, full IDE + agent isolation |
| **v1.1** | 🔜 Planned | ARM64 build support |
| **v1.2** | 🔜 Planned | Auto-rebuild when Cursor updates (watch APT repo) |
| **v2.0** | 💡 Idea | Profile manager UI — switch between N Cursor mirrors |

---

## Build from source

### Requirements

- Cursor installed via `.deb`, **or** CI fetch script (no local Cursor needed)
- `python3`, `dpkg-deb`
- `rsvg-convert`, `inkscape`, or ImageMagick (icon export)

### Build

```bash
./build.sh
# or
make build
```

### CI/CD (no local Cursor needed)

```bash
./scripts/ci-fetch-cursor.sh   # downloads latest Cursor .deb
./build.sh
```

GitHub Actions builds automatically on every push to `main` and publishes artifacts to [Releases](https://github.com/Maijied/dCursor/releases).

### Build notes

- Staging uses `/tmp/dcursor-build.*` for valid `dpkg-deb` permissions (needed on NTFS/exFAT project drives).
- Hardlink copy (`cp -al`) is used when on the same filesystem as `/usr/share/cursor`; otherwise falls back to `cp -a`.
- Override: `DCURSOR_BUILD_DIR=/var/tmp/my-build ./build.sh`

---

## Updating

When Cursor updates on your system:

```bash
git pull
make build
sudo dpkg -i dist/dCursor.deb
```

Or download the latest CI-built package from [Releases](https://github.com/Maijied/dCursor/releases).

---

## Uninstall

```bash
sudo dpkg -r dcursor
```

This removes dCursor only. Your original Cursor install and both apps' user data remain untouched.

---

## Project structure

```
dCursor/
├── build.sh                    # Main build pipeline
├── config/identity.json        # Rebrand identity map
├── scripts/
│   ├── dcursor-launcher.sh     # IDE + agent launcher
│   ├── patch-product-json.py   # product.json patcher
│   ├── ci-fetch-cursor.sh      # CI: download Cursor .deb
│   └── install.sh              # Local install helper
├── assets/                     # Desktop, icon, AppArmor, mime
├── debian/                     # postinst, prerm, postrm
└── .github/workflows/build.yml # CI/CD auto-build + release
```

---

## Lorapok Labs

**dCursor** is a **[Lorapok Labs](https://github.com/Maijied)** open-source utility. The icon blends the Lorapok Larvae identity (green/cyan segmented instar motif) with Cursor's app-tile aesthetic — a visual marker that this is your *second* Cursor instance.

- **Maintainer:** Maizied Hasan Majumder — Lorapok Labs
- **Repository:** [github.com/Maijied/dCursor](https://github.com/Maijied/dCursor)
- **Issues:** [github.com/Maijied/dCursor/issues](https://github.com/Maijied/dCursor/issues)

---

## License and disclaimer

Cursor is proprietary software by Anysphere. **dCursor** repackages an already-installed or officially downloaded Cursor copy for personal multi-account use on the same machine. You must comply with [Cursor's license](https://cursor.com/license.txt) for each account you sign in with.

The dCursor build tooling and branding assets in this repository are provided by Lorapok Labs as-is, without warranty.
