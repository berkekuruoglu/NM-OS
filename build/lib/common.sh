#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '\r\n' < "${ROOT_DIR}/config/version")"
WORK_DIR="${ROOT_DIR}/.build/system-overlay"
ROOTFS_DIR="${WORK_DIR}/rootfs"
INSTALLER_WORK_DIR="${ROOT_DIR}/.build/installer-assets"
INSTALLER_ISO_WORK_DIR="${ROOT_DIR}/.build/installer-iso"
INSTALLER_ISO_TREE_DIR="${INSTALLER_ISO_WORK_DIR}/tree"
INSTALLER_CACHE_DIR="${ROOT_DIR}/.cache/debian-installer"
DIST_DIR="${ROOT_DIR}/dist"
SYSTEM_OVERLAY_SOURCE="${ROOT_DIR}/config/system-overlay"
SYSTEM_PACKAGES_SOURCE="${ROOT_DIR}/config/system-packages"
INSTALLER_ASSETS_SOURCE="${ROOT_DIR}/config/installer"
INSTALLER_PACKAGES_SOURCE="${ROOT_DIR}/config/installer-packages"
BASE_ISO_LOCK_FILE="${ROOT_DIR}/config/installer/base-iso.lock"
PLATFORM_ADAPTER_SOURCE="${SYSTEM_OVERLAY_SOURCE}/etc/nmos/platform-adapter.env"
INSTALLER_PRESEED_TEMPLATE="${ROOT_DIR}/config/installer/debian-installer/preseed/nmos.cfg.in"
INSTALLER_LATE_COMMAND_TEMPLATE="${ROOT_DIR}/config/installer/debian-installer/preseed/install-overlay.sh.in"
INSTALLER_BOOT_MENU_SOURCE="${ROOT_DIR}/config/installer/boot-menu"
APPS_SOURCE="${ROOT_DIR}/apps"
TARGET_PYTHON_DIR="${ROOTFS_DIR}/usr/lib/python3/dist-packages"
DEBIAN_NETINST_BASE_URL="${NMOS_DEBIAN_NETINST_BASE_URL:-https://cdimage.debian.org/debian-cd/current/amd64/iso-cd}"
VERSION_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?$'

PLATFORM_GDM_USER="Debian-gdm"
PLATFORM_SETTINGS_ADMIN_GROUP="sudo"
PLATFORM_RUNTIME_DIR="/run/nmos"
PLATFORM_STATE_DIR="/var/lib/nmos"

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "missing required command: $1" >&2
        exit 1
    }
}

is_truthy() {
    case "${1:-}" in
        1|true|TRUE|yes|YES|on|ON)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

validate_version_format() {
    local value="${1:-${VERSION}}"
    if [[ -z "${value}" ]]; then
        echo "config/version is empty." >&2
        exit 1
    fi
    if [[ ! "${value}" =~ ${VERSION_PATTERN} ]]; then
        echo "config/version has unsupported format: ${value}" >&2
        echo "expected format: MAJOR.MINOR.PATCH[-prerelease[.tag]]" >&2
        exit 1
    fi
}

release_channel_for_version() {
    local value="${1:-${VERSION}}"
    local normalized
    normalized="$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${normalized}" == *alpha* || "${normalized}" == *nightly* ]]; then
        echo "nightly"
        return
    fi
    if [[ "${normalized}" == *beta* || "${normalized}" == *rc* ]]; then
        echo "beta"
        return
    fi
    echo "stable"
}

prepare_directories() {
    mkdir -p "${ROOTFS_DIR}" "${DIST_DIR}" "${INSTALLER_WORK_DIR}" "${INSTALLER_ISO_TREE_DIR}" "${INSTALLER_CACHE_DIR}"
}

install_python_package_dir() {
    local package_dir="$1"
    if [ ! -d "${package_dir}" ]; then
        echo "missing package directory: ${package_dir}" >&2
        exit 1
    fi
    cp -a "${package_dir}" "${TARGET_PYTHON_DIR}/"
}

