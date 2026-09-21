#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '\r\n' < "${ROOT_DIR}/config/version")"
STEM="nmos-system-overlay-${VERSION}"
ARCHIVE_PATH="${ROOT_DIR}/dist/${STEM}.tar.gz"
CHECKSUM_PATH="${ROOT_DIR}/dist/${STEM}.sha256"
PACKAGES_PATH="${ROOT_DIR}/dist/${STEM}.packages"
MANIFEST_PATH="${ROOT_DIR}/dist/${STEM}.build-manifest"
RELEASE_MANIFEST_JSON_PATH="${ROOT_DIR}/dist/release-manifest.json"
UPDATE_CATALOG_PATH="${ROOT_DIR}/dist/update-catalog.json"
RELEASE_SIGNATURE_PATH="${ROOT_DIR}/dist/release-manifest.json.sig"
INSTALLER_STEM="nmos-installer-assets-${VERSION}"
INSTALLER_ARCHIVE_PATH="${ROOT_DIR}/dist/${INSTALLER_STEM}.tar.gz"
INSTALLER_CHECKSUM_PATH="${ROOT_DIR}/dist/${INSTALLER_STEM}.sha256"
INSTALLER_PACKAGES_PATH="${ROOT_DIR}/dist/${INSTALLER_STEM}.packages"
INSTALLER_ISO_STEM="nmos-installer-${VERSION}-amd64"
INSTALLER_ISO_PATH="${ROOT_DIR}/dist/${INSTALLER_ISO_STEM}.iso"
INSTALLER_ISO_CHECKSUM_PATH="${ROOT_DIR}/dist/${INSTALLER_ISO_STEM}.sha256"
RECOVERY_STEM="nmos-recovery-image-${VERSION}"
RECOVERY_ARCHIVE_PATH="${ROOT_DIR}/dist/${RECOVERY_STEM}.tar.gz"
RECOVERY_CHECKSUM_PATH="${ROOT_DIR}/dist/${RECOVERY_STEM}.sha256"
RELEASE_CHANNEL="stable"
case "${VERSION}" in
    *alpha*|*nightly*)
        RELEASE_CHANNEL="nightly"
        ;;
    *beta*|*rc*)
        RELEASE_CHANNEL="beta"
        ;;
esac

for path in \
    "${ARCHIVE_PATH}" \
    "${CHECKSUM_PATH}" \
    "${PACKAGES_PATH}" \
    "${MANIFEST_PATH}" \
    "${RELEASE_MANIFEST_JSON_PATH}" \
    "${UPDATE_CATALOG_PATH}" \
    "${INSTALLER_ARCHIVE_PATH}" \
    "${INSTALLER_CHECKSUM_PATH}" \
    "${INSTALLER_PACKAGES_PATH}" \
    "${INSTALLER_ISO_PATH}" \
    "${INSTALLER_ISO_CHECKSUM_PATH}" \
    "${RECOVERY_ARCHIVE_PATH}" \
    "${RECOVERY_CHECKSUM_PATH}"; do
    [ -s "${path}" ] || {
        echo "missing or empty artifact: ${path}" >&2
        exit 1
    }
done

command -v tar >/dev/null 2>&1 || {
    echo "missing required command: tar" >&2
    exit 1
}
command -v xorriso >/dev/null 2>&1 || {
    echo "missing required command: xorriso" >&2
    exit 1
}

sha256sum -c "${CHECKSUM_PATH}" >/dev/null
sha256sum -c "${INSTALLER_CHECKSUM_PATH}" >/dev/null
sha256sum -c "${INSTALLER_ISO_CHECKSUM_PATH}" >/dev/null
sha256sum -c "${RECOVERY_CHECKSUM_PATH}" >/dev/null
OVERLAY_SHA256="$(awk '{print $1}' "${CHECKSUM_PATH}")"
INSTALLER_ASSETS_SHA256="$(awk '{print $1}' "${INSTALLER_CHECKSUM_PATH}")"
INSTALLER_ISO_SHA256="$(awk '{print $1}' "${INSTALLER_ISO_CHECKSUM_PATH}")"
RECOVERY_IMAGE_SHA256="$(awk '{print $1}' "${RECOVERY_CHECKSUM_PATH}")"
PACKAGE_SET_SHA256="$(sha256sum "${PACKAGES_PATH}" | awk '{print $1}')"

