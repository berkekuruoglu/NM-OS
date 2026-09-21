#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

if [ "$(uname -s)" != "Linux" ]; then
    echo "NM-OS build must run on Linux." >&2
    exit 1
fi

require_cmd rsync
require_cmd tar
require_cmd sha256sum
require_cmd grep
require_cmd curl
require_cmd xorriso
validate_version_format "${VERSION}"

bash "${ROOT_DIR}/build/verify-no-leaks.sh"
stage_system_overlay_tree
stage_installer_assets_tree

ENABLED_FEATURES=()
if [ "${NMOS_ENABLE_BRAVE:-0}" = "1" ]; then
    mkdir -p "${ROOTFS_DIR}/etc/nmos/features"
    cat > "${ROOTFS_DIR}/etc/nmos/features/brave" <<'EOF'
enabled=true
privacy_mode=optional
anonymity_warning=Brave is privacy-focused but not equivalent to Tor Browser anonymity.
EOF
    ENABLED_FEATURES+=("brave")
fi

FEATURES_VALUE="none"
if [ "${#ENABLED_FEATURES[@]}" -gt 0 ]; then
    FEATURES_VALUE="$(IFS=,; echo "${ENABLED_FEATURES[*]}")"
fi

OUTPUT_STEM="$(build_output_stem)"
ARCHIVE_NAME="$(build_archive_name)"
ARCHIVE_PATH="${DIST_DIR}/${ARCHIVE_NAME}"
INSTALLER_STEM="$(installer_output_stem)"
INSTALLER_ARCHIVE_NAME="$(installer_archive_name)"
INSTALLER_ARCHIVE_PATH="${DIST_DIR}/${INSTALLER_ARCHIVE_NAME}"
INSTALLER_ISO_STEM="$(installer_iso_output_stem)"
INSTALLER_ISO_NAME="$(installer_iso_name)"
INSTALLER_ISO_PATH="${DIST_DIR}/${INSTALLER_ISO_NAME}"
RECOVERY_STEM="nmos-recovery-image-${VERSION}"
RECOVERY_ARCHIVE_NAME="${RECOVERY_STEM}.tar.gz"
RECOVERY_ARCHIVE_PATH="${DIST_DIR}/${RECOVERY_ARCHIVE_NAME}"
BUILD_TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
BUILD_ID="$(date -u +"%Y%m%dT%H%M%SZ")-${VERSION}"
RELEASE_SEQUENCE="${NMOS_RELEASE_SEQUENCE:-$(date -u +"%Y%m%d%H%M%S")}"
case "${RELEASE_SEQUENCE}" in
    ""|*[!0-9]*)
        echo "NMOS_RELEASE_SEQUENCE must be a positive integer." >&2
        exit 1
        ;;
esac
if [ "${RELEASE_SEQUENCE}" -le 0 ]; then
    echo "NMOS_RELEASE_SEQUENCE must be greater than zero." >&2
    exit 1
fi
RELEASE_CHANNEL="$(release_channel_for_version "${VERSION}")"
MINIMUM_SOURCE_VERSION="${NMOS_MINIMUM_SOURCE_VERSION:-}"
if [ -z "${MINIMUM_SOURCE_VERSION}" ]; then
    VERSION_CORE="${VERSION%%-*}"
    IFS=. read -r VERSION_MAJOR VERSION_MINOR _ <<< "${VERSION_CORE}"
    MINIMUM_SOURCE_VERSION="${VERSION_MAJOR:-0}.${VERSION_MINOR:-0}.0"
fi
SIGNING_MODE="checksum"
SIGNATURE_VERIFIED="false"
SIGNING_KEY_ID=""
SIGNING_NOTES="Detached signatures are not generated in this build."
if command -v gpg >/dev/null 2>&1 && [ -n "${NMOS_UPDATE_SIGNING_KEY_ID:-}" ]; then
    SIGNING_MODE="detached-gpg"
    SIGNATURE_VERIFIED="true"
    SIGNING_KEY_ID="${NMOS_UPDATE_SIGNING_KEY_ID}"
    SIGNING_NOTES="Release manifest is signed with a detached GPG signature."
fi