enable_system_service() {
    local unit_name="$1"
    local wants_dir="${ROOTFS_DIR}/etc/systemd/system/multi-user.target.wants"
    mkdir -p "${wants_dir}"
    ln -sf "/usr/lib/systemd/system/${unit_name}" "${wants_dir}/${unit_name}"
}

enable_shutdown_service() {
    local unit_name="$1"
    local target_name
    for target_name in poweroff.target reboot.target halt.target; do
        local wants_dir="${ROOTFS_DIR}/etc/systemd/system/${target_name}.wants"
        mkdir -p "${wants_dir}"
        ln -sf "/usr/lib/systemd/system/${unit_name}" "${wants_dir}/${unit_name}"
    done
}

read_platform_adapter_value() {
    local key="$1"
    if [ ! -f "${PLATFORM_ADAPTER_SOURCE}" ]; then
        return
    fi
    awk -F= -v target="${key}" '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        {
            left = $1
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", left)
            if (left != target) {
                next
            }
            right = substr($0, index($0, "=") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", right)
            gsub(/^["'\''"]|["'\''"]$/, "", right)
            print right
            exit
        }
    ' "${PLATFORM_ADAPTER_SOURCE}"
}

read_base_iso_lock_value() {
    local key="$1"
    if [ ! -f "${BASE_ISO_LOCK_FILE}" ]; then
        return
    fi
    awk -F= -v target="${key}" '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        {
            left = $1
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", left)
            if (left != target) {
                next
            }
            right = substr($0, index($0, "=") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", right)
            gsub(/^["'\''"]|["'\''"]$/, "", right)
            print right
            exit
        }
    ' "${BASE_ISO_LOCK_FILE}"
}

resolve_platform_values() {
    local value
    value="${NMOS_GDM_USER:-$(read_platform_adapter_value NMOS_GDM_USER)}"
    if [ -n "${value}" ]; then
        PLATFORM_GDM_USER="${value}"
    fi
    value="${NMOS_RUNTIME_DIR:-$(read_platform_adapter_value NMOS_RUNTIME_DIR)}"
    if [ -n "${value}" ]; then
        PLATFORM_RUNTIME_DIR="${value}"
    fi
    value="${NMOS_SETTINGS_ADMIN_GROUP:-$(read_platform_adapter_value NMOS_SETTINGS_ADMIN_GROUP)}"
    if [ -n "${value}" ]; then
        PLATFORM_SETTINGS_ADMIN_GROUP="${value}"
    fi
    value="${NMOS_STATE_DIR:-$(read_platform_adapter_value NMOS_STATE_DIR)}"
    if [ -n "${value}" ]; then
        PLATFORM_STATE_DIR="${value}"
    fi
}