TMP_DIR="$(mktemp -d)"
INSTALLER_TMP_DIR="$(mktemp -d)"
ISO_TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}" "${INSTALLER_TMP_DIR}" "${ISO_TMP_DIR}"' EXIT

tar -xzf "${ARCHIVE_PATH}" -C "${TMP_DIR}"
tar -xzf "${INSTALLER_ARCHIVE_PATH}" -C "${INSTALLER_TMP_DIR}"
tar -xzf "${RECOVERY_ARCHIVE_PATH}" -C "${ISO_TMP_DIR}"

for path in \
    "${TMP_DIR}/etc/dbus-1/system.d/org.nmos.Settings1.conf" \
    "${TMP_DIR}/etc/dbus-1/system.d/org.nmos.Update1.conf" \
    "${TMP_DIR}/etc/default/grub.d/90-nmos-ab.cfg" \
    "${TMP_DIR}/etc/grub.d/09_nmos_ab" \
    "${TMP_DIR}/usr/local/lib/nmos/settings_bootstrap.py" \
    "${TMP_DIR}/usr/local/lib/nmos/update_boot_health.py" \
    "${TMP_DIR}/usr/local/lib/nmos/network_bootstrap.py" \
    "${TMP_DIR}/usr/local/lib/nmos/brave_policy.py" \
    "${TMP_DIR}/usr/lib/systemd/system/nmos-settings.service" \
    "${TMP_DIR}/usr/lib/systemd/system/nmos-update-engine.service" \
    "${TMP_DIR}/usr/lib/systemd/system/nmos-update-health.service" \
    "${TMP_DIR}/usr/lib/systemd/system/nmos-settings-bootstrap.service" \
    "${TMP_DIR}/usr/lib/systemd/system/nmos-network-bootstrap.service" \
    "${TMP_DIR}/usr/lib/systemd/system/nmos-persistent-storage.service" \
    "${TMP_DIR}/usr/share/applications/nmos-control-center.desktop" \
    "${TMP_DIR}/usr/share/nmos/theme/nmos.css" \
    "${TMP_DIR}/usr/share/gdm/greeter/applications/nmos-greeter.desktop" \
    "${TMP_DIR}/etc/gdm3/PostLogin/Default"; do
    [ -f "${path}" ] || {
        echo "overlay archive is missing expected file: ${path}" >&2
        exit 1
    }
done

[ -f "${ISO_TMP_DIR}/recovery-manifest.txt" ] || {
    echo "recovery archive does not include recovery manifest metadata." >&2
    exit 1
}

for path in \
    "${ISO_TMP_DIR}/collect-diagnostics.py" \
    "${ISO_TMP_DIR}/rollback-helper.sh" \
    "${ISO_TMP_DIR}/verify-manifest.py"; do
    [ -f "${path}" ] || {
        echo "recovery archive is missing expected helper: ${path}" >&2
        exit 1
    }
done

if [ -e "${TMP_DIR}/usr/lib/systemd/system/nmos-live-user-password.service" ]; then
    echo "overlay archive still contains legacy password wiring." >&2
    exit 1
fi

if [ -e "${TMP_DIR}/usr/local/lib/nmos/ensure_live_user_password.py" ]; then
    echo "overlay archive still contains legacy password helper." >&2
    exit 1
fi

for path in \
    "${INSTALLER_TMP_DIR}/calamares/settings.conf" \
    "${INSTALLER_TMP_DIR}/calamares/branding/nmos/branding.desc" \
    "${INSTALLER_TMP_DIR}/debian-installer/preseed/nmos.cfg.in" \
    "${INSTALLER_TMP_DIR}/debian-installer/preseed/install-overlay.sh.in" \
    "${INSTALLER_TMP_DIR}/packages/base.txt"; do
    [ -f "${path}" ] || {
        echo "installer assets archive is missing expected file: ${path}" >&2
        exit 1
    }
