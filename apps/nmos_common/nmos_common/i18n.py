from __future__ import annotations

import re

DEFAULT_UI_LOCALE = "en_US.UTF-8"
LANGUAGE_OPTIONS = (
    (DEFAULT_UI_LOCALE, "English"),
    ("es_ES.UTF-8", "Español"),
)

LANGUAGE_LABELS = {locale: label for locale, label in LANGUAGE_OPTIONS}

NETWORK_POLICY_TITLES = {
    "tor": "Tor-first",
    "direct": "Direct network",
    "offline": "Offline",
}

SANDBOX_TITLES = {
    "standard": "Standard",
    "focused": "Focused",
    "strict": "Strict",
}

DEVICE_POLICY_TITLES = {
    "shared": "Shared devices",
    "prompt": "Prompt first",
    "locked": "Locked down",
}

LOGGING_POLICY_TITLES = {
    "balanced": "Balanced",
    "minimal": "Minimal",
    "sealed": "Sealed",
}

THEME_PROFILE_TITLES = {
    "nmos-classic": "Classic Signal",
    "nmos-night": "Night Console",
    "nmos-light": "Light Grid",
}

ACCENT_TITLES = {
    "amber": "Amber",
    "cyan": "Cyan",
    "mint": "Mint",
    "rose": "Rose",
}

DENSITY_TITLES = {
    "comfortable": "Comfortable",
    "compact": "Compact",
}

MOTION_TITLES = {
    "full": "Full motion",
    "reduced": "Reduced motion",
}

DEFAULT_BROWSER_TITLES = {
    "firefox-esr": "Firefox",
    "chromium": "Chromium",
    "none": "No default browser",
}

