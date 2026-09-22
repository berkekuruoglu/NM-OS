#!/bin/sh

set -eu

TARGET_ROOT="${1:-/target}"
VERSION="${NMOS_VERSION:-@VERSION@}"
PROFILE_SOURCE="${2:-/cdrom/nmos/experimental-ab/profile.json}"
AB_LAYOUT_FILE="${TARGET_ROOT}/etc/nmos/ab-layout.env"
STATE_DIR="${TARGET_ROOT}/var/lib/nmos/update-engine"
TARGET_GRUB_SCRIPT="${TARGET_ROOT}/etc/grub.d/09_nmos_ab"
TARGET_GRUB_DEFAULTS="${TARGET_ROOT}/etc/default/grub.d/90-nmos-ab.cfg"
SLOT_B_DEVICE="/dev/disk/by-label/NMOS_ROOT_B"
SLOT_A_LABEL="NMOS_ROOT_A"
SLOT_B_LABEL="NMOS_ROOT_B"
STATE_LABEL="NMOS_STATE"
EFI_LABEL="NMOS_EFI"

log() {
    echo "[nmos-ab-installer] $*"
    if [ -c /dev/ttyS0 ]; then
        echo "[nmos-ab-installer] $*" > /dev/ttyS0 || true
    fi
}

render_fstab() {
    render_slot_name="$1"
    render_root_label="${SLOT_A_LABEL}"
    render_inactive_label="${SLOT_B_LABEL}"
    render_inactive_slot="b"
    if [ "${render_slot_name}" = "b" ]; then
        render_root_label="${SLOT_B_LABEL}"
        render_inactive_label="${SLOT_A_LABEL}"
        render_inactive_slot="a"
    fi
    cat <<EOF
LABEL=${render_root_label} / ext4 defaults 0 1
LABEL=${STATE_LABEL} /var/lib/nmos ext4 defaults 0 2
LABEL=${EFI_LABEL} /boot/efi vfat umask=0077 0 1
LABEL=${render_inactive_label} /var/lib/nmos/slots/${render_inactive_slot} ext4 defaults,nofail 0 2
EOF
}

mkdir -p "${TARGET_ROOT}/etc/nmos" \
         "${TARGET_ROOT}/var/lib/nmos/slots" \
         "${STATE_DIR}" \
         "${TARGET_ROOT}/etc/default/grub.d"

if [ -f "${PROFILE_SOURCE}" ]; then
    # Debian Installer's runtime is intentionally small and does not provide
    # the coreutils `install` helper. Keep this preparation step compatible
    # with that environment by using the tools d-i guarantees are present.
    cp "${PROFILE_SOURCE}" "${TARGET_ROOT}/etc/nmos/installer-profile.json"
    chmod 0644 "${TARGET_ROOT}/etc/nmos/installer-profile.json"
fi

cat > "${AB_LAYOUT_FILE}" <<EOF
NMOS_SLOT_A_LABEL=${SLOT_A_LABEL}
NMOS_SLOT_B_LABEL=${SLOT_B_LABEL}
NMOS_STATE_LABEL=${STATE_LABEL}
NMOS_EFI_LABEL=${EFI_LABEL}
EOF

cat > "${STATE_DIR}/slot-state.json" <<EOF
{
  "active_slot": "a",
  "inactive_slot": "b",
  "pending_slot": "",
  "previous_slot": "",
  "boot_attempts_remaining": 0,
  "installed_version": "${VERSION}",
  "staged_version": "",
  "last_boot_result": "unknown"
}
EOF

cat > "${STATE_DIR}/history.json" <<EOF
{
  "entries": [
    {
      "at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
      "action": "install_seed",
      "details": {
        "active_slot": "a",
        "inactive_slot": "b",
        "version": "${VERSION}"
      }
    }
  ]
}
EOF

printf '%s\n' '{}' > "${STATE_DIR}/boot-intent.json"
printf '%s\n' '{}' > "${STATE_DIR}/health-state.json"
render_fstab "a" > "${TARGET_ROOT}/etc/fstab"
printf '%s\n' "slot=a" > "${TARGET_ROOT}/etc/nmos/slot-id"

if [ -f "${TARGET_GRUB_SCRIPT}" ]; then
    chmod +x "${TARGET_GRUB_SCRIPT}"
fi

if [ -f "${TARGET_GRUB_DEFAULTS}" ]; then
    chmod 0644 "${TARGET_GRUB_DEFAULTS}"
fi

if [ -e "${SLOT_B_DEVICE}" ]; then
    SLOT_B_MOUNT="$(mktemp -d)"
    cleanup_slot_b() {
        umount "${SLOT_B_MOUNT}" >/dev/null 2>&1 || true
        rmdir "${SLOT_B_MOUNT}" >/dev/null 2>&1 || true
    }
    trap cleanup_slot_b EXIT
    mount "${SLOT_B_DEVICE}" "${SLOT_B_MOUNT}"
    mkdir -p "${SLOT_B_MOUNT}"
    (
        cd "${TARGET_ROOT}"
        tar \
            --one-file-system \
            --exclude='./var/lib/nmos' \
            --exclude='./boot/efi' \
            --exclude='./tmp/*' \
            -cpf - .
    ) | (
        cd "${SLOT_B_MOUNT}"
        tar -xpf -
    )
    mkdir -p "${SLOT_B_MOUNT}/etc/nmos"
    cp "${AB_LAYOUT_FILE}" "${SLOT_B_MOUNT}/etc/nmos/ab-layout.env"
    chmod 0644 "${SLOT_B_MOUNT}/etc/nmos/ab-layout.env"
    render_fstab "b" > "${SLOT_B_MOUNT}/etc/fstab"
    printf '%s\n' "slot=b" > "${SLOT_B_MOUNT}/etc/nmos/slot-id"
    if [ -f "${SLOT_B_MOUNT}/etc/grub.d/09_nmos_ab" ]; then
        chmod +x "${SLOT_B_MOUNT}/etc/grub.d/09_nmos_ab"
    fi
    sync
    umount "${SLOT_B_MOUNT}"
    rmdir "${SLOT_B_MOUNT}"
    trap - EXIT
    log "Cloned rootfs_a into rootfs_b and rendered slot-specific fstab files."
else
    log "Inactive slot device ${SLOT_B_DEVICE} not found; skipped initial clone."
fi

if command -v chroot >/dev/null 2>&1 && [ -x "${TARGET_ROOT}/usr/sbin/update-grub" ]; then
    chroot "${TARGET_ROOT}" grub-editenv /boot/grub/grubenv create || true
    chroot "${TARGET_ROOT}" grub-editenv /boot/grub/grubenv set \
        nmos_active_slot=a \
        nmos_pending_slot= \
        nmos_previous_slot= \
        nmos_boot_attempts_remaining=0 \
        nmos_boot_ok=1 || true
    chroot "${TARGET_ROOT}" /usr/sbin/update-grub || true
fi

log "Experimental A/B target preparation complete."
