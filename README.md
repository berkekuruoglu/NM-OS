# NM-OS

NM-OS is a privacy-focused Linux desktop for people who want stronger protection without becoming security experts.

It works out of the box, gets out of your way, and lets you go as deep as you want when you're ready.
Whether you want a quiet daily computer or a hardened private workspace, NM-OS grows with you.

## What Can I Do With NM-OS?

- Write documents, spreadsheets, and presentations (LibreOffice included)
- Browse the web, check email, watch videos
- Organize your photos and listen to music
- Keep your files safe with an encrypted vault
- Switch to a more private or focused mode in seconds — and switch back just as easily
- Customize everything: colors, fonts, wallpaper, layout, animations

## Who Is NM-OS For?

NM-OS is built first for privacy-conscious people who want a practical Linux desktop without expert-only controls.
A student, small business owner, journalist, or researcher can start with a familiar daily environment and activate
stronger boundaries when the situation calls for them.

## How NM-OS Works

NM-OS gives you four protection levels, which you can switch between at any time:

| Level | What it means |
|---|---|
| **Relaxed** | Easiest to use. Great for trusted home networks. |
| **Balanced** | Recommended default. Direct networking with strong tracking protection. |
| **Hardened** | Tor-routed networking with stricter app and device boundaries. |
| **Maximum** | Highest practical restriction. For sensitive situations. |

Every setting inside each level can also be turned on or off individually.
Profiles are a starting point, not a lock.

## What Is Included

Today the repository builds:

- a bootable installer ISO
- an installed-system overlay archive
- installer assets

The installed system includes:

- a setup assistant that runs before login
- a desktop control center
- productivity apps (office, browser, media, photos)
- an encrypted vault for sensitive files
- network modes: direct, Tor-first, or offline
- a rich personalization system: themes, fonts, wallpaper, density, motion
- Debian-installer-based media for VM and hardware testing

The default profile is `Balanced`.

## Design Principles

### Human-first computing

The computer works for the user, not the other way around.
Every feature must be understandable, reachable, and reversible.

### Fluid modes, not fixed personas

Users are not categorized. Anyone can switch from a comfortable desktop to maximum
security and back again — quickly, visibly, and without losing their previous state.

### Everything is accessible, nothing is forced

No feature is hidden. Security controls are always reachable.
But nothing is mandatory beyond choosing a language and a starting profile.

### Explainable choices

When NM-OS restricts something, it says so clearly.
Users see what changed, why it changed, and what they give up or gain.

### Progressive depth

Start with zero configuration. Go as deep as you want.
The same platform serves a first-time Linux user and an experienced system administrator.

## What Exists In The Repo

- `apps/` — Python applications and services
- `build/` — build entry points and artifact verification helpers
- `config/system-overlay/` — runtime overlay content for the installed system
- `config/installer/` — installer scaffolding
- `config/system-packages/` — target runtime package manifests
- `config/installer-packages/` — installer-side package manifests
- `tests/` — smoke and Python validation
- `docs/` — product direction, security model, build and install guides

## Quick Start

### Windows + WSL2

```powershell
.\build\install-deps.ps1
.\build\build.ps1
```

### Linux / WSL2 Direct

```bash
./build/build.sh
```

Optional Brave-aware overlay:

```bash
NMOS_ENABLE_BRAVE=1 ./build/build.sh
```

## Testing

The safest way to evaluate NM-OS is inside a virtual machine.

1. Build the installer ISO from this repo.
2. Boot the ISO in VirtualBox, QEMU, VMware, or another VM.
3. Choose `Install NM-OS`.
4. Finish the install flow.
5. Reboot and test the setup assistant, apps, vault, and control center.

Install details: [docs/installation.md](docs/installation.md)

## Useful Docs

- [User experience guide](docs/user-experience.md)
- [Product direction](docs/vision.md)
- [Implementation plan additions](docs/implementation-plan-additions.md)
- [Security model](docs/security-model.md)
- [Security profiles](docs/security-profiles.md)
- [Runtime notes](docs/runtime.md)
- [Build notes](docs/build.md)
- [Installation notes](docs/installation.md)
- [Translation guide](docs/translations.md)
- [Windows + WSL2 workflow](docs/windows-wsl.md)
- [Independence program](docs/independence/README.md)

## Current Limits

This is still alpha software. Not finished yet:

- a release-grade update flow
- full per-app permission editing
- release-grade hardware validation
- a fully independent base platform beyond the current Debian-backed layer

## License

NM-OS is licensed under `GPL-3.0-or-later`.

See [LICENSE](LICENSE) and [COPYING](COPYING).
