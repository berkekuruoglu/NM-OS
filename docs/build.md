# Build Notes

## Host requirements

- Linux build host or WSL2
- `curl`
- `rsync`
- `tar`
- `gzip`
- `sha256sum`
- `xorriso`

## What the build publishes

Artifacts in `dist/`:

- `nmos-system-overlay-<version>.tar.gz`
- `nmos-system-overlay-<version>.sha256`
- `nmos-system-overlay-<version>.packages`
- `nmos-system-overlay-<version>.build-manifest`
- `nmos-installer-assets-<version>.tar.gz`
- `nmos-installer-assets-<version>.sha256`
- `nmos-installer-assets-<version>.packages`
- `nmos-installer-<version>-amd64.iso`
- `nmos-installer-<version>-amd64.sha256`
- `nmos-recovery-image-<version>.tar.gz`
- `nmos-recovery-image-<version>.sha256`
- `release-manifest.json.sig` (when signing key is configured)

The release manifest now carries slot-image and recovery-image metadata, a slot-based rollback scope, and signing mode details.
It also carries a positive `release_sequence`; production release automation should set `NMOS_RELEASE_SEQUENCE`
to a value that only increases so clients can reject replayed signed metadata.
When `NMOS_UPDATE_SIGNING_KEY_ID` is configured and `gpg` is available, the build emits a detached `release-manifest.json.sig` and records `detached-gpg` mode in `release-manifest.json`.

## How the installer ISO is built

The current installer media is built by:

1. staging the NM-OS runtime overlay
2. staging installer assets and Debian-installer templates
3. resolving the pinned Debian `amd64 netinst` ISO from `config/installer/base-iso.lock` (or explicit env overrides)
4. injecting the NM-OS preseed, overlay archive, and package manifest
5. replaying the Debian boot layout into a new NM-OS installer ISO

This means you do not need to download a separate Debian ISO by hand just to test NM-OS.
By default, installer builds fail closed if the base ISO lock metadata is incomplete.

## What gets staged

Runtime overlay:

- `config/system-overlay/`
- first-party Python packages in `apps/`
- shared theme assets under `/usr/share/nmos/theme`
- systemd units for settings, network bootstrap, vault, and boot marker flows

Installer assets:

- `config/installer/calamares/`
- `config/installer/debian-installer/`
- `config/installer-packages/`

## Entry points

### Windows + WSL2

```powershell
.\build\install-deps.ps1
.\build\build.ps1
```

Optional Brave-aware overlay:

```powershell
.\build\build.ps1 -EnableBrave
```

### Linux / WSL2 direct

```bash
./build/build.sh
```

Optional Brave-aware overlay:

```bash
NMOS_ENABLE_BRAVE=1 ./build/build.sh
```

Optional base ISO override:

```bash
NMOS_BASE_INSTALLER_ISO_PATH=/path/to/debian-amd64-netinst.iso ./build/build.sh
```

Pinned base ISO metadata override:

```bash
NMOS_BASE_INSTALLER_BASE_URL=https://mirror.example/debian-cd/13.4.0/amd64/iso-cd \
NMOS_BASE_INSTALLER_ISO_FILE=debian-13.4.0-amd64-netinst.iso \
NMOS_BASE_INSTALLER_SHA256=<sha256> \
./build/build.sh
```

Temporary non-reproducible fallback (explicit opt-in):

```bash
NMOS_ALLOW_UNPINNED_BASE_ISO=1 ./build/build.sh
```

## Verification

Before a build:

```bash
./tests/smoke/verify-structure.sh
./tests/smoke/verify-python.sh
./tests/smoke/verify-quality-tooling.sh
./tests/smoke/verify-build-hygiene.sh
./tests/smoke/verify-version-policy.sh
./tests/smoke/verify-settings-model.sh
./tests/smoke/verify-control-center.sh
./tests/smoke/verify-installer-media.sh
./tests/smoke/verify-network-policy.sh
./tests/smoke/verify-prelogin-wiring.sh
./tests/smoke/verify-vault-storage.sh
./tests/smoke/verify-runtime-logic.sh
./tests/smoke/verify-leaks.sh
```

After a build:

```bash
./tests/smoke/verify-artifacts.sh
./build/smoke-overlay.sh
bash ./tests/e2e/run-qemu-ab-smoke.sh
```
