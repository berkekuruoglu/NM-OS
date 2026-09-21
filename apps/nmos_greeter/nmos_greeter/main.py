from __future__ import annotations

import logging
import os
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk

from nmos_common.i18n import LANGUAGE_OPTIONS, resolve_supported_locale, translate, translate_message
from nmos_common.platform_adapter import get_runtime_dir
from nmos_common.runtime_state import read_runtime_json
from nmos_common.settings_client import SettingsClient, SettingsClientError
from nmos_common.system_settings import (
    ACCENT_LABELS,
    DEFAULT_SYSTEM_SETTINGS,
    DEFAULT_UI_LOCALE,
    DENSITY_LABELS,
    MOTION_LABELS,
    PROFILE_METADATA,
    THEME_PROFILE_LABELS,
    derive_overrides_for_profile,
)
from nmos_common.ui_theme import load_css
from nmos_greeter import ui_composition
from nmos_greeter.browser_model import BROWSER_OPTIONS
from nmos_greeter.client import read_network_status
from nmos_greeter.state import (
    load_onboarding_page_index,
    load_state,
    next_onboarding_page_index,
    previous_onboarding_page_index,
    save_state,
    skip_to_summary_page_index,
)


class GreeterWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="NM-OS Setup")
        self.set_default_size(860, 560)
        self.logger = logging.getLogger("nmos.greeter")

        self.settings_client_factory = lambda: SettingsClient(allow_local_fallback=False)
        self.settings_backend_ready = True
        self.settings_backend_message = ""
        try:
            persisted_settings = self.settings_client_factory().get_settings()
        except SettingsClientError as error:
            persisted_settings = dict(DEFAULT_SYSTEM_SETTINGS)
            self.settings_backend_ready = False
            self.settings_backend_message = self.format_backend_guidance(error)
        self.state = {**persisted_settings, **load_state()}
        self.system_settings = dict(persisted_settings)
        self.save_state = save_state
        self.language_values = [locale for locale, _label in LANGUAGE_OPTIONS]
        self.profile_values = list(PROFILE_METADATA)
        self.browser_values = list(BROWSER_OPTIONS)
        self.theme_profile_values = list(THEME_PROFILE_LABELS)
        self.accent_values = list(ACCENT_LABELS)
        self.density_values = list(DENSITY_LABELS)
        self.motion_values = list(MOTION_LABELS)
        self.ui_locale = resolve_supported_locale(self.state.get("locale", os.environ.get("LANG", DEFAULT_UI_LOCALE)))
        self.page_order = self.resolve_page_order()
        self.page_index = load_onboarding_page_index(self.state, len(self.page_order))
        self.status_source = ""
        self.page_widgets: dict[str, Gtk.Widget] = {}
        self.runtime_dir = get_runtime_dir()
        self.network_status_file: Path = self.runtime_dir / "network-status.json"
        self.vault_status_file: Path = self.runtime_dir / "persistent-storage.json"
        self.last_runtime_status = ""

        ui_composition.build_ui(self)
        self.apply_translations()
        self.restore_state()
        self.stack.set_visible_child_name(f"page-{self.page_index}")
        self.apply_settings_ui_policy()
        self.update_navigation()
        if not self.settings_backend_ready:
            prefix = f"{self.settings_backend_message} " if self.settings_backend_message else ""
            self.set_status(f"{prefix}Review mode only until service is reachable.")
        GLib.timeout_add_seconds(10, self.poll_runtime)

    def describe_backend_issue(self, error: SettingsClientError) -> str:
        if error.reason == "access_denied":
            return "Settings backend denied access. Sign in with an authorized session and retry."
        if error.reason == "backend_unavailable":
            return "Settings backend is unavailable. Retry in a moment or check the settings service health."
        if error.reason == "transport_error":
            return "Settings backend connection failed. Check runtime service status, then retry."
        if error.reason == "dbus_import_error":
            return "D-Bus runtime is unavailable on this system."
        return error.user_message()

    def backend_recovery_hint(self, error: SettingsClientError) -> str:
        if error.reason == "access_denied":
            return "Action: sign in with an admin-authorized session and retry."
        if error.reason == "backend_unavailable":
            return "Action: wait a moment, then retry from the setup flow."
        if error.reason == "transport_error":
            return "Action: verify service health, then retry."
        if error.reason == "dbus_import_error":
            return "Action: continue in review mode until D-Bus is available."
        return "Action: retry once the backend is reachable."

    def format_backend_guidance(self, error: SettingsClientError) -> str:
        return f"{self.describe_backend_issue(error)} {self.backend_recovery_hint(error)}"

    def tr(self, source_text: str, **kwargs) -> str:
        return translate(self.ui_locale, source_text, **kwargs)

    def translate_message(self, text: str) -> str:
        return translate_message(self.ui_locale, text)

    def resolve_page_order(self) -> list[str]:
        return ui_composition.resolve_page_order(self)

    def current_page_key(self) -> str:
        return ui_composition.current_page_key(self)

    def current_language_code(self) -> str:
        return ui_composition.current_language_code(self)

    def current_language_name(self) -> str:
        return ui_composition.current_language_name(self)

    def current_profile(self) -> str:
        return ui_composition.current_profile(self)

    def current_profile_name(self) -> str:
        return ui_composition.current_profile_name(self)

    def current_profile_summary(self) -> str:
        return ui_composition.current_profile_summary(self)

    def action_label(self, action: str) -> str:
        return self.tr(action.capitalize()).lower()

    def apply_translations(self) -> None:
        ui_composition.apply_translations(self)

    def apply_settings_ui_policy(self) -> None:
        ui_composition.apply_settings_ui_policy(self)

    def restore_state(self) -> None:
        ui_composition.restore_state(self)

    def current_string(self, dropdown: Gtk.DropDown, values: list[str] | None = None) -> str:
        return ui_composition.current_string(dropdown, values)

    def set_status(self, text: str, *, source: str = "event", force: bool = True) -> None:
        ui_composition.set_status(self, text, source=source, force=force)

    def collect_state(self) -> dict:
        return ui_composition.collect_state(self)

    def persist_pending_state(self) -> bool:
        self.state = self.collect_state()
        self.state["onboarding_page_index"] = self.page_index
        try:
            self.save_state(self.state)
        except (OSError, ValueError, RuntimeError) as exc:
            self.logger.error("unable to save pending settings: %s", exc)
            self.set_status(self.tr("Unable to save pending settings: {error}", error=self.tr("internal error")))
            return False
        return True

    def apply_locale(self) -> bool:
        if not self.persist_pending_state():
            return False
        self.ui_locale = resolve_supported_locale(self.state.get("locale", DEFAULT_UI_LOCALE))
        self.apply_translations()
        self.set_status(self.tr("Language will be applied as {language}.", language=self.current_language_name()))
        return True

    def apply_keyboard(self) -> bool:
        if not self.persist_pending_state():
            return False
        self.set_status(
            self.tr(
                "Keyboard layout will be applied as {layout}.",
                layout=self.current_string(self.keyboard_combo, ui_composition.KEYBOARD_OPTIONS),
            )
        )
        return True

    def apply_browser(self) -> bool:
        if not self.persist_pending_state():
            return False
        return True

    def on_profile_changed(self, *_args) -> None:
        ui_composition.refresh_profile_explanation(self)
        self.update_navigation()

    def on_browser_changed(self, *_args) -> None:
        ui_composition.refresh_browser_explanation(self)
        self.update_navigation()

    def on_network_changed(self, *_args) -> None:
        ui_composition.refresh_network_explanation(self)
        self.update_navigation()

    def on_theme_preview_changed(self, *_args) -> None:
        self.apply_settings_ui_policy()
        self.update_navigation()

    def on_vault_passphrase_changed(self, *_args) -> None:
        ui_composition.refresh_passphrase_strength(self)
        self.update_navigation()

    def on_back(self, _button: Gtk.Button) -> None:
        self.page_index = previous_onboarding_page_index(self.page_index, len(self.page_order))
        self.stack.set_visible_child_name(f"page-{self.page_index}")
        self.persist_pending_state()
        self.update_navigation()

    def on_next(self, _button: Gtk.Button) -> None:
        current_key = self.current_page_key()
        if current_key == "language" and not self.apply_locale():
            return
        if current_key == "keyboard" and not self.apply_keyboard():
            return
        if current_key == "profile":
            self.profile_summary_label.set_text(self.tr(self.current_profile_summary()))
        if current_key == "browser" and not self.apply_browser():
            return
        self.page_index = next_onboarding_page_index(self.page_index, len(self.page_order))
        self.stack.set_visible_child_name(f"page-{self.page_index}")
        self.persist_pending_state()
        self.update_navigation()

    def on_skip(self, _button: Gtk.Button) -> None:
        self.page_index = skip_to_summary_page_index(len(self.page_order))
        self.stack.set_visible_child_name(f"page-{self.page_index}")
        self.persist_pending_state()
        self.update_navigation()
        self.set_status(self.tr("Setup pages skipped. Review summary and click Start using NM-OS."))

    def close_after_apply(self) -> bool:
        self.close()
        return GLib.SOURCE_REMOVE

    def on_finish(self, _button: Gtk.Button) -> None:
        if not self.can_finish():
            self.set_status(self.tr("Encrypted vault activity is still running."))
            return
        state = self.collect_state()
        profile = str(state.get("active_profile", "balanced"))
        overrides = derive_overrides_for_profile(profile, state)
        try:
            self.save_state(
                {
                    "locale": state.get("locale", DEFAULT_UI_LOCALE),
                    "keyboard": state.get("keyboard", "us"),
                    "network_policy": state.get("network_policy", "direct"),
                    "allow_brave_browser": bool(state.get("allow_brave_browser", False)),
                    "browser": state.get("browser", "firefox-esr"),
                    "default_browser": state.get("default_browser", "firefox-esr"),
                    "onboarding_page_index": self.page_index,
                }
            )
            client = self.settings_client_factory()
            client.apply_preset(profile)
            if overrides:
                client.set_overrides(overrides)
            self.system_settings = client.commit()
            self.state = dict(self.system_settings)
            # Setup completed successfully; start from page 0 on the next run.
            self.save_state(
                {
                    "locale": self.system_settings.get("locale", DEFAULT_UI_LOCALE),
                    "keyboard": self.system_settings.get("keyboard", "us"),
                    "network_policy": self.system_settings.get("network_policy", "direct"),
                    "allow_brave_browser": bool(self.system_settings.get("allow_brave_browser", False)),
                    "default_browser": self.system_settings.get("default_browser", "firefox-esr"),
                    "onboarding_page_index": 0,
                }
            )
        except (OSError, ValueError, RuntimeError, SettingsClientError) as exc:
            self.logger.error("failed to save system settings: %s", exc)
            if isinstance(exc, SettingsClientError):
                self.set_status(self.format_backend_guidance(exc))
            else:
                self.set_status(self.tr("Failed to save system settings: {error}", error=self.tr("internal error")))
            return
        self.set_status(self.tr("Settings saved. Some privacy changes apply on the next boot."))
        GLib.timeout_add_seconds(2, self.close_after_apply)

    def update_navigation(self) -> None:
        ui_composition.update_navigation(self)

    def can_finish(self) -> bool:
        return ui_composition.can_finish(self)

    def poll_runtime(self) -> bool:
        network_status = read_network_status()
        vault_status = read_runtime_json(self.vault_status_file, default={})
        runtime_messages: list[str] = []

        phase = str(network_status.get("phase", "")).strip().lower()
        progress = int(network_status.get("progress", 0))
        if phase == "disabled":
            runtime_messages.append("Network: disabled by current policy.")
        elif phase == "open":
            runtime_messages.append("Network: direct access is active.")
        elif bool(network_status.get("ready", False)):
            runtime_messages.append("Network: Tor bootstrap is ready.")
        else:
            runtime_messages.append(f"Network: waiting for Tor ({progress}%).")

        last_error = str(network_status.get("last_error", "")).strip()
        if last_error:
            runtime_messages.append(f"Network error: {self.translate_message(last_error)}")

        if vault_status:
            if bool(vault_status.get("busy", False)):
                runtime_messages.append("Vault: action in progress.")
            elif bool(vault_status.get("unlocked", False)):
                runtime_messages.append("Vault: unlocked.")
            elif bool(vault_status.get("created", False)):
                runtime_messages.append("Vault: locked and available.")
            elif bool(vault_status.get("can_create", False)):
                runtime_messages.append("Vault: ready to create.")
            else:
                runtime_messages.append("Vault: unavailable.")
            vault_error = str(vault_status.get("last_error", "")).strip()
            if vault_error:
                runtime_messages.append(f"Vault error: {self.translate_message(vault_error)}")
        else:
            runtime_messages.append("Vault: status unavailable.")

        try:
            self.settings_client_factory().get_settings()
            self.settings_backend_ready = True
            runtime_messages.append("Settings backend: reachable.")
        except SettingsClientError as error:
            self.settings_backend_ready = False
            runtime_messages.append(self.format_backend_guidance(error))

        combined = " | ".join(runtime_messages)
        if combined != self.last_runtime_status:
            self.last_runtime_status = combined
            self.set_status(combined, source="runtime", force=False)
        return True


class GreeterApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="org.nmos.Greeter")

    def do_activate(self) -> None:
        load_css()
        window = self.props.active_window
        if window is None:
            window = GreeterWindow(self)
        window.present()


def main() -> None:
    app = GreeterApplication()
    app.run([])


if __name__ == "__main__":
    main()