done

xorriso -osirrox on -indev "${INSTALLER_ISO_PATH}" \
    -extract /preseed/nmos.cfg "${ISO_TMP_DIR}/nmos.cfg" \
    -extract /isolinux/txt.cfg "${ISO_TMP_DIR}/txt.cfg" \
    -extract /boot/grub/grub.cfg "${ISO_TMP_DIR}/grub.cfg" \
    -extract "/nmos/${STEM}.tar.gz" "${ISO_TMP_DIR}/overlay.tar.gz" \
    -extract "/nmos/${STEM}.packages" "${ISO_TMP_DIR}/packages.txt" \
    -extract /nmos/experimental-ab/profile.json "${ISO_TMP_DIR}/ab-profile.json" \
    -extract /nmos/experimental-ab/prepare-target.sh "${ISO_TMP_DIR}/prepare-target.sh" \
    -extract /md5sum.txt "${ISO_TMP_DIR}/md5sum.txt" >/dev/null 2>&1

cmp -s "${ISO_TMP_DIR}/overlay.tar.gz" "${ARCHIVE_PATH}" || {
    echo "installer ISO does not embed the built overlay archive." >&2
    exit 1
}

cmp -s "${ISO_TMP_DIR}/packages.txt" "${PACKAGES_PATH}" || {
    echo "installer ISO does not embed the runtime package manifest." >&2
    exit 1
}

grep -q 'pkgsel/include string' "${ISO_TMP_DIR}/nmos.cfg" || {
    echo "installer ISO preseed does not install the runtime package set." >&2
    exit 1
}

grep -q 'partman-auto/expert_recipe string' "${ISO_TMP_DIR}/nmos.cfg" || {
    echo "installer ISO preseed does not carry the unattended A/B partition recipe." >&2
    exit 1
}

[ -f "${ISO_TMP_DIR}/ab-profile.json" ] || {
    echo "installer ISO does not embed the experimental A/B profile." >&2
    exit 1
}

[ -f "${ISO_TMP_DIR}/prepare-target.sh" ] || {
    echo "installer ISO does not embed the experimental A/B target preparation helper." >&2
    exit 1
}

grep -q 'preseed/file=/cdrom/preseed/nmos.cfg' "${ISO_TMP_DIR}/txt.cfg" || {
    echo "installer ISO BIOS menu does not point at the NM-OS preseed file." >&2
    exit 1
}

grep -q 'Install NM-OS' "${ISO_TMP_DIR}/grub.cfg" || {
    echo "installer ISO UEFI menu does not expose the NM-OS entry." >&2
    exit 1
}

grep -q './preseed/nmos.cfg' "${ISO_TMP_DIR}/md5sum.txt" || {
    echo "installer ISO checksum manifest does not cover the NM-OS preseed file." >&2
    exit 1
}

