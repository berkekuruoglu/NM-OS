# Installation Notes

NM-OS now publishes a bootable installer ISO for VM and hardware testing.

## Current artifact output

- `dist/nmos-system-overlay-<version>.tar.gz`
- `dist/nmos-system-overlay-<version>.sha256`
- `dist/nmos-system-overlay-<version>.packages`
- `dist/nmos-system-overlay-<version>.build-manifest`
- `dist/nmos-installer-assets-<version>.tar.gz`
- `dist/nmos-installer-assets-<version>.sha256`
- `dist/nmos-installer-assets-<version>.packages`
- `dist/nmos-installer-<version>-amd64.iso`
- `dist/nmos-installer-<version>-amd64.sha256`
- `dist/nmos-recovery-image-<version>.tar.gz`
- `dist/nmos-recovery-image-<version>.sha256`

## Recommended test flow

1. Build the repository outputs.
2. Create a new VM in VirtualBox, VMware, or QEMU with at least 4 GB RAM, 2 virtual CPUs, and a 64 GB disk.
3. Boot the VM from `nmos-installer-<version>-amd64.iso`.
4. Choose `Install NM-OS`.
5. Finish the Debian-based installer flow.
6. Reboot into the installed system and test the greeter, profiles, vault, and control center.

## What the installer ISO does

The current ISO is based on Debian `amd64 netinst`.

During installation it:

- installs a GNOME-based Debian system
- installs the NM-OS runtime package set
- applies the staged NM-OS overlay in a late install step
- creates the experimental A/B slot layout (`NMOS_ROOT_A`, `NMOS_ROOT_B`, `NMOS_STATE`, `NMOS_EFI`)
- seeds update-engine slot metadata and GRUB slot state
- clones the initial rootfs into the inactive slot so staged updates have a bootable target
- boots into the installed NM-OS environment after setup

## Overlay install flow

The overlay archive is still useful for manual testing or layering NM-OS onto an existing Debian VM.

1. Prepare a Debian-based target with GNOME and GDM.
2. Install the packages listed in `nmos-system-overlay-<version>.packages`.
3. Extract the overlay archive on top of `/`.
4. Run `systemd-tmpfiles --create /usr/lib/tmpfiles.d/nmos.conf`.
5. Run `systemctl daemon-reload`.
6. Reboot.

## Installer notes

- the current installer path uses Debian-installer media with an NM-OS preseed and overlay payload
- the preseed detects the VM's primary disk and applies an unattended experimental A/B partition recipe
- Calamares branding and module scaffolding remain in the repo for the richer desktop installer path
- netinst media still expects network access during installation