TRANSLATIONS = {
    "es": {
        "NM-OS Setup": "Configuración de NM-OS",
        "Review your privacy and desktop settings before login.": "Revisa tus ajustes de privacidad y escritorio antes de iniciar sesión.",
        "Language": "Idioma",
        "Choose the interface language.": "Elige el idioma de la interfaz.",
        "Keyboard": "Teclado",
        "Choose the keyboard layout.": "Elige la distribución del teclado.",
        "Security profile": "Perfil de seguridad",
        "Choose a starting point. You can still fine-tune it later from the desktop.": "Elige un punto de partida. Luego podrás ajustarlo mejor desde el escritorio.",
        "Relaxed": "Relajado",
        "Balanced": "Equilibrado",
        "Hardened": "Reforzado",
        "Maximum": "Máximo",
        "More convenience, fewer guards, direct networking by default.": "Más comodidad, menos barreras y red directa por defecto.",
        "Recommended privacy defaults with direct networking and strong tracking protection.": "Valores de privacidad recomendados con red directa y fuerte protección contra rastreo.",
        "A private Tor-routed workspace with stricter isolation and device policy.": "Un espacio privado enrutado por Tor con aislamiento y política de dispositivos más estrictos.",
        "Highest practical protection with strong restrictions and offline defaults.": "La protección práctica más alta con restricciones fuertes y modo sin conexión por defecto.",
        "Best for people who want the easiest daily desktop experience.": "Ideal para quienes quieren la experiencia diaria de escritorio más sencilla.",
        "You gain convenience and compatibility, but the default trust boundaries are lighter.": "Ganas comodidad y compatibilidad, pero los límites de confianza por defecto son más ligeros.",
        "Best for privacy-conscious people who want a practical daily Linux desktop.": "Ideal para personas conscientes de la privacidad que quieren un escritorio Linux práctico para el día a día.",
        "It keeps broad website compatibility while tightening app, device, logging, and browser privacy defaults.": "Mantiene una amplia compatibilidad web mientras refuerza la privacidad de aplicaciones, dispositivos, registros y navegador.",
        "Best for people who want stronger daily protection and are comfortable with extra friction.": "Ideal para quienes quieren una protección diaria más fuerte y aceptan una fricción adicional.",
        "You get tighter defaults, but compatibility and convenience start to narrow.": "Obtienes valores más estrictos, pero la compatibilidad y la comodidad empiezan a reducirse.",
        "Best for high-sensitivity situations where minimizing exposure matters more than convenience.": "Ideal para situaciones de alta sensibilidad donde minimizar la exposición importa más que la comodidad.",
        "This profile is intentionally restrictive and expects the user to work around missing convenience.": "Este perfil es intencionalmente restrictivo y espera que la persona usuaria acepte la falta de comodidad.",
        "Network": "Red",
        "Choose how NM-OS should treat the network.": "Elige cómo debe tratar NM-OS la red.",
        "Network policy": "Política de red",
        "Allow Brave Browser when installed": "Permitir Brave Browser cuando esté instalado",
        "Refresh network status": "Actualizar estado de la red",
        "Appearance": "Apariencia",
        "Keep the visual language intentional. A few curated options go a long way.": "Mantén un lenguaje visual intencional. Unas pocas opciones bien elegidas rinden mucho.",
        "Classic Signal": "Señal clásica",
        "Night Console": "Consola nocturna",
        "Light Grid": "Cuadrícula clara",
        "Amber": "Ámbar",
        "Cyan": "Cian",
        "Mint": "Menta",
        "Rose": "Rosa",
        "Comfortable": "Cómodo",
        "Compact": "Compacto",
        "Full motion": "Movimiento completo",
        "Reduced motion": "Movimiento reducido",
        "Standard": "Estándar",
        "Focused": "Enfocado",
        "Strict": "Estricto",
        "Shared devices": "Dispositivos compartidos",
        "Prompt first": "Primero preguntar",
        "Locked down": "Bloqueado",
        "Enabled": "Activado",
        "Disabled": "Desactivado",
        "Manual lock": "Bloqueo manual",
        "{minutes} min auto-lock": "Bloqueo automático de {minutes} min",
        "Unlock on login: enabled": "Desbloqueo al iniciar sesión: activado",
        "Unlock on login: disabled": "Desbloqueo al iniciar sesión: desactivado",
        "Change details (now):": "Detalles de cambio (ahora):",
        "Change details (after reboot):": "Detalles de cambio (tras reinicio):",
        "{setting}: {before} -> {after}": "{setting}: {before} -> {after}",
        "Encrypted Vault": "Bóveda cifrada",
        "Create or unlock an encrypted vault for sensitive files.": "Crea o desbloquea una bóveda cifrada para archivos sensibles.",
        "Review": "Resumen",
        "A few changes can apply right away. Network and deeper security policy changes may wait until reboot.": "Algunos cambios se aplican de inmediato. La red y las políticas de seguridad más profundas pueden esperar hasta reiniciar.",
        "Create": "Crear",
        "Unlock": "Desbloquear",
        "Lock": "Bloquear",
        "Repair": "Reparar",
        "Back": "Atrás",
        "Next": "Siguiente",
        "Skip setup": "Saltar configuración",
        "Start using NM-OS": "Empezar a usar NM-OS",
        "Apply settings": "Aplicar ajustes",
        "Tor-first": "Tor primero",
        "Direct network": "Red directa",
        "Offline": "Sin conexión",
        "Waiting for Tor": "Esperando a Tor",
        "Tor is ready": "Tor está listo",
        "Waiting for Tor bootstrap": "Esperando el arranque de Tor",
        "Waiting for Tor control": "Esperando el control de Tor",
        "Preparing network policy": "Preparando la política de red",
        "Network bootstrap failed": "Falló el arranque de la red",
        "Direct network access is enabled by system settings.": "El acceso directo a la red está habilitado por la configuración del sistema.",
        "Network is disabled by current settings.": "La red está desactivada por la configuración actual.",
        "Unable to read network status": "No se pudo leer el estado de la red",
        "invalid status payload": "la carga del estado no es válida",
        "Network status: {error}": "Estado de la red: {error}",
        "Networking is currently disabled.": "La red está actualmente desactivada.",
        "Direct network access is enabled.": "El acceso directo a la red está habilitado.",
        "Tor connection is ready.": "La conexión Tor está lista.",
        "Waiting for Tor to become ready.": "Esperando a que Tor esté listo.",
        "Unable to save pending settings: {error}": "No se pudieron guardar los ajustes pendientes: {error}",
        "Language will be applied as {language}.": "El idioma se aplicará como {language}.",
        "Keyboard layout will be applied as {layout}.": "La distribución del teclado se aplicará como {layout}.",
        "Network policy will be applied as {policy}.": "La política de red se aplicará como {policy}.",
        "Profile: {profile}": "Perfil: {profile}",
        "Language: {language}": "Idioma: {language}",
        "Keyboard: {keyboard}": "Teclado: {keyboard}",
        "Network: {network}": "Red: {network}",
        "Theme: {theme}": "Tema: {theme}",
        "Default browser: {browser}": "Navegador predeterminado: {browser}",
        "Accent: {accent}": "Acento: {accent}",
        "Brave visibility: allowed when installed": "Brave visible cuando esté instalado",
        "Brave visibility: hidden": "Brave oculto",
        "Restart required for: {pending}": "Reinicio necesario para: {pending}",
        "The current draft does not require a reboot.": "La configuración actual no requiere reinicio.",
        "Encrypted vault backend unavailable: {error}": "El servicio de la bóveda cifrada no está disponible: {error}",
        "Encrypted vault error: {error}": "Error de la bóveda cifrada: {error}",
        "Encrypted vault activity is in progress.": "Hay una actividad en curso en la bóveda cifrada.",
        "Encrypted vault is unlocked and ready.": "La bóveda cifrada está desbloqueada y lista.",
        "Encrypted vault exists at {path} and can be unlocked.": "La bóveda cifrada existe en {path} y se puede desbloquear.",
        "Encrypted vault cannot be created because the system disk does not have enough free space.": "No se puede crear la bóveda cifrada porque el disco del sistema no tiene suficiente espacio libre.",
        "Encrypted vault can be created at {path}.": "La bóveda cifrada se puede crear en {path}.",
        "Encrypted vault already exists at {path}.": "La bóveda cifrada ya existe en {path}.",
        "Encrypted vault state is unavailable.": "El estado de la bóveda cifrada no está disponible.",
        "the encrypted vault": "la bóveda cifrada",
        "Encrypted vault action {action} is still running. Please wait.": "La acción {action} de la bóveda cifrada sigue en curso. Espera por favor.",
        "Encrypted vault status is refreshing. Please wait.": "Se está actualizando el estado de la bóveda cifrada. Espera por favor.",
        "Encrypted vault action {action} is in progress...": "La acción {action} de la bóveda cifrada está en curso...",
        "Starting encrypted vault action {action}...": "Iniciando la acción {action} de la bóveda cifrada...",
        "Encrypted vault action {action} failed: {error}": "La acción {action} de la bóveda cifrada falló: {error}",
        "Encrypted vault action {action} completed.": "La acción {action} de la bóveda cifrada se completó.",
        "Encrypted vault activity is still running.": "La actividad de la bóveda cifrada aún continúa.",
        "Failed to save system settings: {error}": "No se pudieron guardar los ajustes del sistema: {error}",
        "Settings saved. Some privacy changes apply on the next boot.": "Los ajustes se guardaron. Algunos cambios de privacidad se aplicarán en el próximo arranque.",
        "Setup pages skipped. Review summary and click Start using NM-OS.": "Se omitieron las páginas de configuración. Revisa el resumen y haz clic en Empezar a usar NM-OS.",
        "internal error": "error interno",
        "Tor-first networking lowers direct exposure and keeps a privacy-first default.": "La red priorizando Tor reduce la exposición directa y mantiene un valor por defecto centrado en la privacidad.",
        "Direct networking keeps the desktop familiar and compatible, but reduces anonymity and network separation.": "La red directa mantiene el escritorio familiar y compatible, pero reduce el anonimato y la separación de red.",
        "Offline mode blocks network access until you intentionally relax the policy.": "El modo sin conexión bloquea el acceso a la red hasta que relajes la política de forma intencional.",
        "Standard app isolation keeps compatibility high, with fewer default restrictions.": "El aislamiento estándar de apps mantiene una alta compatibilidad, con menos restricciones por defecto.",
        "Focused app isolation balances compatibility with clearer containment boundaries.": "El aislamiento enfocado de apps equilibra la compatibilidad con límites de contención más claros.",
        "Strict app isolation raises containment, but more workflows may need adjustment.": "El aislamiento estricto de apps aumenta la contención, pero más flujos de trabajo pueden necesitar ajustes.",
        "Shared device access keeps removable media easy to use, but trusts more by default.": "El acceso compartido a dispositivos mantiene el uso sencillo de medios extraíbles, pero confía más por defecto.",
        "Prompt-first device access asks before trusting new external devices.": "El acceso a dispositivos con confirmación pide permiso antes de confiar en nuevos dispositivos externos.",
        "Locked device access reduces trust in external devices and prioritizes containment.": "El acceso bloqueado a dispositivos reduce la confianza en dispositivos externos y prioriza la contención.",
        "Balanced logging retains more diagnostics for troubleshooting.": "El registro equilibrado conserva más diagnósticos para resolver problemas.",
        "Minimal logging limits retained traces while keeping day-to-day debugging workable.": "El registro mínimo limita los rastros conservados mientras mantiene viable la depuración diaria.",
        "Sealed logging minimizes retained traces and favors privacy over diagnostics.": "El registro sellado minimiza los rastros conservados y prioriza la privacidad sobre el diagnóstico.",
        "Vault locking is manual, which is convenient but easier to forget.": "El bloqueo de la bóveda es manual, lo que es cómodo pero más fácil de olvidar.",
        "Vault auto-locks after {minutes} minutes to reduce accidental exposure.": "La bóveda se bloquea automáticamente después de {minutes} minutos para reducir la exposición accidental.",
        "Vault unlock on login favors convenience over separation.": "Desbloquear la bóveda al iniciar sesión favorece la comodidad sobre la separación.",
        "Vault stays locked until you explicitly unlock it.": "La bóveda permanece bloqueada hasta que la desbloquees explícitamente.",
        "Brave can appear when it is installed and the selected network policy allows it.": "Brave puede mostrarse cuando está instalado y la política de red seleccionada lo permite.",
        "Brave stays hidden unless you explicitly allow it.": "Brave permanece oculto salvo que lo permitas explícitamente.",
        "Applies now: {changes}": "Se aplica ahora: {changes}",
        "Applies after reboot: {changes}": "Se aplica después de reiniciar: {changes}",
        "No changed settings in the current draft.": "No hay cambios en la configuración actual.",
        "None": "Ninguno",
        "Brave visibility": "Visibilidad de Brave",
        "Default app isolation": "Aislamiento por defecto de apps",
        "Vault behavior": "Comportamiento de la bóveda",
        "Theme profile": "Perfil de tema",
        "Motion": "Movimiento",
        "Default browser": "Navegador predeterminado",
        "No default browser": "Sin navegador predeterminado",
        "Protection level: {level}/10": "Nivel de protección: {level}/10",
        "Convenience level: {level}/10": "Nivel de comodidad: {level}/10",
        "Current balance favors stronger protection.": "El balance actual favorece una protección más fuerte.",
        "Current balance favors convenience.": "El balance actual favorece la comodidad.",
        "Current balance is relatively even.": "El balance actual está relativamente equilibrado.",
        "Shift vs current system: protection {protection}, convenience {convenience}": "Cambio respecto al sistema actual: protección {protection}, comodidad {convenience}",
    }
}

