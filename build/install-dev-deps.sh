#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_TOOLS_DIR="${ROOT_DIR}/.dev-tools/quality"

if [ "$(uname -s)" != "Linux" ]; then
    echo "Development dependency installation must run on Linux or WSL2." >&2
    exit 1
fi

APT_PREFIX=()
if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || {
        echo "sudo is required to install shellcheck and python3-venv." >&2
        exit 1
    }
    APT_PREFIX=(sudo)
fi

export DEBIAN_FRONTEND=noninteractive
"${APT_PREFIX[@]}" apt-get update
"${APT_PREFIX[@]}" apt-get install -y python3-venv shellcheck

python3 -m venv "${DEV_TOOLS_DIR}"
"${DEV_TOOLS_DIR}/bin/python" -m pip install --upgrade pip
"${DEV_TOOLS_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements-dev.txt"

echo "Local smoke tooling is installed in ${DEV_TOOLS_DIR}."
echo "You can export PATH=\"${DEV_TOOLS_DIR}/bin:\$PATH\" before running smoke checks."
