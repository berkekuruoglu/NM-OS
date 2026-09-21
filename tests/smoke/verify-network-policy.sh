#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOTSTRAP_FILE="${ROOT_DIR}/config/system-overlay/usr/local/lib/nmos/network_bootstrap.py"
STATUS_FILE="${ROOT_DIR}/config/system-overlay/usr/local/lib/nmos/tor_bootstrap_status.py"

grep -q 'load_effective_system_settings' "${BOOTSTRAP_FILE}" || {
    echo "network bootstrap does not read effective system settings." >&2
    exit 1
}

grep -q 'policy == "offline"' "${BOOTSTRAP_FILE}" || {
    echo "network bootstrap does not handle offline policy." >&2
    exit 1
}

grep -q 'policy == "direct"' "${BOOTSTRAP_FILE}" || {
    echo "network bootstrap does not handle direct policy." >&2
    exit 1
}

grep -q 'write_tor_firewall_rules' "${BOOTSTRAP_FILE}" || {
    echo "network bootstrap does not keep a Tor-first firewall flow." >&2
    exit 1
}

grep -q 'redirect to :{TOR_TRANSPARENT_PORT}' "${BOOTSTRAP_FILE}" || {
    echo "network bootstrap does not transparently redirect TCP through Tor." >&2
    exit 1
}

grep -q 'redirect to :{TOR_DNS_PORT}' "${BOOTSTRAP_FILE}" || {
    echo "network bootstrap does not transparently redirect DNS through Tor." >&2
    exit 1
}

if sed -n '/^def main()/,/^if __name__/p' "${BOOTSTRAP_FILE}" | grep -q 'remove_firewall_gate'; then
    echo "network bootstrap removes Tor enforcement after bootstrap." >&2
    exit 1
fi

if grep -q 'load_boot_mode_profile' "${BOOTSTRAP_FILE}"; then
    echo "network bootstrap still reads boot mode state." >&2
    exit 1
fi

grep -q 'policy == "offline"' "${STATUS_FILE}" || {
    echo "Tor status helper does not reflect offline policy." >&2
    exit 1
}

grep -q 'policy == "direct"' "${STATUS_FILE}" || {
    echo "Tor status helper does not reflect direct policy." >&2
    exit 1
}

echo "Network policy wiring looks configured."