NETWORK_POLICY_EXPLANATIONS = {
    "tor": "Tor-first networking lowers direct exposure and keeps a privacy-first default.",
    "direct": "Direct networking keeps the desktop familiar and compatible, but reduces anonymity and network separation.",
    "offline": "Offline mode blocks network access until you intentionally relax the policy.",
}

SANDBOX_EXPLANATIONS = {
    "standard": "Standard app isolation keeps compatibility high, with fewer default restrictions.",
    "focused": "Focused app isolation balances compatibility with clearer containment boundaries.",
    "strict": "Strict app isolation raises containment, but more workflows may need adjustment.",
}

DEVICE_EXPLANATIONS = {
    "shared": "Shared device access keeps removable media easy to use, but trusts more by default.",
    "prompt": "Prompt-first device access asks before trusting new external devices.",
    "locked": "Locked device access reduces trust in external devices and prioritizes containment.",
}

LOGGING_EXPLANATIONS = {
    "balanced": "Balanced logging retains more diagnostics for troubleshooting.",
    "minimal": "Minimal logging limits retained traces while keeping day-to-day debugging workable.",
    "sealed": "Sealed logging minimizes retained traces and favors privacy over diagnostics.",
}


def locale_language(locale: str | None) -> str:
    text = str(locale or "").strip()
    if not text:
        return ""
    return re.split(r"[_@.]", text, maxsplit=1)[0].lower()


