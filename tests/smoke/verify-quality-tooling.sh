#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QUALITY_CONFIG="${ROOT_DIR}/pyproject.toml"
SHELLCHECK_CONFIG="${ROOT_DIR}/.shellcheckrc"
DEV_TOOLS_DIR="${ROOT_DIR}/.dev-tools/quality/bin"

[ -f "${QUALITY_CONFIG}" ] || {
    echo "missing quality config: ${QUALITY_CONFIG}" >&2
    exit 1
}

[ -f "${SHELLCHECK_CONFIG}" ] || {
    echo "missing shellcheck config: ${SHELLCHECK_CONFIG}" >&2
    exit 1
}

command -v git >/dev/null 2>&1 || {
    echo "missing required command: git" >&2
    exit 1
}

command -v ruff >/dev/null 2>&1 || {
    echo "missing required command: ruff" >&2
    exit 1
}

command -v shellcheck >/dev/null 2>&1 || {
    echo "missing required command: shellcheck" >&2
    exit 1
}

resolve_tool() {
    local name="$1"
    if command -v "${name}" >/dev/null 2>&1; then
        command -v "${name}"
        return
    fi
    if [ -x "${DEV_TOOLS_DIR}/${name}" ]; then
        echo "${DEV_TOOLS_DIR}/${name}"
        return
    fi
    echo "missing required command: ${name}" >&2
    exit 1
}

RUFF_BIN="$(resolve_tool ruff)"
MYPY_BIN="$(resolve_tool mypy)"
PYTEST_BIN="$(resolve_tool pytest)"
BANDIT_BIN="$(resolve_tool bandit)"

mapfile -t PYTHON_FILES < <(cd "${ROOT_DIR}" && git ls-files '*.py')
[ "${#PYTHON_FILES[@]}" -gt 0 ] || {
    echo "no Python files found for Ruff checks." >&2
    exit 1
}

(
    cd "${ROOT_DIR}"
    "${RUFF_BIN}" check "${PYTHON_FILES[@]}"
)

mapfile -t SHELL_FILES < <(
    cd "${ROOT_DIR}" && git ls-files \
        '*.sh' \
        'config/system-overlay/usr/local/bin/*' \
        'config/system-overlay/etc/gdm3/PostLogin/*'
)
[ "${#SHELL_FILES[@]}" -gt 0 ] || {
    echo "no shell files found for ShellCheck." >&2
    exit 1
}

(
    cd "${ROOT_DIR}"
    shellcheck --severity=error --external-sources --exclude=SC1091 "${SHELL_FILES[@]}"
)

(
    cd "${ROOT_DIR}"
    "${MYPY_BIN}" --config-file "${QUALITY_CONFIG}"
)

(
    cd "${ROOT_DIR}"
    "${BANDIT_BIN}" -q -lll -r \
        apps \
        config/system-overlay/usr/local/lib/nmos \
        config/recovery
)

"${PYTEST_BIN}" --version >/dev/null

echo "Quality tooling checks passed"
