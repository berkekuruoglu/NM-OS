# NM-OS

NM-OS is a privacy-focused Linux desktop for people who want stronger protection without becoming security experts.
It combines a familiar daily environment with clear, switchable protection profiles that explain what changes and why.

> **Project status:** NM-OS is alpha software (`0.1.0-alpha.1`). Evaluate it in a virtual machine before considering real hardware or sensitive work.

## Why NM-OS?

Privacy-focused systems often ask people to choose between convenience and control before they understand the tradeoff.
NM-OS takes a different approach:

- start with practical defaults suitable for everyday browsing and office work
- move to stronger isolation only when the situation calls for it
- keep security choices visible, understandable, and reversible
- use enforcement layers such as nftables, browser policy, application sandboxing, and encrypted storage

The recommended `Balanced` profile uses direct networking with strong tracking protection. Tor routing is reserved for the explicitly selected `Hardened` profile, where the additional compatibility cost is expected.

## Protection Profiles

| Profile | Network behavior | Intended use | Main tradeoff |
|---|---|---|---|
| **Relaxed** | Direct | Familiar daily use on trusted networks | Lighter default boundaries |
| **Balanced** | Direct with strong tracking protection | Recommended daily profile | Privacy protections without Tor-related website friction |
| **Hardened** | TCP and DNS routed through Tor | Private work where stronger isolation matters | More CAPTCHAs, slower connections, and reduced service compatibility |
| **Maximum** | Offline by default | High-sensitivity, minimal-exposure work | Intentionally restrictive |

Profiles are starting points rather than permanent personas. Individual controls remain available, and users can move between profiles as their needs change.

Routing an ordinary browser through Tor does not make it equivalent to Tor Browser and does not guarantee anonymity. See the [security model](docs/security-model.md) and [internet and email guide](docs/user-guides/internet-and-email.md) for the current boundaries.

## What Exists Today

The installed desktop includes:

- a pre-login setup assistant with plain-language profile selection
- a desktop control center for security, privacy, applications, and system settings
- productivity, browser, media, and photo applications
- an encrypted vault for sensitive files
- direct, Tor-routed, and offline network policies
- Firefox and Chromium privacy policies
- Flatpak-oriented application isolation and portal controls
- experimental A/B update, health-check, recovery, and rollback infrastructure
- themes, fonts, wallpaper, layout, density, and motion controls

The repository builds:

- a bootable Debian-installer-based NM-OS ISO
- an installed-system overlay archive
- installer and recovery assets
- update catalog and release-manifest scaffolding

## Design Principles

- **Human-first:** controls should be understandable without specialist knowledge.
- **Explainable:** restrictions should state what changed, why, and what the user gains or loses.
- **Reversible:** profiles and individual settings should be safe to change and easy to undo.
- **Progressive:** begin with sensible defaults, then expose deeper control when requested.
- **Honest:** document current limits instead of turning security goals into unsupported promises.

## Build

### Windows with WSL2

```powershell
.\build\install-deps.ps1
.\build\build.ps1
```

### Linux or WSL2

```bash
./build/build.sh
```

To include the optional Brave integration:

```bash
NMOS_ENABLE_BRAVE=1 ./build/build.sh
```

Detailed instructions and supported overrides are in the [build guide](docs/build.md).

## Test in a Virtual Machine

1. Build the installer ISO.
2. Boot it in QEMU, VirtualBox, VMware, or another virtual machine.
3. Choose `Install NM-OS (erases the target disk)` and press Enter. The remaining installation is automatic.
4. Reboot and sign in with username `nmos` and password `nmos`.
5. Exercise setup, profile switching, networking, the encrypted vault, updates, and recovery.

See the [installation guide](docs/installation.md) for the current workflow.

## Repository Layout

- `apps/` — Python desktop applications and services
- `build/` — build entry points and artifact verification
- `config/system-overlay/` — installed-system files and policy
- `config/installer/` — installer configuration and A/B scaffolding
- `config/system-packages/` — runtime package manifests
- `tests/` — Python, smoke, Windows, build, and QEMU validation
- `docs/` — product, security, build, installation, and user documentation

## Documentation

- [Product direction](docs/vision.md)
- [Security model](docs/security-model.md)
- [Security profiles](docs/security-profiles.md)
- [User experience](docs/user-experience.md)
- [Installation](docs/installation.md)
- [Build and release](docs/build.md)
- [Update and rollback architecture](docs/update-rollback-architecture.md)
- [Runtime notes](docs/runtime.md)
- [Translation guide](docs/translations.md)
- [Independence program](docs/independence/README.md)

## Current Limits

NM-OS is not yet a release-ready daily-driver operating system. Important remaining work includes:

- release-grade update publishing, signing-key operations, and recovery validation
- complete per-application permission editing
- broader automated privacy, networking, and failure-mode tests
- hardware compatibility, suspend/resume, Wi-Fi, and installation testing
- usability and accessibility testing with non-expert Linux users
- reducing dependence on the current Debian-backed base platform

## License

NM-OS is licensed under `GPL-3.0-or-later`. See [LICENSE](LICENSE) and [COPYING](COPYING).