grep -q "^artifact=${STEM}\.tar\.gz$" "${MANIFEST_PATH}" || {
    echo "build manifest does not record the overlay artifact." >&2
    exit 1
}
grep -q "^artifact_type=system-overlay$" "${MANIFEST_PATH}" || {
    echo "build manifest does not describe the system overlay artifact type." >&2
    exit 1
}
grep -q "^installer_assets=${INSTALLER_STEM}\.tar\.gz$" "${MANIFEST_PATH}" || {
    echo "build manifest does not record the installer assets archive." >&2
    exit 1
}
grep -q "^installer_iso=${INSTALLER_ISO_STEM}\.iso$" "${MANIFEST_PATH}" || {
    echo "build manifest does not record the installer ISO." >&2
    exit 1
}
grep -q "^installer_stack=debian-installer$" "${MANIFEST_PATH}" || {
    echo "build manifest does not record the Debian installer stack." >&2
    exit 1
}
grep -q "^installer_ui=calamares-assets$" "${MANIFEST_PATH}" || {
    echo "build manifest does not record the installer UI scaffolding." >&2
    exit 1
}
grep -q "^app_isolation=flatpak-portals$" "${MANIFEST_PATH}" || {
    echo "build manifest does not record the app isolation stack." >&2
    exit 1
}
grep -q '"schema_version": 1' "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not declare the expected schema version." >&2
    exit 1
}
grep -q "\"version\": \"${VERSION}\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the current version." >&2
    exit 1
}
grep -Eq '"release_sequence": [1-9][0-9]*' "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record a positive monotonic release sequence." >&2
    exit 1
}
grep -q "\"channel\": \"${RELEASE_CHANNEL}\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the derived release channel." >&2
    exit 1
}
grep -q "\"name\": \"${STEM}\\.tar\\.gz\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the system overlay artifact." >&2
    exit 1
}
grep -q "\"slot_image\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not define slot_image metadata." >&2
    exit 1
}
grep -q "\"url\": \"/usr/share/nmos/${STEM}\\.tar\\.gz\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not define the slot image URL." >&2
    exit 1
}
grep -q "\"sha256\": \"${OVERLAY_SHA256}\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the system overlay checksum." >&2
    exit 1
}
grep -q "\"recovery_image\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not define recovery_image metadata." >&2
    exit 1
}
grep -q "\"name\": \"${RECOVERY_STEM}\\.tar\\.gz\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the recovery image artifact." >&2
    exit 1
}
grep -q "\"sha256\": \"${RECOVERY_IMAGE_SHA256}\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the recovery image checksum." >&2
    exit 1
}
grep -q "\"name\": \"${INSTALLER_STEM}\\.tar\\.gz\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the installer assets artifact." >&2
    exit 1
}
grep -q "\"sha256\": \"${INSTALLER_ASSETS_SHA256}\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the installer assets checksum." >&2
    exit 1
}
grep -q "\"name\": \"${INSTALLER_ISO_STEM}\\.iso\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the installer ISO artifact." >&2
    exit 1
}
grep -q "\"sha256\": \"${INSTALLER_ISO_SHA256}\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the installer ISO checksum." >&2
    exit 1
}
grep -q "\"sha256\": \"${PACKAGE_SET_SHA256}\"" "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not record the package set lock digest." >&2
    exit 1
}
grep -q '"supports_rollback": true' "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not declare rollback support." >&2
    exit 1
}
grep -q '"migration"' "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not include migration metadata." >&2
    exit 1
}
grep -q '"mode": "' "${RELEASE_MANIFEST_JSON_PATH}" || {
    echo "release manifest does not describe the current signing mode." >&2
    exit 1
}
grep -q "\"${RELEASE_CHANNEL}\":" "${UPDATE_CATALOG_PATH}" || {
    echo "update catalog does not expose the current release channel." >&2
    exit 1
}
grep -q "\"version\": \"${VERSION}\"" "${UPDATE_CATALOG_PATH}" || {
    echo "update catalog does not expose the current version." >&2
    exit 1
}
grep -q '"manifest_url"' "${UPDATE_CATALOG_PATH}" || {
    echo "update catalog does not expose manifest feed URLs." >&2
    exit 1
}
grep -q '"signature_url"' "${UPDATE_CATALOG_PATH}" || {
    echo "update catalog does not expose detached signature URLs." >&2
    exit 1
}
if [ "${RELEASE_CHANNEL}" = "stable" ]; then
    grep -q '"mode": "detached-gpg"' "${RELEASE_MANIFEST_JSON_PATH}" || {
        echo "stable release manifest does not require detached-gpg signing mode." >&2
        exit 1
    }
    [ -s "${RELEASE_SIGNATURE_PATH}" ] || {
        echo "stable release is missing detached signature: ${RELEASE_SIGNATURE_PATH}" >&2
        exit 1
    }
fi

echo "Artifacts look consistent."
