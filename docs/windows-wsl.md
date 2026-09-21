# Windows + WSL2 Workflow

NM-OS is developed on Windows, but the build runs inside WSL2.

## What runs where

- Edit code on Windows
- Run build commands from PowerShell
- Let WSL2 execute the Linux build
- Review the generated overlay, installer assets, and installer ISO from Windows
- Boot the installer ISO in a VM to test the full setup flow

## First setup

1. Install WSL2 and a Debian or Ubuntu distribution.
2. Open PowerShell in the repository root.
3. Run:

```powershell
.\build\install-deps.ps1
```

If you want a specific distro:

```powershell
.\build\install-deps.ps1 -Distro Ubuntu
```

## Build

From PowerShell:

```powershell
.\build\build.ps1
```

Outputs for Windows testing:

- `dist\nmos-system-overlay-<version>.tar.gz`
- `dist\nmos-installer-assets-<version>.tar.gz`
- `dist\nmos-installer-<version>-amd64.iso`

If you want the optional Brave-aware overlay:

```powershell
.\build\build.ps1 -EnableBrave
```

## Test

Typical next steps are:

1. open VirtualBox or another hypervisor
2. create a fresh VM with at least 4 GB RAM, 2 virtual CPUs, and a 64 GB disk
3. mount `dist\nmos-installer-<version>-amd64.iso`
4. boot, choose `Install NM-OS (erases the target disk)`, and press Enter
5. wait for the unattended setup to finish, then sign in as `nmos` with password `nmos`
6. test the greeter, profiles, vault, updates, and recovery in the installed system
