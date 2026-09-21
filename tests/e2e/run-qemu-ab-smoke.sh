#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '\r\n' < "${ROOT_DIR}/config/version")"
ISO_PATH="${ROOT_DIR}/dist/nmos-installer-${VERSION}-amd64.iso"
WORK_DIR="${ROOT_DIR}/.build/qemu-ab-smoke"
DISK_PATH="${WORK_DIR}/nmos-ab-smoke.qcow2"
INSTALL_LOG="${WORK_DIR}/install.log"
BOOT_LOG="${WORK_DIR}/boot.log"
ROLLBACK_LOG="${WORK_DIR}/rollback.log"
VMLINUX_PATH="${WORK_DIR}/vmlinuz"
INITRD_PATH="${WORK_DIR}/initrd.gz"

for command in guestfish qemu-img qemu-system-x86_64 timeout xorriso; do
    command -v "${command}" >/dev/null 2>&1 || {
        echo "missing required command: ${command}" >&2
        exit 1
    }
done

[ -f "${ISO_PATH}" ] || {
    echo "missing installer ISO: ${ISO_PATH}" >&2
    exit 1
}

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"
xorriso -osirrox on -indev "${ISO_PATH}" \
    -extract /install.amd/vmlinuz "${VMLINUX_PATH}" \
    -extract /install.amd/initrd.gz "${INITRD_PATH}" >/dev/null 2>&1
qemu-img create -f qcow2 "${DISK_PATH}" 64G >/dev/null

timeout 45m qemu-system-x86_64 \
    -m 4096 \
    -smp 2 \
    -nographic \
    -no-reboot \
    -drive file="${DISK_PATH}",format=qcow2,if=virtio \
    -drive file="${ISO_PATH}",media=cdrom,readonly=on \
    -kernel "${VMLINUX_PATH}" \
    -initrd "${INITRD_PATH}" \
    -append "auto=true priority=critical preseed/file=/cdrom/preseed/nmos.cfg console=ttyS0,115200n8" \
    -serial "file:${INSTALL_LOG}"

grep -q 'Experimental A/B target preparation complete.' "${INSTALL_LOG}" || {
    echo "installer did not finish the experimental A/B target preparation step." >&2
    exit 1
}

timeout 4m qemu-system-x86_64 \
    -m 4096 \
    -smp 2 \
    -nographic \
    -drive file="${DISK_PATH}",format=qcow2,if=virtio \
    -serial "file:${BOOT_LOG}" || true

grep -q 'NMOS_UPDATE_HEALTH state=idle' "${BOOT_LOG}" || {
    echo "installed image did not boot into NM-OS health monitor cleanly." >&2
    exit 1
}

guestfish --rw -a "${DISK_PATH}" -i <<'EOF'
write /var/lib/nmos/update-engine/slot-state.json "{\"active_slot\": \"b\", \"inactive_slot\": \"a\", \"pending_slot\": \"b\", \"previous_slot\": \"a\", \"boot_attempts_remaining\": 1, \"installed_version\": \"test-staged\", \"staged_version\": \"test-staged\", \"last_boot_result\": \"pending\"}"
write /var/lib/nmos/update-engine/boot-intent.json "{\"pending_slot\": \"b\", \"previous_slot\": \"a\", \"boot_attempts_remaining\": 1, \"active_slot\": \"b\", \"staged_version\": \"test-staged\"}"
write /var/lib/nmos/update-engine/health-state.json "{\"state\": \"awaiting_health_ack\", \"deadline_epoch\": 1, \"pending_slot\": \"b\"}"
EOF

timeout 4m qemu-system-x86_64 \
    -m 4096 \
    -smp 2 \
    -nographic \
    -drive file="${DISK_PATH}",format=qcow2,if=virtio \
    -serial "file:${ROLLBACK_LOG}" || true

grep -q 'NMOS_UPDATE_HEALTH state=rolled_back' "${ROLLBACK_LOG}" || {
    echo "rollback simulation did not produce the expected rolled_back health marker." >&2
    exit 1
}

echo "QEMU A/B smoke passed."