def _repair_mojibake(text: str) -> str:
    if "\u00c3" not in text and "\u00c2" not in text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def resolve_supported_locale(locale: str | None, default: str = DEFAULT_UI_LOCALE) -> str:
    text = str(locale or "").strip()
    if not text:
        return default
    for supported, _label in LANGUAGE_OPTIONS:
        if text.lower() == supported.lower():
            return supported
    language = locale_language(text)
    for supported, _label in LANGUAGE_OPTIONS:
        if locale_language(supported) == language:
            return supported
    return default


def display_language_name(locale: str | None) -> str:
    resolved = resolve_supported_locale(locale)
    return _repair_mojibake(LANGUAGE_LABELS.get(resolved, resolved))


def translate(locale: str | None, source_text: str, **kwargs) -> str:
    language = locale_language(resolve_supported_locale(locale))
    template = _repair_mojibake(TRANSLATIONS.get(language, {}).get(source_text, source_text))
    repaired_kwargs = {
        key: _repair_mojibake(value) if isinstance(value, str) else value
        for key, value in kwargs.items()
    }
    return template.format(**repaired_kwargs)


def display_network_policy_name(policy: str | None, locale: str | None = None) -> str:
    normalized = str(policy or "").strip().lower()
    title = NETWORK_POLICY_TITLES.get(normalized, NETWORK_POLICY_TITLES["tor"])
    return translate(locale, title)


