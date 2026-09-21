#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMMON_SH="${ROOT_DIR}/build/lib/common.sh"
BUILD_SH="${ROOT_DIR}/build/build.sh"
VERIFY_ARTIFACTS_SH="${ROOT_DIR}/build/verify-artifacts.sh"
PRESEED_TEMPLATE="${ROOT_DIR}/config/installer/debian-installer/preseed/nmos.cfg.in"
LATE_COMMAND_TEMPLATE="${ROOT_DIR}/config/installer/debian-installer/preseed/install-overlay.sh.in"
INSTALLATION_DOC="${ROOT_DIR}/docs/installation.md"

for path in \
    "${COMMON_SH}" \
    "${BUILD_SH}" \
    "${VERIFY_ARTIFACTS_SH}" \
    "${PRESEED_TEMPLATE}" \
    "${LATE_COMMAND_TEMPLATE}" \
    "${INSTALLATION_DOC}"; do
    [ -f "${path}" ] || {
        echo "missing installer media path: ${path}" >&2
        exit 1
    }
done

grep -q 'resolve_base_installer_iso' "${COMMON_SH}" || {
    echo "build helpers do not resolve a base Debian installer ISO." >&2
    exit 1
}

grep -q 'NMOS_ALLOW_UNPINNED_BASE_ISO' "${COMMON_SH}" || {
    echo "build helpers do not expose explicit opt-in for unpinned Debian base ISO resolution." >&2
    exit 1
}

grep -q 'base ISO lock is incomplete' "${COMMON_SH}" || {
    echo "build helpers do not fail closed when base ISO lock metadata is incomplete." >&2
    exit 1
}

grep -q 'build_installer_iso_image' "${COMMON_SH}" || {
    echo "build helpers do not expose the installer ISO builder." >&2
    exit 1
}

grep -q 'chmod -R u+w "${INSTALLER_ISO_TREE_DIR}"' "${COMMON_SH}" || {
    echo "build helpers do not make extracted Debian installer files writable before patching menus." >&2
    exit 1
}

grep -q 'preseed/file=/cdrom/preseed/nmos.cfg' "${COMMON_SH}" || {
    echo "build helpers do not wire the Debian installer menus to the NM-OS preseed." >&2
    exit 1
}

grep -q 'experimental-ab' "${COMMON_SH}" || {
    echo "build helpers do not embed the experimental A/B installer payload into the ISO." >&2
    exit 1
}

grep -Fq 'sub(/^\.\//, "", path)' "${COMMON_SH}" || {
    echo "build helpers do not normalize Debian checksum paths with ./ prefixes." >&2
    exit 1
}

grep -Fq 'sub(/^\*/, "", path)' "${COMMON_SH}" || {
    echo "build helpers do not normalize Debian checksum paths with * prefixes." >&2
    exit 1
}

grep -q 'build_installer_iso_image' "${BUILD_SH}" || {
    echo "build.sh does not produce the installer ISO artifact." >&2
    exit 1
}

grep -q 'installer_iso=' "${BUILD_SH}" || {
    echo "build manifest does not record the installer ISO artifact." >&2
    exit 1
}

grep -q '@PKGSEL_INCLUDE@' "${PRESEED_TEMPLATE}" || {
    echo "installer preseed template does not accept the runtime package list." >&2
    exit 1
}

grep -q 'partman-auto/expert_recipe string' "${PRESEED_TEMPLATE}" || {
    echo "installer preseed template does not define the unattended A/B partition recipe." >&2
    exit 1
}

grep -q 'list-devices disk' "${PRESEED_TEMPLATE}" || {
    echo "installer preseed does not discover the target disk dynamically." >&2
    exit 1
}

grep -q 'debconf-set partman-auto/disk' "${PRESEED_TEMPLATE}" || {
    echo "installer preseed does not apply the dynamically discovered target disk." >&2
    exit 1
}

if grep -q '/dev/vda' "${PRESEED_TEMPLATE}"; then
    echo "installer preseed still hard-codes the QEMU-only /dev/vda target." >&2
    exit 1
fi

grep -q 'prepare-target.sh' "${PRESEED_TEMPLATE}" || {
    echo "installer preseed template does not run the experimental A/B target preparation step." >&2
    exit 1
}

grep -q 'in-target /bin/bash /root/nmos-install-overlay.sh' "${PRESEED_TEMPLATE}" || {
    echo "installer preseed template does not apply the NM-OS overlay in late_command." >&2
    exit 1
}

grep -q 'tar -xzf "${OVERLAY_ARCHIVE}" -C /' "${LATE_COMMAND_TEMPLATE}" || {
    echo "installer late-command script does not extract the NM-OS overlay." >&2
    exit 1
}

grep -q 'xorriso -osirrox on -indev' "${VERIFY_ARTIFACTS_SH}" || {
    echo "artifact verification does not inspect the built installer ISO." >&2
    exit 1
}

grep -q 'nmos-installer-<version>-amd64.iso' "${INSTALLATION_DOC}" || {
    echo "installation documentation does not mention the installer ISO artifact." >&2
    exit 1
}

echo "Installer media flow looks configured."
