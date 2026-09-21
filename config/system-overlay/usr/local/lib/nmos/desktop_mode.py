#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from nmos_common.config_helpers import load_feature_flag
from nmos_common.platform_adapter import get_runtime_dir
from nmos_common.runtime_state import read_runtime_text, write_runtime_json, write_runtime_text
from nmos_common.system_settings import load_effective_system_settings

BRAVE_FEATURE_FILE = Path("/etc/nmos/features/brave")
BRAVE_DESKTOP_SOURCE = Path("/usr/share/applications/brave-browser.desktop")
BRAVE_DESKTOP_OVERRIDE = Path("/usr/local/share/applications/brave-browser.desktop")
SESSION_APPEARANCE_FILE = Path.home() / ".config/nmos/session-appearance.json"
THEME_DIR = Path("/usr/share/nmos/theme")
MANAGED_MARKER = "X-NMOS-Managed=true"
BRAVE_OVERRIDE_SIGNATURE_FILE = get_runtime_dir() / "brave-desktop.override.sha256"
WALLPAPER_BY_PROFILE = {
    "nmos-classic": THEME_DIR / "wallpaper.svg",
    "nmos-night": THEME_DIR / "wallpaper-night.svg",
    "nmos-light": THEME_DIR / "wallpaper-light.svg",
}
DEFAULT_BROWSER_DESKTOP_FILES = {
    "firefox-esr": "firefox-esr.desktop",
    "chromium": "chromium.desktop",
}


def log_policy_message(message: str) -> None:
    try:
        subprocess.run(
            ["logger", "-t", "nmos-desktop-mode", message],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        pass


def remove_override() -> None:
    if not BRAVE_DESKTOP_OVERRIDE.exists():
        BRAVE_OVERRIDE_SIGNATURE_FILE.unlink(missing_ok=True)
        return
    try:
        text = BRAVE_DESKTOP_OVERRIDE.read_text(encoding="utf-8")
    except OSError:
        return
    if MANAGED_MARKER not in text:
        return
    expected = ""
    try:
        expected = read_runtime_text(BRAVE_OVERRIDE_SIGNATURE_FILE).strip()
    except OSError:
        expected = ""
    observed = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if expected and observed == expected:
        BRAVE_DESKTOP_OVERRIDE.unlink(missing_ok=True)
        BRAVE_OVERRIDE_SIGNATURE_FILE.unlink(missing_ok=True)


def write_hidden_override() -> None:
    if not BRAVE_DESKTOP_SOURCE.exists():
        return
    BRAVE_DESKTOP_OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
    lines = BRAVE_DESKTOP_SOURCE.read_text(encoding="utf-8").splitlines()
    filtered = [
        line
        for line in lines
        if not line.startswith("NoDisplay=") and not line.startswith("Hidden=") and line != MANAGED_MARKER
    ]
    filtered.append("NoDisplay=true")
    filtered.append("Hidden=true")
    filtered.append(MANAGED_MARKER)
    content = "\n".join(filtered) + "\n"
    BRAVE_DESKTOP_OVERRIDE.write_text(content, encoding="utf-8")
    write_runtime_text(
        BRAVE_OVERRIDE_SIGNATURE_FILE,
        hashlib.sha256(content.encode("utf-8")).hexdigest() + "\n",
        mode=0o600,
    )


def apply_brave_visibility(settings: dict) -> None:
    if not BRAVE_DESKTOP_SOURCE.exists():
        remove_override()
        return
    brave_enabled = load_feature_flag(BRAVE_FEATURE_FILE)
    allow_brave = bool(settings.get("allow_brave_browser", False))
    offline = str(settings.get("network_policy", "direct")) == "offline"
    if brave_enabled and allow_brave and not offline:
        remove_override()
        return
    write_hidden_override()


def run_gsettings(*args: str) -> None:
    completed = subprocess.run(
        ["gsettings", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or f"exit={completed.returncode}").strip()
        raise RuntimeError(detail)


def wallpaper_for_profile(theme_profile: str) -> Path:
    candidate = WALLPAPER_BY_PROFILE.get(theme_profile, WALLPAPER_BY_PROFILE["nmos-classic"])
    return candidate if candidate.exists() else WALLPAPER_BY_PROFILE["nmos-classic"]


def write_session_appearance(settings: dict) -> None:
    wallpaper_path = wallpaper_for_profile(str(settings.get("ui_theme_profile", "nmos-classic")))
    SESSION_APPEARANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_runtime_json(
        SESSION_APPEARANCE_FILE,
        {
            "theme_profile": str(settings.get("ui_theme_profile", "nmos-classic")),
            "accent": str(settings.get("ui_accent", "amber")),
            "density": str(settings.get("ui_density", "comfortable")),
            "motion": str(settings.get("ui_motion", "full")),
            "wallpaper": str(wallpaper_path),
        },
        mode=0o600,
    )


def apply_desktop_preferences(settings: dict) -> None:
    theme_profile = str(settings.get("ui_theme_profile", "nmos-classic"))
    motion = str(settings.get("ui_motion", "full"))
    density = str(settings.get("ui_density", "comfortable"))
    wallpaper_path = wallpaper_for_profile(theme_profile)
    wallpaper_uri = wallpaper_path.resolve().as_uri()
    color_scheme = "default" if theme_profile == "nmos-light" else "prefer-dark"
    enable_animations = "false" if motion == "reduced" else "true"
    text_scale = "0.95" if density == "compact" else "1.0"

    for args in (
        ("set", "org.gnome.desktop.background", "picture-uri", wallpaper_uri),
        ("set", "org.gnome.desktop.background", "picture-uri-dark", wallpaper_uri),
        ("set", "org.gnome.desktop.background", "picture-options", "zoom"),
        ("set", "org.gnome.desktop.interface", "color-scheme", color_scheme),
        ("set", "org.gnome.desktop.interface", "enable-animations", enable_animations),
        ("set", "org.gnome.desktop.interface", "text-scaling-factor", text_scale),
    ):
        run_gsettings(*args)

    write_session_appearance(settings)
    log_policy_message(
        json.dumps(
            {
                "theme_profile": theme_profile,
                "motion": motion,
                "density": density,
                "wallpaper": str(wallpaper_path),
            },
            sort_keys=True,
        )
    )


def apply_default_browser(settings: dict) -> None:
    default_browser = str(settings.get("default_browser", "firefox-esr")).strip().lower()
    desktop_file = DEFAULT_BROWSER_DESKTOP_FILES.get(default_browser)
    if not desktop_file:
        return
    for command in (
        ["xdg-settings", "set", "default-web-browser", desktop_file],
        ["gio", "mime", "x-scheme-handler/http", desktop_file],
        ["gio", "mime", "x-scheme-handler/https", desktop_file],
    ):
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception as exc:
            log_policy_message(f"default browser command failed ({' '.join(command)}): {exc}")
            continue
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or f"exit={completed.returncode}").strip()
            log_policy_message(f"default browser command failed ({' '.join(command)}): {detail}")


def main() -> None:
    settings = load_effective_system_settings()
    apply_brave_visibility(settings)
    apply_default_browser(settings)
    try:
        apply_desktop_preferences(settings)
    except Exception as exc:
        log_policy_message(f"appearance sync skipped: {exc}")


if __name__ == "__main__":
    main()