escape_for_sed() {
    printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

render_platform_overlay_templates() {
    local settings_policy_file="${ROOTFS_DIR}/etc/dbus-1/system.d/org.nmos.Settings1.conf"
    local persistent_policy_file="${ROOTFS_DIR}/etc/dbus-1/system.d/org.nmos.PersistentStorage.conf"
    local tmpfiles_file="${ROOTFS_DIR}/usr/lib/tmpfiles.d/nmos.conf"
    local update_policy_file="${ROOTFS_DIR}/etc/dbus-1/system.d/org.nmos.Update1.conf"
    local settings_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-settings.service"
    local update_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-update-engine.service"
    local update_health_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-update-health.service"
    local logging_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-logging-policy.service"
    local app_isolation_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-app-isolation-policy.service"
    local device_policy_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-device-policy.service"
    local ram_wipe_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-ram-wipe-policy.service"
    local ram_wipe_shutdown_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-ram-wipe-shutdown.service"
    local persistent_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-persistent-storage.service"
    local network_service_file="${ROOTFS_DIR}/usr/lib/systemd/system/nmos-network-bootstrap.service"
    local escaped_gdm_user
    local escaped_settings_admin_group
    local escaped_runtime_dir
    local escaped_state_dir
    escaped_gdm_user="$(escape_for_sed "${PLATFORM_GDM_USER}")"
    escaped_settings_admin_group="$(escape_for_sed "${PLATFORM_SETTINGS_ADMIN_GROUP}")"
    escaped_runtime_dir="$(escape_for_sed "${PLATFORM_RUNTIME_DIR}")"
    escaped_state_dir="$(escape_for_sed "${PLATFORM_STATE_DIR}")"
    for path in \
        "${settings_policy_file}" \
        "${persistent_policy_file}" \
        "${tmpfiles_file}" \
        "${update_policy_file}" \
        "${settings_service_file}" \
        "${update_service_file}" \
        "${update_health_service_file}" \
        "${logging_service_file}" \
        "${app_isolation_service_file}" \
        "${device_policy_service_file}" \
        "${ram_wipe_service_file}" \
        "${ram_wipe_shutdown_service_file}" \
        "${persistent_service_file}" \
        "${network_service_file}"; do
        [ -f "${path}" ] || continue
        sed -i \
            -e "s/@NMOS_GDM_USER@/${escaped_gdm_user}/g" \
            -e "s/@NMOS_SETTINGS_ADMIN_GROUP@/${escaped_settings_admin_group}/g" \
            -e "s|@NMOS_RUNTIME_DIR@|${escaped_runtime_dir}|g" \
            -e "s|@NMOS_STATE_DIR@|${escaped_state_dir}|g" \
            "${path}"
    done
}

stage_system_overlay_tree() {
    prepare_directories
    rm -rf "${WORK_DIR}"
    mkdir -p "${ROOTFS_DIR}"
    rsync -a --exclude '__pycache__/' --exclude '*.pyc' --exclude '*.pyo' "${SYSTEM_OVERLAY_SOURCE}/" "${ROOTFS_DIR}/"
    resolve_platform_values
    render_platform_overlay_templates
    mkdir -p "${TARGET_PYTHON_DIR}"
    install_python_package_dir "${APPS_SOURCE}/nmos_common/nmos_common"
    install_python_package_dir "${APPS_SOURCE}/nmos_greeter/nmos_greeter"
    install_python_package_dir "${APPS_SOURCE}/nmos_persistent_storage/nmos_persistent_storage"
    install_python_package_dir "${APPS_SOURCE}/nmos_settings/nmos_settings"
    install_python_package_dir "${APPS_SOURCE}/nmos_update/nmos_update"
    install_python_package_dir "${APPS_SOURCE}/nmos_control_center/nmos_control_center"
    install_python_package_dir "${APPS_SOURCE}/nmos_help/nmos_help"
    mkdir -p "${ROOTFS_DIR}/usr/share/doc/nmos"
    if [ -d "${ROOT_DIR}/docs/user-guides" ]; then
        rsync -a "${ROOT_DIR}/docs/user-guides/" "${ROOTFS_DIR}/usr/share/doc/nmos/user-guides/"
    fi
    mkdir -p "${ROOTFS_DIR}/usr/share/nmos"
    cat > "${ROOTFS_DIR}/usr/share/nmos/build-info" <<EOF
NMOS_VERSION=${VERSION}
BUILD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
    enable_system_service "nmos-settings.service"
    enable_system_service "nmos-update-engine.service"
    enable_system_service "nmos-update-health.service"
    enable_system_service "nmos-settings-bootstrap.service"
    enable_system_service "nmos-logging-policy.service"
    enable_system_service "nmos-app-isolation-policy.service"
    enable_system_service "nmos-device-policy.service"
    enable_system_service "nmos-ram-wipe-policy.service"
    enable_shutdown_service "nmos-ram-wipe-shutdown.service"
    enable_system_service "nmos-boot-marker.service"
    enable_system_service "nmos-network-bootstrap.service"
    enable_system_service "nmos-persistent-storage.service"
    if find "${WORK_DIR}" \( -type d -name "__pycache__" -o -type f \( -name "*.pyc" -o -name "*.pyo" \) \) | grep -q .; then
        echo "staged system overlay tree contains Python cache artifacts." >&2
        exit 1
    fi
    if [ -d "${ROOTFS_DIR}/usr/local/bin" ]; then
        find "${ROOTFS_DIR}/usr/local/bin" -type f -exec chmod +x {} +
    fi
    if [ -d "${ROOTFS_DIR}/usr/local/lib/nmos" ]; then
        find "${ROOTFS_DIR}/usr/local/lib/nmos" -type f -name "*.py" -exec chmod +x {} +
        find "${ROOTFS_DIR}/usr/local/lib/nmos" -type f -name "*.sh" -exec chmod +x {} +
    fi
    if [ -d "${ROOTFS_DIR}/etc/grub.d" ]; then
        find "${ROOTFS_DIR}/etc/grub.d" -type f -exec chmod +x {} +
    fi
    if [ -d "${ROOTFS_DIR}/etc/gdm3/PostLogin" ]; then
        find "${ROOTFS_DIR}/etc/gdm3/PostLogin" -type f -exec chmod +x {} +
    fi
}

stage_installer_assets_tree() {
    prepare_directories
    rm -rf "${INSTALLER_WORK_DIR}"
    mkdir -p "${INSTALLER_WORK_DIR}"
    if [ -d "${INSTALLER_ASSETS_SOURCE}" ]; then
        rsync -a --exclude '__pycache__/' "${INSTALLER_ASSETS_SOURCE}/" "${INSTALLER_WORK_DIR}/"
    fi
    if [ -d "${INSTALLER_PACKAGES_SOURCE}" ]; then
        mkdir -p "${INSTALLER_WORK_DIR}/packages"
        rsync -a "${INSTALLER_PACKAGES_SOURCE}/" "${INSTALLER_WORK_DIR}/packages/"
    fi
}

build_output_stem() {
    echo "nmos-system-overlay-${VERSION}"
}

build_archive_name() {
    echo "$(build_output_stem).tar.gz"
}

installer_output_stem() {
    echo "nmos-installer-assets-${VERSION}"
}

installer_archive_name() {
    echo "$(installer_output_stem).tar.gz"
}

installer_iso_output_stem() {
    echo "nmos-installer-${VERSION}-amd64"
}

installer_iso_name() {
    echo "$(installer_iso_output_stem).iso"
}

resolve_base_installer_iso() {
    if [ -n "${NMOS_BASE_INSTALLER_ISO_PATH:-}" ]; then
        if [ ! -s "${NMOS_BASE_INSTALLER_ISO_PATH}" ]; then
            echo "configured base installer ISO is missing or empty: ${NMOS_BASE_INSTALLER_ISO_PATH}" >&2
            exit 1
        fi
        echo "${NMOS_BASE_INSTALLER_ISO_PATH}"
        return
    fi

    require_cmd curl
    mkdir -p "${INSTALLER_CACHE_DIR}"

    local locked_base_url="${NMOS_BASE_INSTALLER_BASE_URL:-$(read_base_iso_lock_value BASE_URL)}"
    local locked_iso_file="${NMOS_BASE_INSTALLER_ISO_FILE:-$(read_base_iso_lock_value ISO_FILE)}"
    local locked_sha256="${NMOS_BASE_INSTALLER_SHA256:-$(read_base_iso_lock_value SHA256)}"

    local iso_file=""
    local checksum_value=""
    local resolved_base_url="${DEBIAN_NETINST_BASE_URL}"
    if [ -n "${locked_base_url}" ] && [ -n "${locked_iso_file}" ] && [ -n "${locked_sha256}" ]; then
        iso_file="${locked_iso_file}"
        checksum_value="${locked_sha256}"
        resolved_base_url="${locked_base_url}"
    else
        local allow_unpinned="${NMOS_ALLOW_UNPINNED_BASE_ISO:-0}"
        if ! is_truthy "${allow_unpinned}"; then
            local missing=()
            [ -n "${locked_base_url}" ] || missing+=("BASE_URL")
            [ -n "${locked_iso_file}" ] || missing+=("ISO_FILE")
            [ -n "${locked_sha256}" ] || missing+=("SHA256")
            echo "base ISO lock is incomplete; missing keys: ${missing[*]}." >&2
            echo "set config/installer/base-iso.lock (or NMOS_BASE_INSTALLER_* env vars) for reproducible builds." >&2
            echo "to explicitly allow unpinned current Debian netinst resolution, set NMOS_ALLOW_UNPINNED_BASE_ISO=1." >&2
            exit 1
        fi
        local checksums_path="${INSTALLER_CACHE_DIR}/SHA256SUMS"
        curl -fsSL "${resolved_base_url}/SHA256SUMS" -o "${checksums_path}"
        iso_file="$(
            awk '
                $2 ~ /amd64-netinst\.iso$/ {
                    path = $2
                    sub(/^\.\//, "", path)
                    sub(/^\*/, "", path)
                    print path
                    exit
                }
            ' "${checksums_path}"
        )"
        if [ -z "${iso_file}" ]; then
            echo "could not resolve the Debian netinst ISO name from ${resolved_base_url}/SHA256SUMS" >&2
            exit 1
        fi
        checksum_value="$(
            awk -v target="${iso_file}" '
                {
                    path = $2
                    sub(/^\.\//, "", path)
                    sub(/^\*/, "", path)
                    if (path == target) {
                        print $1
                        exit
                    }
                }
            ' "${checksums_path}"
        )"
        if [ -z "${checksum_value}" ]; then
            echo "could not resolve the Debian netinst checksum for ${iso_file}" >&2
            exit 1
        fi
    fi

    local iso_path="${INSTALLER_CACHE_DIR}/${iso_file}"
    local checksum_file="${INSTALLER_CACHE_DIR}/${iso_file}.sha256"
    printf '%s  %s\n' "${checksum_value}" "${iso_file}" > "${checksum_file}"

    if [ ! -s "${iso_path}" ]; then
        if ! curl -fL "${resolved_base_url}/${iso_file}" -o "${iso_path}.tmp"; then
            rm -f "${iso_path}.tmp"
            echo "failed to download pinned Debian installer ISO: ${resolved_base_url}/${iso_file}" >&2
            exit 1
        fi
        mv "${iso_path}.tmp" "${iso_path}"
    fi

    (
        cd "${INSTALLER_CACHE_DIR}"
        sha256sum -c "${checksum_file}" >/dev/null
    )

    echo "${iso_path}"
}

installer_pkgsel_include() {
    local packages_file="$1"
    awk '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        $1 == "brave-browser" { next }
        { print $1 }
    ' "${packages_file}" | paste -sd ' ' -
}

render_installer_preseed_files() {
    local stage_dir="$1"
    local overlay_archive_path="$2"
    local packages_file_path="$3"

    local overlay_archive_name
    overlay_archive_name="$(basename "${overlay_archive_path}")"
    local packages_file_name
    packages_file_name="$(basename "${packages_file_path}")"
    local pkgsel_include
    pkgsel_include="$(installer_pkgsel_include "${packages_file_path}")"

    if [ -z "${pkgsel_include}" ]; then
        echo "installer package selection is empty." >&2
        exit 1
    fi

    mkdir -p "${stage_dir}/preseed" "${stage_dir}/nmos"
    cp "${overlay_archive_path}" "${stage_dir}/nmos/${overlay_archive_name}"
    cp "${packages_file_path}" "${stage_dir}/nmos/${packages_file_name}"
    if [ -d "${INSTALLER_ASSETS_SOURCE}/experimental-ab" ]; then
        mkdir -p "${stage_dir}/nmos/experimental-ab"
        rsync -a "${INSTALLER_ASSETS_SOURCE}/experimental-ab/" "${stage_dir}/nmos/experimental-ab/"
        if [ -f "${stage_dir}/nmos/experimental-ab/prepare-target.sh" ]; then
            sed -i -e "s|@VERSION@|${VERSION}|g" "${stage_dir}/nmos/experimental-ab/prepare-target.sh"
        fi
        find "${stage_dir}/nmos/experimental-ab" -type f -name "*.sh" -exec chmod +x {} +
    fi

    sed \
        -e "s|@PKGSEL_INCLUDE@|${pkgsel_include}|g" \
        -e "s|@OVERLAY_ARCHIVE@|${overlay_archive_name}|g" \
        -e "s|@PACKAGES_FILE@|${packages_file_name}|g" \
        "${INSTALLER_PRESEED_TEMPLATE}" > "${stage_dir}/preseed/nmos.cfg"

    sed \
        -e "s|@OVERLAY_ARCHIVE@|${overlay_archive_name}|g" \
        -e "s|@PACKAGES_FILE@|${packages_file_name}|g" \
        -e "s|@VERSION@|${VERSION}|g" \
        "${INSTALLER_LATE_COMMAND_TEMPLATE}" > "${stage_dir}/nmos/install-overlay.sh"
    chmod +x "${stage_dir}/nmos/install-overlay.sh"
}

patch_debian_installer_menu() {
    local stage_dir="$1"
    local isolinux_menu_cfg="${stage_dir}/isolinux/menu.cfg"
    local isolinux_cfg="${stage_dir}/isolinux/txt.cfg"
    local grub_cfg="${stage_dir}/boot/grub/grub.cfg"

    for path in \
        "${INSTALLER_BOOT_MENU_SOURCE}/menu.cfg" \
        "${INSTALLER_BOOT_MENU_SOURCE}/txt.cfg" \
        "${INSTALLER_BOOT_MENU_SOURCE}/grub.cfg"; do
        [ -f "${path}" ] || {
            echo "NM-OS installer boot menu is missing: ${path}" >&2
            exit 1
        }
    done

    cp "${INSTALLER_BOOT_MENU_SOURCE}/menu.cfg" "${isolinux_menu_cfg}"
    cp "${INSTALLER_BOOT_MENU_SOURCE}/txt.cfg" "${isolinux_cfg}"
    cp "${INSTALLER_BOOT_MENU_SOURCE}/grub.cfg" "${grub_cfg}"
}

refresh_installer_md5sums() {
    local stage_dir="$1"
    (
        cd "${stage_dir}"
        find . -type f ! -name 'md5sum.txt' -print0 | LC_ALL=C sort -z | xargs -0 md5sum > md5sum.txt
    )
}

build_installer_iso_image() {
    local overlay_archive_path="$1"
    local packages_file_path="$2"

    require_cmd xorriso

    local base_iso
    base_iso="$(resolve_base_installer_iso)"

    rm -rf "${INSTALLER_ISO_WORK_DIR}"
    mkdir -p "${INSTALLER_ISO_TREE_DIR}"
    xorriso -osirrox on -indev "${base_iso}" -extract / "${INSTALLER_ISO_TREE_DIR}" >/dev/null 2>&1
    if [ -d "${INSTALLER_ISO_TREE_DIR}/[BOOT]" ]; then
        rm -rf "${INSTALLER_ISO_TREE_DIR}/[BOOT]"
    fi
    chmod -R u+w "${INSTALLER_ISO_TREE_DIR}"

    render_installer_preseed_files "${INSTALLER_ISO_TREE_DIR}" "${overlay_archive_path}" "${packages_file_path}"
    patch_debian_installer_menu "${INSTALLER_ISO_TREE_DIR}"
    refresh_installer_md5sums "${INSTALLER_ISO_TREE_DIR}"

    local installer_iso_path="${DIST_DIR}/$(installer_iso_name)"
    rm -f "${installer_iso_path}"
    xorriso \
        -indev "${base_iso}" \
        -outdev "${installer_iso_path}" \
        -update_r "${INSTALLER_ISO_TREE_DIR}" / \
        -boot_image any replay \
        -changes_pending yes \
        -volid "NMOS-${VERSION}" >/dev/null 2>&1

    sha256sum "${installer_iso_path}" > "${DIST_DIR}/$(installer_iso_output_stem).sha256"
}
