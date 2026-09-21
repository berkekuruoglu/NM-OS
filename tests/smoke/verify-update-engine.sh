#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPDATE_SERVICE="${ROOT_DIR}/apps/nmos_update/nmos_update/service.py"
UPDATE_CLIENT="${ROOT_DIR}/apps/nmos_common/nmos_common/update_client.py"
UPDATE_ENGINE="${ROOT_DIR}/apps/nmos_common/nmos_common/update_engine.py"
UPDATE_POLICY="${ROOT_DIR}/config/system-overlay/etc/dbus-1/system.d/org.nmos.Update1.conf"
UPDATE_UNIT="${ROOT_DIR}/config/system-overlay/usr/lib/systemd/system/nmos-update-engine.service"
UPDATE_HEALTH_UNIT="${ROOT_DIR}/config/system-overlay/usr/lib/systemd/system/nmos-update-health.service"
UPDATE_BOOT_HEALTH="${ROOT_DIR}/config/system-overlay/usr/local/lib/nmos/update_boot_health.py"
CONTROL_CENTER_MAIN="${ROOT_DIR}/apps/nmos_control_center/nmos_control_center/main.py"

for path in \
    "${UPDATE_SERVICE}" \
    "${UPDATE_CLIENT}" \
    "${UPDATE_ENGINE}" \
    "${UPDATE_POLICY}" \
    "${UPDATE_UNIT}" \
    "${UPDATE_HEALTH_UNIT}" \
    "${UPDATE_BOOT_HEALTH}" \
    "${CONTROL_CENTER_MAIN}"; do
    [ -f "${path}" ] || {
        echo "missing update engine path: ${path}" >&2
        exit 1
    }
done

for symbol in \
    'GetStatus' \
    'GetHistory' \
    'GetChannels' \
    'CheckForUpdates' \
    'StageUpdate' \
    'CommitStagedUpdate' \
    'RollbackToPreviousSlot' \
    'AcknowledgeHealthyBoot'; do
    grep -q "${symbol}" "${UPDATE_SERVICE}" || {
        echo "update service is missing D-Bus method: ${symbol}" >&2
        exit 1
    }
done

for symbol in \
    'check_for_updates' \
    'stage_update' \
    'commit_staged_update' \
    'rollback_to_previous_slot' \
    'acknowledge_healthy_boot' \
    'process_boot_health' \
    'run_health_monitor' \
    '_verify_detached_signature' \
    '_enforce_anti_rollback' \
    '_require_manifest_fields'; do
    grep -q "${symbol}" "${UPDATE_ENGINE}" || {
        echo "update engine is missing function: ${symbol}" >&2
        exit 1
    }
done

if grep -q 'archive.extractall' "${UPDATE_ENGINE}"; then
    echo "update engine still uses unsafe bulk tar extraction." >&2
    exit 1
fi

grep -q 'release_sequence' "${UPDATE_ENGINE}" || {
    echo "update engine does not enforce monotonic signed release metadata." >&2
    exit 1
}

for symbol in \
    'self.update_client.check_for_updates' \
    'self.update_client.stage_update' \
    'self.update_client.commit_staged_update' \
    'self.update_client.rollback_to_previous_slot' \
    'Engine state:'; do
    grep -q "${symbol}" "${CONTROL_CENTER_MAIN}" || {
        echo "control center update integration is missing: ${symbol}" >&2
        exit 1
    }
done

grep -q 'org.nmos.Update1.Read' "${UPDATE_POLICY}" || {
    echo "update D-Bus policy is missing read interface." >&2
    exit 1
}

grep -q 'org.nmos.Update1.Write' "${UPDATE_POLICY}" || {
    echo "update D-Bus policy is missing write interface." >&2
    exit 1
}

echo "Update engine scaffolding checks passed."