def display_setting_value(locale: str | None, key: str, value: object) -> str:
    if key == "locale":
        return display_language_name(str(value or DEFAULT_UI_LOCALE))
    if key == "keyboard":
        text = str(value or "").strip().lower()
        return text or "us"
    if key == "network_policy":
        return display_network_policy_name(str(value or "direct"), locale=locale)
    if key == "allow_brave_browser":
        return translate(locale, "Enabled" if bool(value) else "Disabled")
    if key == "sandbox_default":
        title = SANDBOX_TITLES.get(str(value or "").strip().lower(), SANDBOX_TITLES["focused"])
        return translate(locale, title)
    if key == "device_policy":
        title = DEVICE_POLICY_TITLES.get(str(value or "").strip().lower(), DEVICE_POLICY_TITLES["prompt"])
        return translate(locale, title)
    if key == "logging_policy":
        title = LOGGING_POLICY_TITLES.get(str(value or "").strip().lower(), LOGGING_POLICY_TITLES["minimal"])
        return translate(locale, title)
    if key == "ui_theme_profile":
        title = THEME_PROFILE_TITLES.get(str(value or "").strip().lower(), THEME_PROFILE_TITLES["nmos-classic"])
        return translate(locale, title)
    if key == "ui_accent":
        title = ACCENT_TITLES.get(str(value or "").strip().lower(), ACCENT_TITLES["amber"])
        return translate(locale, title)
    if key == "ui_density":
        title = DENSITY_TITLES.get(str(value or "").strip().lower(), DENSITY_TITLES["comfortable"])
        return translate(locale, title)
    if key == "ui_motion":
        title = MOTION_TITLES.get(str(value or "").strip().lower(), MOTION_TITLES["full"])
        return translate(locale, title)
    if key == "default_browser":
        title = DEFAULT_BROWSER_TITLES.get(str(value or "").strip().lower(), DEFAULT_BROWSER_TITLES["firefox-esr"])
        return translate(locale, title)
    if key == "vault":
        raw = value if isinstance(value, dict) else {}
        try:
            auto_lock_minutes = int(raw.get("auto_lock_minutes", 15))
        except (TypeError, ValueError):
            auto_lock_minutes = 15
        auto_lock_minutes = max(0, auto_lock_minutes)
        lock_text = (
            translate(locale, "Manual lock")
            if auto_lock_minutes == 0
            else translate(locale, "{minutes} min auto-lock", minutes=auto_lock_minutes)
        )
        login_text = translate(
            locale,
            "Unlock on login: enabled" if bool(raw.get("unlock_on_login", False)) else "Unlock on login: disabled",
        )
        return f"{lock_text}, {login_text}"
    return str(value)


def format_change_detail(
    locale: str | None,
    setting_name: str,
    key: str,
    before: object,
    after: object,
) -> str:
    return translate(
        locale,
        "{setting}: {before} -> {after}",
        setting=setting_name,
        before=display_setting_value(locale, key, before),
        after=display_setting_value(locale, key, after),
    )


def posture_meter_lines(locale: str | None, posture: object) -> list[str]:
    raw = posture if isinstance(posture, dict) else {}
    scores = raw.get("scores", {}) if isinstance(raw.get("scores", {}), dict) else {}
    protection = int(scores.get("protection", 5))
    convenience = int(scores.get("convenience", 5))
    lines = [
        translate(locale, "Protection level: {level}/10", level=protection),
        translate(locale, "Convenience level: {level}/10", level=convenience),
    ]
    if protection - convenience >= 2:
        lines.append(translate(locale, "Current balance favors stronger protection."))
    elif convenience - protection >= 2:
        lines.append(translate(locale, "Current balance favors convenience."))
    else:
        lines.append(translate(locale, "Current balance is relatively even."))
    return lines


