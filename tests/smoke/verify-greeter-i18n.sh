#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
I18N_FILE="${ROOT_DIR}/apps/nmos_common/nmos_common/i18n.py"
DESKTOP_ENTRY="${ROOT_DIR}/config/system-overlay/usr/share/applications/nmos-greeter.desktop"
GDM_DESKTOP_ENTRY="${ROOT_DIR}/config/system-overlay/usr/share/gdm/greeter/applications/nmos-greeter.desktop"

grep -q 'es_ES.UTF-8' "${I18N_FILE}" || {
    echo "Greeter language selector does not include Spanish." >&2
    exit 1
}

for unsupported_locale in tr_TR.UTF-8 de_DE.UTF-8 fr_FR.UTF-8; do
    if grep -q "${unsupported_locale}" "${I18N_FILE}"; then
        echo "Greeter language selector still exposes an incomplete locale: ${unsupported_locale}" >&2
        exit 1
    fi
done

grep -q '^Name\[es\]=' "${DESKTOP_ENTRY}" || {
    echo "Desktop entry does not expose a Spanish display name." >&2
    exit 1
}

grep -q '^Name\[es\]=' "${GDM_DESKTOP_ENTRY}" || {
    echo "GDM desktop entry does not expose a Spanish display name." >&2
    exit 1
}

PYTHONDONTWRITEBYTECODE=1 NMOS_ROOT="${ROOT_DIR}" python3 - <<'PY'
import os
import sys
from pathlib import Path

root = Path(os.environ["NMOS_ROOT"])
sys.path.insert(0, str(root / "apps" / "nmos_common"))

from nmos_common.i18n import (
    TRANSLATIONS,
    display_language_name,
    display_network_policy_name,
    posture_explanation_lines,
    resolve_supported_locale,
    translate,
    translate_message,
)
from nmos_common.system_settings import describe_posture_preview

assert resolve_supported_locale("es_MX.UTF-8") == "es_ES.UTF-8"
assert display_language_name("es_ES.UTF-8") == "Español"
assert resolve_supported_locale("tr_TR.UTF-8") == "en_US.UTF-8"
assert translate("es_ES.UTF-8", "Language") == "Idioma"
assert translate("es_ES.UTF-8", "Apply settings") == "Aplicar ajustes"
assert translate("es_ES.UTF-8", "Security profile") == "Perfil de seguridad"
assert translate("es_ES.UTF-8", "Review") == "Resumen"
assert display_network_policy_name("direct", locale="es_ES.UTF-8") == "Red directa"
assert translate_message("es_ES.UTF-8", "Tor is ready") == "Tor está listo"
posture = describe_posture_preview("balanced", {"network_policy": "direct", "allow_brave_browser": True})
assert any("red directa" in line.lower() for line in posture_explanation_lines("es_ES.UTF-8", posture))
assert "Ã" not in translate("es_ES.UTF-8", "NM-OS Setup")
for key, value in TRANSLATIONS.get("es", {}).items():
    assert "Ã" not in key and "Â" not in key and "�" not in key
    assert "Ã" not in value and "Â" not in value and "�" not in value
assert translate("de_DE.UTF-8", "Language") == "Language"

print("Greeter i18n checks passed")
PY

PYTHONDONTWRITEBYTECODE=1 python3 "${ROOT_DIR}/scripts/check_i18n_quality.py"