tar -C "${ROOTFS_DIR}" -czf "${ARCHIVE_PATH}" .
tar -C "${INSTALLER_WORK_DIR}" -czf "${INSTALLER_ARCHIVE_PATH}" .
RECOVERY_STAGE_DIR="${ROOT_DIR}/.build/recovery-image"
rm -rf "${RECOVERY_STAGE_DIR}"
mkdir -p "${RECOVERY_STAGE_DIR}"
if [ -d "${ROOT_DIR}/config/recovery" ]; then
    rsync -a "${ROOT_DIR}/config/recovery/" "${RECOVERY_STAGE_DIR}/"
fi
cat > "${RECOVERY_STAGE_DIR}/recovery-manifest.txt" <<EOF
version=${VERSION}
build_id=${BUILD_ID}
channel=${RELEASE_CHANNEL}
created_at=${BUILD_TIMESTAMP}
EOF
tar -C "${RECOVERY_STAGE_DIR}" -czf "${RECOVERY_ARCHIVE_PATH}" .
sha256sum "${ARCHIVE_PATH}" > "${DIST_DIR}/${OUTPUT_STEM}.sha256"
sha256sum "${INSTALLER_ARCHIVE_PATH}" > "${DIST_DIR}/${INSTALLER_STEM}.sha256"
sha256sum "${RECOVERY_ARCHIVE_PATH}" > "${DIST_DIR}/${RECOVERY_STEM}.sha256"

cp "${SYSTEM_PACKAGES_SOURCE}/base.txt" "${DIST_DIR}/${OUTPUT_STEM}.packages"
if [ "${NMOS_ENABLE_BRAVE:-0}" = "1" ]; then
    cat "${SYSTEM_PACKAGES_SOURCE}/optional-brave.txt" >> "${DIST_DIR}/${OUTPUT_STEM}.packages"
fi
if [ -f "${INSTALLER_PACKAGES_SOURCE}/base.txt" ]; then
    cp "${INSTALLER_PACKAGES_SOURCE}/base.txt" "${DIST_DIR}/${INSTALLER_STEM}.packages"
fi

build_installer_iso_image "${ARCHIVE_PATH}" "${DIST_DIR}/${OUTPUT_STEM}.packages"

OVERLAY_SHA256="$(awk '{print $1}' "${DIST_DIR}/${OUTPUT_STEM}.sha256")"
INSTALLER_ASSETS_SHA256="$(awk '{print $1}' "${DIST_DIR}/${INSTALLER_STEM}.sha256")"
INSTALLER_ISO_SHA256="$(awk '{print $1}' "${DIST_DIR}/${INSTALLER_ISO_STEM}.sha256")"
RECOVERY_IMAGE_SHA256="$(awk '{print $1}' "${DIST_DIR}/${RECOVERY_STEM}.sha256")"
PACKAGE_SET_SHA256="$(sha256sum "${DIST_DIR}/${OUTPUT_STEM}.packages" | awk '{print $1}')"
INSTALLER_BASE_NAME="$(basename "$(resolve_base_installer_iso)")"

cat > "${DIST_DIR}/${OUTPUT_STEM}.build-manifest" <<EOF
version=${VERSION}
artifact=${ARCHIVE_NAME}
build_host=$(hostname)
built_at=${BUILD_TIMESTAMP}
build_id=${BUILD_ID}
channel=${RELEASE_CHANNEL}
source_repo=https://github.com/berkekuruoglu/NM-OS.git
artifact_type=system-overlay
installer_assets=${INSTALLER_ARCHIVE_NAME}
installer_iso=${INSTALLER_ISO_NAME}
installer_stack=debian-installer
installer_ui=calamares-assets
installer_base=${INSTALLER_BASE_NAME}
app_isolation=flatpak-portals
features=${FEATURES_VALUE}
EOF