def format_posture_shift(locale: str | None, shift: object) -> str:
    raw = shift if isinstance(shift, dict) else {}
    protection_delta = int(raw.get("protection_delta", 0))
    convenience_delta = int(raw.get("convenience_delta", 0))
    protection_text = f"{protection_delta:+d}"
    convenience_text = f"{convenience_delta:+d}"
    return translate(
        locale,
        "Shift vs current system: protection {protection}, convenience {convenience}",
        protection=protection_text,
        convenience=convenience_text,
    )


def translate_message(locale: str | None, text: str) -> str:
    translated = translate(locale, text)
    if translated != text:
        return translated

    network_policy_match = re.fullmatch(r"Direct network access is enabled by system settings\.", text)
    if network_policy_match is not None:
        return translate(locale, "Direct network access is enabled by system settings.")

    disabled_match = re.fullmatch(r"Network is disabled by current settings\.", text)
    if disabled_match is not None:
        return translate(locale, "Network is disabled by current settings.")

    return text


def explain_vault_behavior(locale: str | None, vault: object) -> list[str]:
    raw = vault if isinstance(vault, dict) else {}
    lines = []
    try:
        auto_lock_minutes = int(raw.get("auto_lock_minutes", 15))
    except (TypeError, ValueError):
        auto_lock_minutes = 15
    auto_lock_minutes = max(0, auto_lock_minutes)
    if auto_lock_minutes == 0:
        lines.append(translate(locale, "Vault locking is manual, which is convenient but easier to forget."))
    else:
        lines.append(
            translate(
                locale,
                "Vault auto-locks after {minutes} minutes to reduce accidental exposure.",
                minutes=auto_lock_minutes,
            )
        )
    if bool(raw.get("unlock_on_login", False)):
        lines.append(translate(locale, "Vault unlock on login favors convenience over separation."))
    else:
        lines.append(translate(locale, "Vault stays locked until you explicitly unlock it."))
    return lines


def explain_network_policy(locale: str | None, policy: str | None) -> str:
    normalized = str(policy or "tor").strip().lower()
    template = NETWORK_POLICY_EXPLANATIONS.get(normalized, NETWORK_POLICY_EXPLANATIONS["tor"])
    return translate(locale, template)


def explain_sandbox_default(locale: str | None, value: str | None) -> str:
    normalized = str(value or "focused").strip().lower()
    template = SANDBOX_EXPLANATIONS.get(normalized, SANDBOX_EXPLANATIONS["focused"])
    return translate(locale, template)


def explain_device_policy(locale: str | None, value: str | None) -> str:
    normalized = str(value or "prompt").strip().lower()
    template = DEVICE_EXPLANATIONS.get(normalized, DEVICE_EXPLANATIONS["prompt"])
    return translate(locale, template)


def explain_logging_policy(locale: str | None, value: str | None) -> str:
    normalized = str(value or "minimal").strip().lower()
    template = LOGGING_EXPLANATIONS.get(normalized, LOGGING_EXPLANATIONS["minimal"])
    return translate(locale, template)


def explain_brave_visibility(locale: str | None, allow_brave_browser: bool, network_policy: str | None) -> str:
    normalized_policy = str(network_policy or "direct").strip().lower()
    if allow_brave_browser and normalized_policy != "offline":
        return translate(locale, "Brave can appear when it is installed and the selected network policy allows it.")
    return translate(locale, "Brave stays hidden unless you explicitly allow it.")


def posture_explanation_lines(locale: str | None, posture: object) -> list[str]:
    raw = posture if isinstance(posture, dict) else {}
    effective = raw.get("effective", {}) if isinstance(raw.get("effective", {}), dict) else {}
    lines = []

    network_policy = str(effective.get("network_policy", "direct")).strip().lower()
    lines.append(explain_network_policy(locale, network_policy))

    sandbox_default = str(effective.get("sandbox_default", "focused")).strip().lower()
    lines.append(explain_sandbox_default(locale, sandbox_default))

    device_policy = str(effective.get("device_policy", "prompt")).strip().lower()
    lines.append(explain_device_policy(locale, device_policy))

    logging_policy = str(effective.get("logging_policy", "minimal")).strip().lower()
    lines.append(explain_logging_policy(locale, logging_policy))

    lines.extend(explain_vault_behavior(locale, effective.get("vault", {})))

    lines.append(explain_brave_visibility(locale, bool(effective.get("allow_brave_browser", False)), network_policy))

    return lines