cat > "${DIST_DIR}/release-manifest.json" <<EOF
{
  "schema_version": 1,
  "product": "NM-OS",
  "version": "${VERSION}",
  "release_sequence": ${RELEASE_SEQUENCE},
  "channel": "${RELEASE_CHANNEL}",
  "build_id": "${BUILD_ID}",
  "released_at": "${BUILD_TIMESTAMP}",
  "source_repo": "https://github.com/berkekuruoglu/NM-OS.git",
  "artifacts": {
    "slot_image": {
      "name": "${ARCHIVE_NAME}",
      "sha256": "${OVERLAY_SHA256}",
      "url": "/usr/share/nmos/${ARCHIVE_NAME}"
    },
    "recovery_image": {
      "name": "${RECOVERY_ARCHIVE_NAME}",
      "sha256": "${RECOVERY_IMAGE_SHA256}",
      "url": "/usr/share/nmos/${RECOVERY_ARCHIVE_NAME}"
    },
    "system_overlay": {
      "name": "${ARCHIVE_NAME}",
      "sha256": "${OVERLAY_SHA256}"
    },
    "installer_assets": {
      "name": "${INSTALLER_ARCHIVE_NAME}",
      "sha256": "${INSTALLER_ASSETS_SHA256}"
    },
    "installer_iso": {
      "name": "${INSTALLER_ISO_NAME}",
      "sha256": "${INSTALLER_ISO_SHA256}"
    }
  },
  "package_set_lock": {
    "name": "${OUTPUT_STEM}.packages",
    "sha256": "${PACKAGE_SET_SHA256}"
  },
  "upgrade_policy": {
    "minimum_source_version": "${MINIMUM_SOURCE_VERSION}",
    "supports_rollback": true,
    "rollback_scope": "slot-based"
  },
  "migration": {
    "bundle_id": "${BUILD_ID}"
  },
  "signing": {
    "mode": "${SIGNING_MODE}",
    "signature_verified": ${SIGNATURE_VERIFIED},
    "key_id": "${SIGNING_KEY_ID}",
    "notes": "${SIGNING_NOTES}"
  }
}
EOF

if command -v gpg >/dev/null 2>&1 && [ -n "${NMOS_UPDATE_SIGNING_KEY_ID:-}" ]; then
    gpg --batch --yes --armor --detach-sign \
        --local-user "${NMOS_UPDATE_SIGNING_KEY_ID}" \
        --output "${DIST_DIR}/release-manifest.json.sig" \
        "${DIST_DIR}/release-manifest.json"
fi

if [ "${RELEASE_CHANNEL}" = "stable" ] && [ ! -s "${DIST_DIR}/release-manifest.json.sig" ]; then
    if [ "${NMOS_ALLOW_UNSIGNED_STABLE_RELEASE:-0}" != "1" ]; then
        echo "stable release requires detached signature: dist/release-manifest.json.sig" >&2
        echo "set NMOS_UPDATE_SIGNING_KEY_ID or explicitly opt in with NMOS_ALLOW_UNSIGNED_STABLE_RELEASE=1" >&2
        exit 1
    fi
fi

RELEASE_MANIFEST_SHA256="$(sha256sum "${DIST_DIR}/release-manifest.json" | awk '{print $1}')"

stable_version=""
stable_notes="No stable release published in the local catalog."
beta_version=""
beta_notes="No beta release published in the local catalog."
nightly_version=""
nightly_notes="No nightly release published in the local catalog."

case "${RELEASE_CHANNEL}" in
    stable)
        stable_version="${VERSION}"
        stable_notes="Local stable catalog entry generated from release-manifest.json."
        ;;
    beta)
        beta_version="${VERSION}"
        beta_notes="Local beta catalog entry generated from release-manifest.json."
        ;;
    nightly)
        nightly_version="${VERSION}"
        nightly_notes="Local nightly catalog entry generated from release-manifest.json."
        ;;
esac

cat > "${DIST_DIR}/update-catalog.json" <<EOF
{
  "schema_version": 1,
  "generated_at": "${BUILD_TIMESTAMP}",
  "channels": {
    "stable": {
      "version": "${stable_version}",
      "notes": "${stable_notes}",
      "manifest_url": "/usr/share/nmos/release-manifest.json",
      "manifest_sha256": "${RELEASE_MANIFEST_SHA256}",
      "signature_url": "/usr/share/nmos/release-manifest.json.sig"
    },
    "beta": {
      "version": "${beta_version}",
      "notes": "${beta_notes}",
      "manifest_url": "/usr/share/nmos/release-manifest.json",
      "manifest_sha256": "${RELEASE_MANIFEST_SHA256}",
      "signature_url": "/usr/share/nmos/release-manifest.json.sig"
    },
    "nightly": {
      "version": "${nightly_version}",
      "notes": "${nightly_notes}",
      "manifest_url": "/usr/share/nmos/release-manifest.json",
      "manifest_sha256": "${RELEASE_MANIFEST_SHA256}",
      "signature_url": "/usr/share/nmos/release-manifest.json.sig"
    }
  }
}
EOF

bash "${ROOT_DIR}/build/verify-artifacts.sh"

echo "Build complete: ${ARCHIVE_PATH}"
echo "Installer ISO complete: ${INSTALLER_ISO_PATH}"
