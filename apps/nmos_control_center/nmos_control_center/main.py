from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk
from nmos_common.i18n import (
    LANGUAGE_OPTIONS,
    explain_brave_visibility,
    explain_device_policy,
    explain_logging_policy,
    explain_network_policy,
    explain_sandbox_default,
    explain_vault_behavior,
    format_change_detail,
    format_posture_shift,
    posture_explanation_lines,
    posture_meter_lines,
    resolve_supported_locale,
    translate,
)
from nmos_common.passphrase_policy import passphrase_feedback_text
from nmos_common.platform_adapter import get_runtime_dir
from nmos_common.runtime_state import (
    read_runtime_json,
    read_runtime_text,
    write_runtime_json,
    write_runtime_text,
)
from nmos_common.settings_client import SettingsClient, SettingsClientError
from nmos_common.system_settings import (
    ACCENT_LABELS,
    DEFAULT_SYSTEM_SETTINGS,
    DENSITY_LABELS,
    MOTION_LABELS,
    PROFILE_METADATA,
    THEME_PROFILE_LABELS,
    compute_posture_score_shift,
    compute_posture_scores,
    derive_overrides_for_profile,
    describe_effective_change_details,
    describe_posture_preview,
    normalize_system_settings,
    setting_display_name,
)
from nmos_common.ui_theme import apply_window_theme, load_css
from nmos_common.update_client import UpdateClient, UpdateClientError

KEYBOARD_OPTIONS = ("us", "tr", "de", "fr")


def as_object_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    return {}
NETWORK_OPTIONS = (
    ("tor", "Tor-first"),
    ("direct", "Direct network"),
    ("offline", "Offline"),
)
SANDBOX_OPTIONS = (
    ("standard", "Standard"),
    ("focused", "Focused"),
    ("strict", "Strict"),
)
DEVICE_POLICY_OPTIONS = (
    ("shared", "Shared devices"),
    ("prompt", "Prompt first"),
    ("locked", "Locked down"),
)
LOGGING_OPTIONS = (
    ("balanced", "Balanced"),
    ("minimal", "Minimal"),
    ("sealed", "Sealed"),
)
RAM_WIPE_OPTIONS = (
    ("off", "Off"),
    ("balanced", "Balanced"),
    ("strict", "Strict"),
)
THEME_PROFILE_OPTIONS = tuple(THEME_PROFILE_LABELS.items())
ACCENT_OPTIONS = tuple(ACCENT_LABELS.items())
DENSITY_OPTIONS = tuple(DENSITY_LABELS.items())
MOTION_OPTIONS = tuple(MOTION_LABELS.items())
DEFAULT_BROWSER_OPTIONS = (
    ("firefox-esr", "Firefox"),
    ("chromium", "Chromium"),
    ("none", "No default browser"),
)
APP_FILESYSTEM_OPTIONS = (
    ("inherit", "Inherit default"),
    ("home", "Home access"),
    ("documents", "Documents only"),
    ("host", "Host filesystem"),
    ("none", "No filesystem access"),
)
APP_NETWORK_OPTIONS = (
    ("inherit", "Inherit default"),
    ("shared", "Shared network"),
    ("isolated", "Isolated network"),
)
APP_DEVICE_OPTIONS = (
    ("inherit", "Inherit default"),
    ("all", "All devices"),
    ("none", "No device access"),
)
APP_SANDBOX_PRESET_OPTIONS = (
    ("secure", "Secure"),
    ("balanced", "Balanced"),
    ("compatible", "Compatible"),
)
UPDATE_CHANNEL_OPTIONS = (
    ("stable", "Stable"),
    ("beta", "Beta"),
    ("nightly", "Nightly"),
)
VAULT_AUTO_LOCK_OPTIONS = (
    ("0", "Manual lock"),
    ("5", "5 minutes"),
    ("15", "15 minutes"),
    ("30", "30 minutes"),
    ("60", "1 hour"),
)
SETTING_RISK_HINTS = {
    "network_policy": "Network reachability and some online apps can be affected.",
    "allow_brave_browser": "Browser availability and app-launch expectations can change.",
    "sandbox_default": "File access and inter-app workflows may become stricter.",
    "default_browser": "Link handling behavior across desktop apps changes immediately.",
    "device_policy": "External peripherals and removable media behavior may tighten.",
    "logging_policy": "Diagnostic visibility may decrease as retention gets stricter.",
    "ram_wipe_mode": "Stricter memory wiping improves hygiene but can reduce performance.",
    "vault_auto_lock_minutes": "Shorter lock timers reduce convenience during active work.",
    "vault_unlock_on_login": "Disabling auto-unlock increases manual unlock steps.",
    "app_overrides": "Per-app filesystem, network, or device access can affect app behavior.",
    "active_profile": "Multiple security defaults can change together with profile shifts.",
}


from nmos_control_center.panels import applications, language, network, personalization, security, system


class ControlCenterWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="NM-OS Control Center")
        self.set_default_size(1080, 720)
        self.client = SettingsClient(allow_local_fallback=False)
        self.update_client = UpdateClient(allow_local_fallback=False)
        self.repo_root = Path(__file__).resolve().parents[3]
        self._signal_bus = None
        self._signal_interface = None
        self._signal_match = None
        self._reload_source_id: int | None = None
        self.backend_ready = True
        self.startup_error_message = ""
        try:
            self.settings = self.client.get_settings()
        except SettingsClientError as error:
            self.settings = dict(DEFAULT_SYSTEM_SETTINGS)
            self.backend_ready = False
            self.startup_error_message = self.format_backend_guidance(error)
        self.profile_values = list(PROFILE_METADATA)
        self.language_values = [locale for locale, _label in LANGUAGE_OPTIONS]
        runtime_dir = get_runtime_dir()
        self.logging_status_file = runtime_dir / "logging-policy-status.json"
        self.app_isolation_status_file = runtime_dir / "app-isolation-status.json"
        self.device_policy_status_file = runtime_dir / "device-policy-status.json"
        self.ram_wipe_status_file = runtime_dir / "ram-wipe-status.json"
        self.update_status_file = runtime_dir / "update-center-status.json"
        self.update_history_file = runtime_dir / "update-center-history.json"
        self.update_catalog_file = self.repo_root / "config" / "update-catalog.json"
        self.dist_update_catalog_file = self.repo_root / "dist" / "update-catalog.json"
        self.shared_metadata_dir = Path("/usr/share/nmos")
        self.shared_update_catalog_file = self.shared_metadata_dir / "update-catalog.json"
        self.build_info_file = self.shared_metadata_dir / "build-info"
        self.release_manifest_file = self.shared_metadata_dir / "release-manifest.json"
        self.dist_release_manifest_file = self.repo_root / "dist" / "release-manifest.json"
        self.recovery_bundle_file = runtime_dir / "recovery-diagnostics.json"
        self.settings_snapshot_file = runtime_dir / "settings-rollback-snapshot.json"

        self.KEYBOARD_OPTIONS = KEYBOARD_OPTIONS
        self.NETWORK_OPTIONS = NETWORK_OPTIONS
        self.SANDBOX_OPTIONS = SANDBOX_OPTIONS
        self.DEVICE_POLICY_OPTIONS = DEVICE_POLICY_OPTIONS
        self.LOGGING_OPTIONS = LOGGING_OPTIONS
        self.RAM_WIPE_OPTIONS = RAM_WIPE_OPTIONS
        self.THEME_PROFILE_OPTIONS = THEME_PROFILE_OPTIONS
        self.ACCENT_OPTIONS = ACCENT_OPTIONS
        self.DENSITY_OPTIONS = DENSITY_OPTIONS
        self.MOTION_OPTIONS = MOTION_OPTIONS
        self.DEFAULT_BROWSER_OPTIONS = DEFAULT_BROWSER_OPTIONS
        self.APP_FILESYSTEM_OPTIONS = APP_FILESYSTEM_OPTIONS
        self.APP_NETWORK_OPTIONS = APP_NETWORK_OPTIONS
        self.APP_DEVICE_OPTIONS = APP_DEVICE_OPTIONS
        self.APP_SANDBOX_PRESET_OPTIONS = APP_SANDBOX_PRESET_OPTIONS
        self.UPDATE_CHANNEL_OPTIONS = UPDATE_CHANNEL_OPTIONS
        self.VAULT_AUTO_LOCK_OPTIONS = VAULT_AUTO_LOCK_OPTIONS
        self.app_override_dropdowns: dict[str, dict[str, Gtk.DropDown]] = {}

        self.ui_locale = resolve_supported_locale(self.settings.get("locale", "en_US.UTF-8"))
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.root.set_margin_top(24)
        self.root.set_margin_bottom(24)
        self.root.set_margin_start(24)
        self.root.set_margin_end(24)
        self.build_ui()
        self.connect("close-request", self._on_close_request)
        self._connect_settings_signal()
        self.restore_settings()
        self.refresh_summary()
        self._set_backend_action_sensitivity(self.backend_ready)
        if not self.backend_ready:
            self._set_review_mode_status(self.startup_error_message)
        self.set_content(self.root)

    def _connect_settings_signal(self) -> None:
        try:
            self._signal_bus, self._signal_interface, self._signal_match = self.client.connect_settings_changed(
                self._on_settings_changed_signal
            )
        except Exception:
            self._signal_bus = None
            self._signal_interface = None
            self._signal_match = None

    def _disconnect_settings_signal(self) -> None:
        if self._signal_match is not None:
            try:
                self._signal_match.remove()
            except Exception:
                pass
        self._signal_match = None
        self._signal_interface = None
        self._signal_bus = None

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self._disconnect_settings_signal()
        return False

    def _on_settings_changed_signal(self, _payload: dict) -> None:
        # D-Bus callbacks may arrive off the GTK main loop, so defer the refresh safely.
        if self._reload_source_id is not None:
            return
        self._reload_source_id = GLib.idle_add(self._reload_from_backend)

    def _reload_from_backend(self) -> bool:
        self._reload_source_id = None
        try:
            self.settings = self.client.get_settings()
        except SettingsClientError as error:
            self.backend_ready = False
            self._set_backend_action_sensitivity(False)
            self._set_review_mode_status(self.format_backend_guidance(error))
            return GLib.SOURCE_REMOVE
        self.backend_ready = True
        self._set_backend_action_sensitivity(True)
        self.restore_settings()
        self.refresh_summary()
        self.status_label.set_text("Settings updated by another session.")
        return GLib.SOURCE_REMOVE

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
            return "Action: sign in with an admin-authorized session, then click Refresh."
        if error.reason == "backend_unavailable":
            return "Action: click Refresh. If it persists, run: systemctl status nmos-settings.service"
        if error.reason == "transport_error":
            return "Action: verify D-Bus and service health, then retry. Diagnostics can help."
        if error.reason == "dbus_import_error":
            return "Action: use review mode or safe mode until D-Bus is available."
        return "Action: retry, then open diagnostics if the problem continues."

    def format_backend_guidance(self, error: SettingsClientError) -> str:
        return f"{self.describe_backend_issue(error)} {self.backend_recovery_hint(error)}"

    def _set_review_mode_status(self, prefix: str = "") -> None:
        guidance = "Review mode only until service is reachable. Use Diagnostics for details."
        if prefix:
            self.status_label.set_text(f"{prefix} {guidance}")
            return
        self.status_label.set_text(guidance)

    def _set_backend_action_sensitivity(self, enabled: bool) -> None:
        self.apply_button.set_sensitive(enabled)
        self.reset_button.set_sensitive(enabled)
        self.comfort_mode_button.set_sensitive(enabled)
        self.emergency_lockdown_button.set_sensitive(enabled)

    def _guard_backend_mutation(self) -> bool:
        if self.backend_ready:
            return True
        self._set_backend_action_sensitivity(False)
        self._set_review_mode_status("Settings backend is unavailable.")
        return False

    def _selected_value(self, dropdown: Gtk.DropDown, values: list[str]) -> str:
        selected = dropdown.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or selected >= len(values):
            dropdown.set_selected(0)
            return values[0]
        return values[selected]

    def _selected_option_value(self, dropdown: Gtk.DropDown, options: tuple[tuple[str, str], ...]) -> str:
        return self._selected_value(dropdown, [value for value, _label in options])

    def _set_dropdown_value(self, dropdown: Gtk.DropDown, values: list[str], value: str) -> None:
        try:
            dropdown.set_selected(values.index(value))
        except ValueError:
            dropdown.set_selected(0)

    def tr(self, source_text: str, **kwargs) -> str:
        return translate(self.ui_locale, source_text, **kwargs)

    def discover_flatpak_apps(self) -> list[str]:
        try:
            completed = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if completed.returncode != 0:
            return []
        apps = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        return sorted(set(apps))

    def _selected_filesystem_profile(self, dropdown: Gtk.DropDown) -> str:
        values = [value for value, _label in self.APP_FILESYSTEM_OPTIONS]
        selected = dropdown.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or selected >= len(values):
            return "inherit"
        return values[selected]

    def _selected_app_profile(self, dropdown: Gtk.DropDown, values: list[str]) -> str:
        selected = dropdown.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or selected >= len(values):
            return "inherit"
        return values[selected]

    def collect_app_overrides(self) -> dict[str, dict[str, str]]:
        overrides: dict[str, dict[str, str]] = {}
        filesystem_values = [value for value, _label in self.APP_FILESYSTEM_OPTIONS]
        network_values = [value for value, _label in self.APP_NETWORK_OPTIONS]
        device_values = [value for value, _label in self.APP_DEVICE_OPTIONS]
        for app_id, controls in self.app_override_dropdowns.items():
            filesystem = self._selected_app_profile(controls["filesystem"], filesystem_values)
            network = self._selected_app_profile(controls["network"], network_values)
            devices = self._selected_app_profile(controls["devices"], device_values)
            if filesystem == "inherit" and network == "inherit" and devices == "inherit":
                continue
            app_override: dict[str, str] = {}
            if filesystem != "inherit":
                app_override["filesystem"] = filesystem
            if network != "inherit":
                app_override["network"] = network
            if devices != "inherit":
                app_override["devices"] = devices
            overrides[app_id] = app_override
        return overrides

    def set_all_app_overrides(self, *, filesystem: str, network: str, devices: str) -> None:
        filesystem_values = [value for value, _label in self.APP_FILESYSTEM_OPTIONS]
        network_values = [value for value, _label in self.APP_NETWORK_OPTIONS]
        device_values = [value for value, _label in self.APP_DEVICE_OPTIONS]
        try:
            filesystem_index = filesystem_values.index(filesystem)
        except ValueError:
            filesystem_index = 0
        try:
            network_index = network_values.index(network)
        except ValueError:
            network_index = 0
        try:
            device_index = device_values.index(devices)
        except ValueError:
            device_index = 0
        for controls in self.app_override_dropdowns.values():
            controls["filesystem"].set_selected(filesystem_index)
            controls["network"].set_selected(network_index)
            controls["devices"].set_selected(device_index)

    def apply_sandbox_preset(self, preset: str) -> None:
        if preset == "secure":
            self._set_dropdown_value(
                self.sandbox_combo,
                [value for value, _label in self.SANDBOX_OPTIONS],
                "strict",
            )
            self.set_all_app_overrides(filesystem="none", network="isolated", devices="none")
            return
        if preset == "compatible":
            self._set_dropdown_value(
                self.sandbox_combo,
                [value for value, _label in self.SANDBOX_OPTIONS],
                "standard",
            )
            self.set_all_app_overrides(filesystem="host", network="shared", devices="all")
            return
        self._set_dropdown_value(
            self.sandbox_combo,
            [value for value, _label in self.SANDBOX_OPTIONS],
            "focused",
        )
        self.set_all_app_overrides(filesystem="inherit", network="inherit", devices="inherit")

    def rebuild_app_overrides_editor(self, settings: dict) -> None:
        model = settings.get("app_overrides", {}) if isinstance(settings.get("app_overrides", {}), dict) else {}
        known_apps = self.discover_flatpak_apps()
        all_apps = sorted(set(known_apps) | {str(app_id) for app_id in model.keys()})
        self.app_override_dropdowns = {}
        while True:
            child = self.app_overrides_list.get_first_child()
            if child is None:
                break
            self.app_overrides_list.remove(child)
        if not all_apps:
            self.app_overrides_empty.set_text("No Flatpak apps detected. Install apps, then click Refresh.")
            self.app_overrides_empty.set_visible(True)
            return
        self.app_overrides_empty.set_visible(False)
        filesystem_labels = [label for _value, label in self.APP_FILESYSTEM_OPTIONS]
        filesystem_values = [value for value, _label in self.APP_FILESYSTEM_OPTIONS]
        network_labels = [label for _value, label in self.APP_NETWORK_OPTIONS]
        network_values = [value for value, _label in self.APP_NETWORK_OPTIONS]
        device_labels = [label for _value, label in self.APP_DEVICE_OPTIONS]
        device_values = [value for value, _label in self.APP_DEVICE_OPTIONS]
        for app_id in all_apps:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_label = Gtk.Label(label=app_id, xalign=0)
            row_label.set_hexpand(True)
            filesystem_dropdown = Gtk.DropDown(model=Gtk.StringList.new(filesystem_labels))
            network_dropdown = Gtk.DropDown(model=Gtk.StringList.new(network_labels))
            device_dropdown = Gtk.DropDown(model=Gtk.StringList.new(device_labels))
            selected_filesystem = str(model.get(app_id, {}).get("filesystem", "inherit")).strip().lower()
            selected_network = str(model.get(app_id, {}).get("network", "inherit")).strip().lower()
            selected_devices = str(model.get(app_id, {}).get("devices", "inherit")).strip().lower()
            try:
                filesystem_dropdown.set_selected(filesystem_values.index(selected_filesystem))
            except ValueError:
                filesystem_dropdown.set_selected(0)
            try:
                network_dropdown.set_selected(network_values.index(selected_network))
            except ValueError:
                network_dropdown.set_selected(0)
            try:
                device_dropdown.set_selected(device_values.index(selected_devices))
            except ValueError:
                device_dropdown.set_selected(0)
            filesystem_dropdown.connect("notify::selected", self.on_draft_settings_changed)
            network_dropdown.connect("notify::selected", self.on_draft_settings_changed)
            device_dropdown.connect("notify::selected", self.on_draft_settings_changed)
            row.append(row_label)
            row.append(filesystem_dropdown)
            row.append(network_dropdown)
            row.append(device_dropdown)
            self.app_overrides_list.append(row)
            self.app_override_dropdowns[app_id] = {
                "filesystem": filesystem_dropdown,
                "network": network_dropdown,
                "devices": device_dropdown,
            }

    def on_vault_passphrase_changed(self, *_args) -> None:
        text = self.vault_passphrase_entry.get_text()
        self.vault_passphrase_strength.set_text(passphrase_feedback_text(text))

    def on_refresh_app_list(self, _button: Gtk.Button) -> None:
        draft = self.collect_values()
        self.rebuild_app_overrides_editor({"app_overrides": draft.get("app_overrides", {})})
        self.status_label.set_text("Flatpak app list refreshed.")

    def format_policy_runtime_status(self) -> str:
        app_status = read_runtime_json(self.app_isolation_status_file, default={})
        logging_status = read_runtime_json(self.logging_status_file, default={})
        device_status = read_runtime_json(self.device_policy_status_file, default={})
        ram_wipe_status = read_runtime_json(self.ram_wipe_status_file, default={})

        lines = []
        if app_status:
            apply_ok = bool(app_status.get("apply_ok", False))
            lines.append(
                "App isolation: "
                f"profile={app_status.get('sandbox_default', 'unknown')} "
                f"applied={apply_ok}"
            )
            if not apply_ok:
                lines.append("Action: review nmos-app-isolation-policy.service diagnostics.")
        else:
            lines.append("App isolation: status unavailable")

        if device_status:
            write_ok = bool(device_status.get("write_ok", False))
            reload_ok = bool(device_status.get("reload_ok", False))
            lines.append(
                "Device policy: "
                f"profile={device_status.get('device_policy', 'unknown')} "
                f"write={write_ok} "
                f"reload={reload_ok}"
            )
            if not write_ok or not reload_ok:
                lines.append("Action: review nmos-device-policy.service diagnostics.")
        else:
            lines.append("Device policy: status unavailable")

        if logging_status:
            reload_ok = bool(logging_status.get("reload_ok", False))
            vacuum_ok = bool(logging_status.get("vacuum_ok", False))
            lines.append(
                "Logging policy: "
                f"profile={logging_status.get('logging_policy', 'unknown')} "
                f"reload={reload_ok} "
                f"vacuum={vacuum_ok}"
            )
            if not reload_ok or not vacuum_ok:
                lines.append("Action: review nmos-logging-policy.service diagnostics.")
        else:
            lines.append("Logging policy: status unavailable")
        if ram_wipe_status:
            update_ok = bool(ram_wipe_status.get("update_grub_ok", False))
            reboot_required = bool(ram_wipe_status.get("reboot_required", False))
            lines.append(
                "RAM wipe policy: "
                f"mode={ram_wipe_status.get('ram_wipe_mode', 'unknown')} "
                f"update_grub={update_ok} "
                f"reboot_required={reboot_required}"
            )
            if not update_ok:
                lines.append("Action: review nmos-ram-wipe-policy.service diagnostics.")
        else:
            lines.append("RAM wipe policy: status unavailable")
        return "\n".join(lines)

    def format_ram_wipe_status(self) -> str:
        status = read_runtime_json(self.ram_wipe_status_file, default={})
        if not status:
            return "RAM wipe runtime status is unavailable."
        mode = str(status.get("ram_wipe_mode", "unknown"))
        update_grub_ok = bool(status.get("update_grub_ok", False))
        update_grub_detail = str(status.get("update_grub_detail", ""))
        reboot_required = bool(status.get("reboot_required", False))
        lines = [
            f"Mode: {mode}",
            f"update-grub: {update_grub_ok}",
            f"Reboot required: {reboot_required}",
        ]
        if update_grub_detail:
            lines.append(f"Detail: {update_grub_detail}")
        return "\n".join(lines)

    def _change_timing_for_key(self, key: str, details: dict[str, list[dict[str, object]]]) -> str:
        immediate_keys = {str(item.get("key", "")) for item in details.get("immediate", [])}
        reboot_keys = {str(item.get("key", "")) for item in details.get("reboot", [])}
        if key in immediate_keys and key in reboot_keys:
            return "Partly now, partly after reboot."
        if key in reboot_keys:
            return "Applies after reboot."
        return "Applies now."

    def _change_phase_flags_for_key(self, key: str, details: dict[str, list[dict[str, object]]]) -> tuple[bool, bool]:
        immediate_keys = {str(item.get("key", "")) for item in details.get("immediate", [])}
        reboot_keys = {str(item.get("key", "")) for item in details.get("reboot", [])}
        return key in immediate_keys, key in reboot_keys

    def build_setting_change_explanation(
        self,
        *,
        key: str,
        details: dict[str, list[dict[str, object]]],
    ) -> str:
        changes_now, changes_after_reboot = self._change_phase_flags_for_key(key, details)
        timing = self._change_timing_for_key(key, details)
        risk = SETTING_RISK_HINTS.get(key, "Compatibility impact depends on your current workflow.")
        return (
            f"Explain this setting: {self.tr(setting_display_name(key))}. "
            f"Changes now: {'yes' if changes_now else 'no'}. "
            f"Changes after reboot: {'yes' if changes_after_reboot else 'no'}. "
            f"When: {timing} "
            f"Compatibility risk: {risk}"
        )

    def format_privacy_dashboard(
        self,
        *,
        draft_values: dict,
        change_details: dict[str, list[dict[str, object]]],
    ) -> str:
        immediate = [self.tr(setting_display_name(str(item["key"]))) for item in change_details["immediate"]]
        reboot = [self.tr(setting_display_name(str(item["key"]))) for item in change_details["reboot"]]
        services = self.format_policy_runtime_status().splitlines()
        policy_line = (
            "Active policies: "
            f"network={draft_values.get('network_policy', 'unknown')}, "
            f"sandbox={draft_values.get('sandbox_default', 'unknown')}, "
            f"devices={draft_values.get('device_policy', 'unknown')}, "
            f"logging={draft_values.get('logging_policy', 'unknown')}"
        )
        changes_line = (
            "Recent draft changes: "
            f"now={', '.join(immediate) if immediate else 'none'}; "
            f"reboot={', '.join(reboot) if reboot else 'none'}"
        )
        return "\n".join([policy_line, *services, changes_line])

    def detect_release_channel(self, version: str) -> str:
        version_text = str(version).lower()
        if "alpha" in version_text or "nightly" in version_text:
            return "nightly"
        if "beta" in version_text or "rc" in version_text:
            return "beta"
        return "stable"

    def _selected_update_channel(self) -> str:
        return self._selected_option_value(self.update_channel_combo, self.UPDATE_CHANNEL_OPTIONS)

    def _current_timestamp(self) -> str:
        now = GLib.DateTime.new_now_local()
        formatted = now.format("%Y-%m-%d %H:%M:%S %Z")
        return formatted or "unknown"

    def load_update_status(self) -> dict[str, object]:
        try:
            data = self.update_client.get_status()
        except UpdateClientError:
            data = read_runtime_json(self.update_status_file, default={})
        if isinstance(data, dict):
            return data
        return {}

    def write_update_status(self, payload: dict[str, object]) -> None:
        write_runtime_json(self.update_status_file, payload)

    def load_update_history(self) -> list[dict[str, object]]:
        try:
            payload = self.update_client.get_history()
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
        except UpdateClientError:
            pass
        if not self.update_history_file.exists():
            return []
        try:
            fallback_payload = json.loads(read_runtime_text(self.update_history_file))
        except (OSError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(fallback_payload, list):
            return []
        history: list[dict[str, object]] = []
        for item in fallback_payload:
            if isinstance(item, dict):
                history.append(item)
        return history

    def write_update_history(self, history: list[dict[str, object]]) -> None:
        write_runtime_text(
            self.update_history_file,
            json.dumps(history, indent=2, sort_keys=True),
        )

    def load_settings_snapshot(self) -> dict[str, object]:
        data = read_runtime_json(self.settings_snapshot_file, default={})
        if isinstance(data, dict):
            return data
        return {}

    def write_settings_snapshot(self, payload: dict[str, object]) -> None:
        write_runtime_json(self.settings_snapshot_file, payload)

    def snapshot_current_settings(self, *, reason: str) -> bool:
        current_settings = normalize_system_settings(self.settings)
        snapshot: dict[str, object] = {
            "taken_at": self._current_timestamp(),
            "reason": reason,
            "settings": current_settings,
        }
        try:
            self.write_settings_snapshot(snapshot)
        except OSError:
            return False
        return True

    def load_recovery_bundle(self) -> dict[str, object]:
        data = read_runtime_json(self.recovery_bundle_file, default={})
        if isinstance(data, dict):
            return data
        return {}

    def build_diagnostics_bundle(self) -> dict[str, object]:
        try:
            effective_settings = self.client.get_effective_settings()
        except SettingsClientError:
            effective_settings = normalize_system_settings(self.settings)
        bundle_id = GLib.DateTime.new_now_utc().format("%Y%m%dT%H%M%SZ") or "unknown"
        update_history = self.load_update_history()
        return {
            "bundle_id": bundle_id,
            "created_at": self._current_timestamp(),
            "backend_ready": self.backend_ready,
            "startup_error_message": self.startup_error_message,
            "settings": normalize_system_settings(self.settings),
            "effective_settings": effective_settings,
            "policy_runtime_status": {
                "app_isolation": read_runtime_json(self.app_isolation_status_file, default={}),
                "device_policy": read_runtime_json(self.device_policy_status_file, default={}),
                "logging_policy": read_runtime_json(self.logging_status_file, default={}),
            },
            "update_center": {
                "status": self.load_update_status(),
                "history_count": len(update_history),
                "history_tail": update_history[-5:],
            },
            "rollback_snapshot": self.load_settings_snapshot(),
            "trust_chain": self.format_trust_chain_status().splitlines(),
            "diagnostic_commands": [
                "systemctl status nmos-settings.service nmos-app-isolation-policy.service nmos-device-policy.service nmos-logging-policy.service",
                "journalctl -u nmos-settings.service -u nmos-app-isolation-policy.service -u nmos-device-policy.service -u nmos-logging-policy.service -n 50",
            ],
        }

    def format_recovery_status(self) -> str:
        snapshot = self.load_settings_snapshot()
        snapshot_settings = as_object_dict(snapshot.get("settings", {}))
        snapshot_profile = str(snapshot_settings.get("active_profile", "unknown"))
        snapshot_time = str(snapshot.get("taken_at", "not captured"))
        snapshot_reason = str(snapshot.get("reason", "No rollback snapshot captured yet."))
        bundle = self.load_recovery_bundle()
        bundle_time = str(bundle.get("created_at", "not created"))
        bundle_id = str(bundle.get("bundle_id", "not created"))
        self.snapshot_rollback_button.set_sensitive(bool(snapshot_settings) and self.backend_ready)
        return "\n".join(
            [
                f"Rollback snapshot: {snapshot_time}",
                f"Snapshot profile: {snapshot_profile}",
                f"Snapshot reason: {snapshot_reason}",
                f"Diagnostics bundle: {bundle_id}",
                f"Bundle created: {bundle_time}",
                "Recovery guidance: create a diagnostics bundle before resetting or rolling back settings.",
            ]
        )

    def read_build_info(self) -> dict[str, str]:
        if not self.build_info_file.exists():
            return {}
        try:
            raw = read_runtime_text(self.build_info_file)
        except OSError:
            return {}
        info: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            info[str(key).strip()] = str(value).strip()
        return info

    def load_release_manifest(self) -> dict[str, object]:
        for path in (self.release_manifest_file, self.dist_release_manifest_file):
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                return payload

        dist_dir = self.dist_release_manifest_file.parent
        if dist_dir.exists():
            for path in sorted(dist_dir.glob("*.build-manifest")):
                try:
                    raw = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                legacy: dict[str, str] = {}
                for line in raw.splitlines():
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    legacy[str(key).strip()] = str(value).strip()
                if legacy:
                    version = str(legacy.get("version", "")).strip()
                    channel = str(legacy.get("channel", "")).strip() or self.detect_release_channel(version)
                    return {
                        "schema_version": 1,
                        "product": "NM-OS",
                        "version": version,
                        "channel": channel,
                        "build_id": str(legacy.get("build_id", "")).strip(),
                        "released_at": str(legacy.get("built_at", "")).strip(),
                        "source_repo": str(legacy.get("source_repo", "")).strip(),
                        "artifacts": {
                            "system_overlay": {
                                "name": str(legacy.get("artifact", "")).strip(),
                                "sha256": "",
                            },
                            "installer_assets": {
                                "name": str(legacy.get("installer_assets", "")).strip(),
                                "sha256": "",
                            },
                            "installer_iso": {
                                "name": str(legacy.get("installer_iso", "")).strip(),
                                "sha256": "",
                            },
                        },
                        "signing": {
                            "mode": "legacy-metadata",
                            "signature_verified": False,
                            "key_id": "",
                            "notes": "Legacy build manifest loaded without detached signatures.",
                        },
                    }
        return {}

    def read_installed_version(self) -> str:
        status = self.load_update_status()
        status_version = str(status.get("installed_version", "")).strip()
        if status_version:
            return status_version
        manifest = self.load_release_manifest()
        manifest_version = str(manifest.get("version", "")).strip()
        if manifest_version:
            return manifest_version
        build_info = self.read_build_info()
        build_info_version = str(build_info.get("NMOS_VERSION", "")).strip()
        if build_info_version:
            return build_info_version
        version_path = self.repo_root / "config" / "version"
        if version_path.exists():
            try:
                version = version_path.read_text(encoding="utf-8").strip()
                if version:
                    return version
            except OSError:
                pass
        return "unknown"

    def _normalize_update_catalog(self, payload: object) -> dict[str, dict[str, str]]:
        catalog_root = payload if isinstance(payload, dict) else {}
        channels = catalog_root.get("channels", catalog_root) if isinstance(catalog_root, dict) else {}
        if not isinstance(channels, dict):
            return {}
        catalog: dict[str, dict[str, str]] = {}
        for channel in ("stable", "beta", "nightly"):
            item = channels.get(channel, {})
            if not isinstance(item, dict):
                continue
            catalog[channel] = {
                "version": str(item.get("version", "")).strip(),
                "notes": str(item.get("notes", "")).strip(),
            }
        return catalog

    def load_update_catalog(self) -> dict[str, dict[str, str]]:
        try:
            backend_channels = self.update_client.get_channels()
            backend_payload = backend_channels.get("channels", {}) if isinstance(backend_channels, dict) else {}
            normalized_backend = self._normalize_update_catalog({"channels": backend_payload})
            if normalized_backend:
                return normalized_backend
        except UpdateClientError:
            pass
        for path in (
            self.shared_update_catalog_file,
            self.dist_update_catalog_file,
            self.update_catalog_file,
        ):
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            catalog = self._normalize_update_catalog(payload)
            if catalog:
                return catalog
        manifest = self.load_release_manifest()
        manifest_version = str(manifest.get("version", "")).strip()
        manifest_channel = str(manifest.get("channel", "")).strip()
        if manifest_version and manifest_channel:
            return {
                "stable": {"version": "", "notes": "No stable release published in the local catalog."},
                "beta": {"version": "", "notes": "No beta release published in the local catalog."},
                "nightly": {"version": "", "notes": "No nightly release published in the local catalog."},
                manifest_channel: {
                    "version": manifest_version,
                    "notes": "Local release manifest detected. Check signed catalog metadata before updating across channels.",
                },
            }
        installed = self.read_installed_version()
        return {
            "stable": {"version": installed, "notes": "No catalog published."},
            "beta": {"version": installed, "notes": "No catalog published."},
            "nightly": {"version": installed, "notes": "No catalog published."},
        }

    def _manifest_supports_trusted_updates(self) -> tuple[bool, str]:
        status = self.load_update_status()
        if bool(status.get("manifest_signature_verified", False)):
            return True, "Update metadata verified with detached signatures."
        guardrail = str(status.get("guardrail_update", "")).strip()
        if guardrail:
            return False, guardrail
        manifest = self.load_release_manifest()
        if not manifest:
            return False, "Update blocked: release manifest metadata is unavailable."
        signing = as_object_dict(manifest.get("signing", {}))
        signature_verified = bool(signing.get("signature_verified") is True)
        signing_mode = str(signing.get("mode", "")).strip().lower()
        if signature_verified:
            return True, "Update metadata verified with detached signatures."
        if signing_mode == "checksum":
            return True, "Update metadata verified with checksum policy."
        return False, "Update blocked: trusted signing metadata is missing or unsupported."

    def _manifest_supports_rollback(self) -> tuple[bool, str]:
        status = self.load_update_status()
        guardrail = str(status.get("guardrail_rollback", "")).strip()
        if guardrail:
            if guardrail.startswith("Rollback is supported"):
                return True, guardrail
            return False, guardrail
        trusted_ok, trusted_message = self._manifest_supports_trusted_updates()
        if not trusted_ok:
            return False, trusted_message
        manifest = self.load_release_manifest()
        upgrade_policy = as_object_dict(manifest.get("upgrade_policy", {}))
        supports_rollback_raw = str(upgrade_policy.get("supports_rollback", "")).strip().lower()
        supports_rollback = supports_rollback_raw in {"1", "true", "yes", "on"}
        if supports_rollback:
            return True, "Rollback is supported by current release policy."
        return False, "Rollback blocked: current release policy does not declare rollback support."

    def refresh_update_center(self, *, persist_status: bool = False) -> None:
        status = self.load_update_status()
        installed_version = str(status.get("installed_version", "")).strip() or self.read_installed_version()
        default_channel = self.detect_release_channel(installed_version)
        selected_channel = self._selected_update_channel()
        if selected_channel not in {value for value, _label in self.UPDATE_CHANNEL_OPTIONS}:
            selected_channel = str(status.get("channel", default_channel) or default_channel)
        catalog = self.load_update_catalog()
        available = catalog.get(selected_channel, {})
        available_version = str(status.get("available_version", "")).strip() or str(available.get("version", "")).strip() or "unknown"
        available_notes = str(available.get("notes", "")).strip() or "No release notes."
        has_update = (
            available_version not in {"", "unknown"}
            and installed_version not in {"", "unknown"}
            and available_version != installed_version
        )
        updates_allowed, update_guardrail = self._manifest_supports_trusted_updates()
        rollback_allowed, rollback_guardrail = self._manifest_supports_rollback()
        last_checked_at = str(status.get("last_checked_at", "never"))
        last_action = str(status.get("last_action", "No update action yet."))
        backend_state = str(status.get("state", "idle")).strip()
        state_line = "Update available." if has_update else "System is up to date for selected channel."
        self.update_status_label.set_text(
            "\n".join(
                [
                    f"Installed version: {installed_version}",
                    f"Selected channel: {selected_channel}",
                    f"Available version: {available_version}",
                    f"Engine state: {backend_state}",
                    f"State: {state_line}",
                    f"Last checked: {last_checked_at}",
                    f"Last action: {last_action}",
                    f"Release notes: {available_notes}",
                    f"Update guardrail: {update_guardrail}",
                    f"Rollback guardrail: {rollback_guardrail}",
                ]
            )
        )
        staged = backend_state in {"staged", "switching_on_reboot", "awaiting_health_ack"}
        self.update_apply_button.set_sensitive((has_update or staged) and updates_allowed)
        self.update_rollback_button.set_sensitive((len(self.load_update_history()) > 0 or staged) and rollback_allowed)
        if persist_status:
            next_status = dict(status)
            next_status["channel"] = selected_channel
            if "installed_version" not in next_status:
                next_status["installed_version"] = installed_version
            self.write_update_status(next_status)

    def format_trust_chain_status(self) -> str:
        manifest = self.load_release_manifest()
        build_info = self.read_build_info()
        version = self.read_installed_version()
        channel = str(manifest.get("channel", "")).strip() or self.detect_release_channel(version)
        build_id = str(manifest.get("build_id", "")).strip() or str(build_info.get("BUILD_TIMESTAMP", "unknown")).strip()
        artifacts = as_object_dict(manifest.get("artifacts", {}))
        installer_iso = as_object_dict(artifacts.get("installer_iso", {}))
        artifact_name = str(installer_iso.get("name", "")).strip() or str(manifest.get("installer_iso", "unknown"))
        signing = as_object_dict(manifest.get("signing", {}))
        signing_mode = str(signing.get("mode", "")).strip()
        if signing.get("signature_verified") is True:
            signature_state = "detached signatures verified"
        elif signing_mode == "checksum":
            signature_state = "checksum manifest only"
        elif signing_mode:
            signature_state = signing_mode
        else:
            signature_state = "not available in current build"
        upgrade_policy = as_object_dict(manifest.get("upgrade_policy", {}))
        minimum_source_version = str(upgrade_policy.get("minimum_source_version", "unknown"))
        rollback_support = str(upgrade_policy.get("supports_rollback", "unknown")).lower()
        verification = "partial"
        if manifest:
            verification = "release manifest available"
        if signing.get("signature_verified") is True:
            verification = "signed metadata verified"
        elif signing_mode == "checksum":
            verification = "artifact checksums recorded"
        return "\n".join(
            [
                f"Installed version: {version}",
                f"Channel: {channel}",
                f"Build id: {build_id}",
                f"Installer artifact: {artifact_name or 'unknown'}",
                f"Signatures: {signature_state}",
                f"Verification status: {verification}",
                f"Upgrade floor: {minimum_source_version}",
                f"Rollback support: {rollback_support}",
            ]
        )

    def on_update_channel_changed(self, *_args) -> None:
        self.refresh_update_center(persist_status=True)

    def on_check_updates(self, _button: Gtk.Button) -> None:
        channel = self._selected_update_channel()
        try:
            self.update_client.check_for_updates(channel)
            self.refresh_update_center(persist_status=True)
            self.status_label.set_text("Update check completed.")
        except UpdateClientError as error:
            self.refresh_update_center(persist_status=True)
            self.status_label.set_text(error.user_message())

    def on_apply_update(self, _button: Gtk.Button) -> None:
        status = self.load_update_status()
        backend_state = str(status.get("state", "idle")).strip()
        channel = self._selected_update_channel()
        try:
            if backend_state == "staged":
                self.update_client.commit_staged_update()
                self.refresh_update_center(persist_status=True)
                self.status_label.set_text("Staged update committed. Reboot to activate the new slot.")
                return
            self.update_client.stage_update(channel)
            self.update_client.commit_staged_update()
            self.trust_chain_label.set_text(self.format_trust_chain_status())
            self.refresh_update_center(persist_status=True)
            self.status_label.set_text("Update staged and committed. Reboot to activate the new slot.")
        except UpdateClientError as error:
            self.refresh_update_center(persist_status=True)
            self.status_label.set_text(error.user_message())

    def on_rollback_update(self, _button: Gtk.Button) -> None:
        try:
            self.update_client.rollback_to_previous_slot()
            self.trust_chain_label.set_text(self.format_trust_chain_status())
            self.refresh_update_center(persist_status=True)
            self.status_label.set_text("Rollback staged to the previous slot. Reboot and verify package state.")
        except UpdateClientError as error:
            self.refresh_update_center(persist_status=True)
            self.status_label.set_text(error.user_message())

    def try_lock_vault_now(self) -> bool:
        try:
            from nmos_common.settings_client import load_dbus

            dbus = load_dbus()
            bus = dbus.SystemBus()
            proxy = bus.get_object("org.nmos.PersistentStorage", "/org/nmos/PersistentStorage", introspect=False)
            interface = dbus.Interface(proxy, "org.nmos.PersistentStorage")
            interface.Lock()
            return True
        except Exception:
            return False

    def build_ui(self) -> None:
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label="NM-OS Control Center", xalign=0)
        title.add_css_class("title-1")
        subtitle = Gtk.Label(
            label="Tune privacy, Appearance, and recovery behavior without leaving the desktop.",
            xalign=0,
        )
        subtitle.set_wrap(True)
        subtitle.add_css_class("dim-label")
        header.append(title)
        header.append(subtitle)
        self.root.append(header)

        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        self.root.append(split)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.sidebar = Gtk.StackSidebar()
        self.sidebar.set_stack(self.stack)
        self.sidebar.set_vexpand(True)
        self.sidebar.set_size_request(240, -1)
        split.append(self.sidebar)
        split.append(self.stack)

        self.personalization_page = personalization.build(self)
        self.applications_page = applications.build(self)
        self.network_page = network.build(self)
        self.security_page = security.build(self)
        self.system_page = system.build(self)
        self.language_page = language.build(self)

        pages = [
            ("personalization", "Personalization", self.personalization_page),
            ("applications", "Applications", self.applications_page),
            ("network", "Network & Internet", self.network_page),
            ("security", "Security & Profiles", self.security_page),
            ("system", "System & Recovery", self.system_page),
            ("language", "Language & Region", self.language_page),
        ]
        for key, title_text, widget in pages:
            self.stack.add_titled(widget, key, title_text)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.help_button = Gtk.Button(label="Help")
        self.refresh_button = Gtk.Button(label="Refresh")
        self.diagnostics_button = Gtk.Button(label="Diagnostics")
        self.reset_button = Gtk.Button(label="Reset To Profile")
        self.apply_button = Gtk.Button(label="Apply Changes")
        self.status_label = Gtk.Label(xalign=0)
        self.status_label.set_hexpand(True)
        self.status_label.set_wrap(True)
        self.status_label.add_css_class("dim-label")
        self.help_button.connect("clicked", self.on_open_help)
        self.refresh_button.connect("clicked", self.on_refresh)
        self.diagnostics_button.connect("clicked", self.on_diagnostics)
        self.reset_button.connect("clicked", self.on_reset_to_profile)
        self.apply_button.connect("clicked", self.on_apply)
        actions.append(self.status_label)
        actions.append(self.help_button)
        actions.append(self.refresh_button)
        actions.append(self.diagnostics_button)
        actions.append(self.reset_button)
        actions.append(self.apply_button)
        self.root.append(actions)

    def restore_settings(self) -> None:
        settings = self.settings
        profile = str(settings.get("active_profile", "balanced"))
        locale = resolve_supported_locale(settings.get("locale", "en_US.UTF-8"))
        keyboard = str(settings.get("keyboard", "us"))
        network_policy = str(settings.get("network_policy", "direct"))
        sandbox_default = str(settings.get("sandbox_default", "focused"))
        device_policy = str(settings.get("device_policy", "prompt"))
        logging_policy = str(settings.get("logging_policy", "minimal"))
        ram_wipe_mode = str(settings.get("ram_wipe_mode", "balanced"))
        theme_profile = str(settings.get("ui_theme_profile", "nmos-classic"))
        accent = str(settings.get("ui_accent", "amber"))
        density = str(settings.get("ui_density", "comfortable"))
        motion = str(settings.get("ui_motion", "full"))
        default_browser = str(settings.get("default_browser", "firefox-esr"))
        vault = settings.get("vault", {})
        auto_lock = str(vault.get("auto_lock_minutes", 15))

        self._set_dropdown_value(self.profile_combo, self.profile_values, profile)
        self._set_dropdown_value(self.language_combo, self.language_values, locale)
        self._set_dropdown_value(self.keyboard_combo, list(KEYBOARD_OPTIONS), keyboard)
        self._set_dropdown_value(self.network_combo, [value for value, _label in NETWORK_OPTIONS], network_policy)
        self._set_dropdown_value(self.sandbox_combo, [value for value, _label in SANDBOX_OPTIONS], sandbox_default)
        self._set_dropdown_value(self.device_policy_combo, [value for value, _label in DEVICE_POLICY_OPTIONS], device_policy)
        self._set_dropdown_value(self.logging_combo, [value for value, _label in LOGGING_OPTIONS], logging_policy)
        self._set_dropdown_value(self.ram_wipe_combo, [value for value, _label in RAM_WIPE_OPTIONS], ram_wipe_mode)
        self._set_dropdown_value(self.theme_profile_combo, [value for value, _label in THEME_PROFILE_OPTIONS], theme_profile)
        self._set_dropdown_value(self.accent_combo, [value for value, _label in ACCENT_OPTIONS], accent)
        self._set_dropdown_value(self.density_combo, [value for value, _label in DENSITY_OPTIONS], density)
        self._set_dropdown_value(self.motion_combo, [value for value, _label in MOTION_OPTIONS], motion)
        self._set_dropdown_value(self.default_browser_combo, [value for value, _label in DEFAULT_BROWSER_OPTIONS], default_browser)
        self._set_dropdown_value(self.vault_auto_lock_combo, [value for value, _label in VAULT_AUTO_LOCK_OPTIONS], auto_lock)
        update_status = self.load_update_status()
        update_channel = str(
            update_status.get("channel", self.detect_release_channel(self.read_installed_version()))
        )
        self._set_dropdown_value(
            self.update_channel_combo,
            [value for value, _label in UPDATE_CHANNEL_OPTIONS],
            update_channel,
        )
        self.brave_switch.set_active(bool(settings.get("allow_brave_browser", False)))
        self.vault_unlock_on_login.set_active(bool(vault.get("unlock_on_login", False)))
        self.vault_passphrase_entry.set_text("")
        self.vault_passphrase_strength.set_text(passphrase_feedback_text(""))
        self.rebuild_app_overrides_editor(settings)
        self.ui_locale = locale
        self.preview_theme()

    def preview_theme(self) -> None:
        apply_window_theme(
            self.root,
            {
                "ui_theme_profile": self._selected_value(self.theme_profile_combo, [value for value, _label in THEME_PROFILE_OPTIONS]),
                "ui_accent": self._selected_value(self.accent_combo, [value for value, _label in ACCENT_OPTIONS]),
                "ui_density": self._selected_value(self.density_combo, [value for value, _label in DENSITY_OPTIONS]),
                "ui_motion": self._selected_value(self.motion_combo, [value for value, _label in MOTION_OPTIONS]),
            },
        )

    def collect_values(self) -> dict:
        return {
            "locale": self._selected_value(self.language_combo, self.language_values),
            "keyboard": self._selected_value(self.keyboard_combo, list(KEYBOARD_OPTIONS)),
            "network_policy": self._selected_value(self.network_combo, [value for value, _label in NETWORK_OPTIONS]),
            "allow_brave_browser": self.brave_switch.get_active(),
            "sandbox_default": self._selected_value(self.sandbox_combo, [value for value, _label in SANDBOX_OPTIONS]),
            "default_browser": self._selected_value(
                self.default_browser_combo,
                [value for value, _label in DEFAULT_BROWSER_OPTIONS],
            ),
            "vault": {
                "enabled": True,
                "auto_lock_minutes": int(
                    self._selected_value(self.vault_auto_lock_combo, [value for value, _label in VAULT_AUTO_LOCK_OPTIONS])
                ),
                "unlock_on_login": self.vault_unlock_on_login.get_active(),
            },
            "device_policy": self._selected_value(self.device_policy_combo, [value for value, _label in DEVICE_POLICY_OPTIONS]),
            "logging_policy": self._selected_value(self.logging_combo, [value for value, _label in LOGGING_OPTIONS]),
            "ram_wipe_mode": self._selected_value(self.ram_wipe_combo, [value for value, _label in RAM_WIPE_OPTIONS]),
            "ui_theme_profile": self._selected_value(self.theme_profile_combo, [value for value, _label in THEME_PROFILE_OPTIONS]),
            "ui_accent": self._selected_value(self.accent_combo, [value for value, _label in ACCENT_OPTIONS]),
            "ui_density": self._selected_value(self.density_combo, [value for value, _label in DENSITY_OPTIONS]),
            "ui_motion": self._selected_value(self.motion_combo, [value for value, _label in MOTION_OPTIONS]),
            "app_overrides": self.collect_app_overrides(),
        }

    def refresh_summary(self) -> None:
        profile = self._selected_value(self.profile_combo, self.profile_values)
        draft_values = self.collect_values()
        self.ui_locale = resolve_supported_locale(self._selected_value(self.language_combo, self.language_values))
        posture = describe_posture_preview(profile, {"active_profile": profile, **draft_values})
        draft_settings = normalize_system_settings(
            {
                "active_profile": profile,
                "overrides": derive_overrides_for_profile(profile, draft_values),
            }
        )
        self.profile_summary.set_text(self.tr(posture["summary"]))
        self.profile_guidance.set_text(self.tr(posture["ideal_for"]))
        self.profile_tradeoff.set_text(self.tr(posture["tradeoff"]))
        self.profile_meter_label.set_text("\n".join(posture_meter_lines(self.ui_locale, posture)))
        current_scores = compute_posture_scores(self.settings)
        shift = compute_posture_score_shift(current_scores, posture.get("scores", {}))
        self.profile_shift_label.set_text(format_posture_shift(self.ui_locale, shift))
        self.profile_details.set_text(
            "\n".join(f"- {line}" for line in posture_explanation_lines(self.ui_locale, posture))
        )
        effective_payload = {
            "active_profile": profile,
            "overrides": derive_overrides_for_profile(profile, draft_values),
        }
        change_details = describe_effective_change_details(effective_payload)
        immediate_details = change_details["immediate"]
        reboot_details = change_details["reboot"]
        immediate_labels = [self.tr(setting_display_name(str(item["key"]))) for item in immediate_details]
        reboot_labels = [self.tr(setting_display_name(str(item["key"]))) for item in reboot_details]
        if immediate_labels or reboot_labels:
            self.change_timing_label.set_text(
                "\n".join(
                    [
                        self.tr(
                            "Applies now: {changes}",
                            changes=", ".join(immediate_labels) if immediate_labels else self.tr("None"),
                        ),
                        self.tr(
                            "Applies after reboot: {changes}",
                            changes=", ".join(reboot_labels) if reboot_labels else self.tr("None"),
                        ),
                    ]
                )
            )
            detail_lines: list[str] = []
            if immediate_details:
                detail_lines.append(self.tr("Change details (now):"))
                detail_lines.extend(
                    f"- {format_change_detail(self.ui_locale, self.tr(setting_display_name(str(item['key']))), str(item['key']), item.get('from'), item.get('to'))}"
                    for item in immediate_details
                )
            if reboot_details:
                detail_lines.append(self.tr("Change details (after reboot):"))
                detail_lines.extend(
                    f"- {format_change_detail(self.ui_locale, self.tr(setting_display_name(str(item['key']))), str(item['key']), item.get('from'), item.get('to'))}"
                    for item in reboot_details
                )
            self.change_detail_label.set_text("\n".join(detail_lines))
        else:
            self.change_timing_label.set_text(self.tr("No changed settings in the current draft."))
            self.change_detail_label.set_text("")
        self.privacy_explanation.set_text(
            "\n".join(
                [
                    explain_network_policy(self.ui_locale, draft_values["network_policy"]),
                    explain_brave_visibility(
                        self.ui_locale,
                        bool(draft_values["allow_brave_browser"]),
                        str(draft_values["network_policy"]),
                    ),
                ]
            )
        )
        self.apps_explanation.set_text(
            explain_sandbox_default(self.ui_locale, str(draft_values["sandbox_default"]))
        )
        self.vault_explanation.set_text(
            "\n".join(explain_vault_behavior(self.ui_locale, draft_values["vault"]))
        )
        self.vault_passphrase_strength.set_text(passphrase_feedback_text(self.vault_passphrase_entry.get_text()))
        self.system_explanation.set_text(
            "\n".join(
                [
                    explain_device_policy(self.ui_locale, str(draft_values["device_policy"])),
                    explain_logging_policy(self.ui_locale, str(draft_values["logging_policy"])),
                    "RAM wipe policy controls kernel memory scrubbing flags and usually needs a reboot.",
                ]
            )
        )
        self.enforcement_status_label.set_text(self.format_policy_runtime_status())
        self.privacy_dashboard_label.set_text(
            self.format_privacy_dashboard(draft_values=draft_values, change_details=change_details)
        )
        self.trust_chain_label.set_text(self.format_trust_chain_status())
        self.recovery_status_label.set_text(self.format_recovery_status())
        self.ram_wipe_status_label.set_text(self.format_ram_wipe_status())
        self.refresh_update_center()
        self.network_change_explanation.set_text(
            self.build_setting_change_explanation(key="network_policy", details=change_details)
        )
        self.profile_change_explanation.set_text(
            self.build_setting_change_explanation(key="active_profile", details=change_details)
        )
        self.brave_change_explanation.set_text(
            self.build_setting_change_explanation(key="allow_brave_browser", details=change_details)
        )
        self.default_browser_change_explanation.set_text(
            self.build_setting_change_explanation(key="default_browser", details=change_details)
        )
        self.sandbox_change_explanation.set_text(
            self.build_setting_change_explanation(key="sandbox_default", details=change_details)
        )
        self.app_overrides_change_explanation.set_text(
            self.build_setting_change_explanation(key="app_overrides", details=change_details)
        )
        self.vault_auto_lock_change_explanation.set_text(
            self.build_setting_change_explanation(key="vault_auto_lock_minutes", details=change_details)
        )
        self.vault_unlock_change_explanation.set_text(
            self.build_setting_change_explanation(key="vault_unlock_on_login", details=change_details)
        )
        self.device_policy_change_explanation.set_text(
            self.build_setting_change_explanation(key="device_policy", details=change_details)
        )
        self.logging_change_explanation.set_text(
            self.build_setting_change_explanation(key="logging_policy", details=change_details)
        )
        self.ram_wipe_change_explanation.set_text(
            self.build_setting_change_explanation(key="ram_wipe_mode", details=change_details)
        )
        pending = draft_settings.get("pending_reboot", [])
        if pending:
            self.pending_reboot_label.set_text(
                self.tr(
                    "Restart required for: {pending}",
                    pending=", ".join(str(item).replace("_", " ") for item in pending),
                )
            )
        else:
            self.pending_reboot_label.set_text(self.tr("The current draft does not require a reboot."))

    def on_profile_preview_changed(self, *_args) -> None:
        self.refresh_summary()

    def on_draft_settings_changed(self, *_args) -> None:
        self.refresh_summary()

    def on_theme_preview_changed(self, *_args) -> None:
        self.preview_theme()
        self.refresh_summary()

    def on_apply_sandbox_preset(self, _button: Gtk.Button) -> None:
        preset = self._selected_option_value(self.sandbox_preset_combo, self.APP_SANDBOX_PRESET_OPTIONS)
        self.apply_sandbox_preset(preset)
        self.refresh_summary()
        self.status_label.set_text(f"Sandbox preset applied: {preset}. Review and click Apply Changes.")

    def on_refresh(self, _button: Gtk.Button) -> None:
        try:
            self.settings = self.client.get_settings()
            self.backend_ready = True
            self._set_backend_action_sensitivity(True)
        except SettingsClientError as error:
            self.backend_ready = False
            self._set_backend_action_sensitivity(False)
            self._set_review_mode_status(self.format_backend_guidance(error))
            return
        self.restore_settings()
        self.refresh_summary()
        self.status_label.set_text("Settings refreshed.")

    def on_reset_to_profile(self, _button: Gtk.Button) -> None:
        if not self._guard_backend_mutation():
            return
        snapshot_saved = self.snapshot_current_settings(reason="Before reset to profile")
        try:
            self.client.apply_preset(self._selected_value(self.profile_combo, self.profile_values))
            self.settings = self.client.commit()
        except SettingsClientError as error:
            self.status_label.set_text(self.format_backend_guidance(error))
            return
        self.restore_settings()
        self.refresh_summary()
        if snapshot_saved:
            self.status_label.set_text("Overrides removed. The selected profile is active again. Rollback snapshot captured.")
        else:
            self.status_label.set_text("Overrides removed. The selected profile is active again.")

    def on_apply(self, _button: Gtk.Button) -> bool:
        if not self._guard_backend_mutation():
            return False
        profile = self._selected_value(self.profile_combo, self.profile_values)
        values = self.collect_values()
        overrides = derive_overrides_for_profile(profile, values)
        snapshot_saved = self.snapshot_current_settings(reason="Before apply changes")
        try:
            self.client.apply_preset(profile)
            if overrides:
                self.client.set_overrides(overrides)
            self.settings = self.client.commit()
        except SettingsClientError as error:
            self.status_label.set_text(self.format_backend_guidance(error))
            return False
        self.restore_settings()
        self.refresh_summary()
        if self.settings.get("pending_reboot"):
            if snapshot_saved:
                self.status_label.set_text("Changes saved. Some protections apply after the next reboot. Rollback snapshot captured.")
            else:
                self.status_label.set_text("Changes saved. Some protections apply after the next reboot.")
        else:
            if snapshot_saved:
                self.status_label.set_text("Changes saved. Rollback snapshot captured.")
            else:
                self.status_label.set_text("Changes saved.")
        return True

    def on_apply_comfort_mode(self, _button: Gtk.Button) -> None:
        if not self._guard_backend_mutation():
            return
        snapshot_saved = self.snapshot_current_settings(reason="Before comfort mode")
        current_overrides = self.settings.get("overrides", {})
        if not isinstance(current_overrides, dict):
            current_overrides = {}
        try:
            self.client.apply_preset("relaxed")
            if current_overrides:
                self.client.set_overrides(current_overrides)
            self.settings = self.client.commit()
        except SettingsClientError as error:
            self.status_label.set_text(self.format_backend_guidance(error))
            return
        self.restore_settings()
        self.refresh_summary()
        if snapshot_saved:
            self.status_label.set_text("Comfort Mode applied with existing overrides preserved. Rollback snapshot captured.")
        else:
            self.status_label.set_text("Comfort Mode applied with existing overrides preserved.")

    def on_emergency_lockdown(self, _button: Gtk.Button) -> None:
        if not self._guard_backend_mutation():
            return
        self._set_dropdown_value(self.network_combo, [value for value, _label in self.NETWORK_OPTIONS], "offline")
        self._set_dropdown_value(self.logging_combo, [value for value, _label in self.LOGGING_OPTIONS], "sealed")
        self._set_dropdown_value(self.device_policy_combo, [value for value, _label in self.DEVICE_POLICY_OPTIONS], "locked")
        self._set_dropdown_value(self.sandbox_combo, [value for value, _label in self.SANDBOX_OPTIONS], "strict")
        self._set_dropdown_value(self.ram_wipe_combo, [value for value, _label in self.RAM_WIPE_OPTIONS], "strict")
        self._set_dropdown_value(self.vault_auto_lock_combo, [value for value, _label in self.VAULT_AUTO_LOCK_OPTIONS], "0")
        self.vault_unlock_on_login.set_active(False)
        self.set_all_app_overrides(filesystem="none", network="isolated", devices="none")
        self.refresh_summary()
        if not self.on_apply(self.apply_button):
            self.status_label.set_text(
                "Emergency Lockdown draft prepared, but applying changes failed. Resolve backend issue and retry Apply Changes."
            )
            return
        locked_now = self.try_lock_vault_now()
        suffix = " Vault locked now." if locked_now else " Vault lock will apply on next service action."
        self.status_label.set_text("Emergency Lockdown applied: offline, sealed logging, locked devices, strict app isolation." + suffix)

    def on_refresh_trust_chain(self, _button: Gtk.Button) -> None:
        self.trust_chain_label.set_text(self.format_trust_chain_status())
        self.status_label.set_text("Trust chain data refreshed.")

    def on_create_diagnostics_bundle(self, _button: Gtk.Button) -> None:
        bundle = self.build_diagnostics_bundle()
        try:
            write_runtime_json(self.recovery_bundle_file, bundle)
        except OSError:
            self.status_label.set_text("Diagnostics bundle could not be written to the runtime directory.")
            return
        self.recovery_status_label.set_text(self.format_recovery_status())
        self.status_label.set_text(f"Diagnostics bundle created: {self.recovery_bundle_file}")

    def on_rollback_settings_snapshot(self, _button: Gtk.Button) -> None:
        if not self._guard_backend_mutation():
            return
        snapshot = self.load_settings_snapshot()
        target_settings = as_object_dict(snapshot.get("settings", {}))
        if not target_settings:
            self.recovery_status_label.set_text(self.format_recovery_status())
            self.status_label.set_text("No rollback snapshot is available yet.")
            return
        current_settings = normalize_system_settings(self.settings)
        target_profile = str(target_settings.get("active_profile", "balanced"))
        target_overrides = target_settings.get("overrides", {})
        if not isinstance(target_overrides, dict):
            target_overrides = {}
        try:
            self.client.apply_preset(target_profile)
            if target_overrides:
                self.client.set_overrides(target_overrides)
            self.settings = self.client.commit()
        except SettingsClientError as error:
            self.status_label.set_text(self.format_backend_guidance(error))
            return
        try:
            self.write_settings_snapshot(
                {
                    "taken_at": self._current_timestamp(),
                    "reason": "Rollback undo point",
                    "settings": current_settings,
                }
            )
        except OSError:
            pass
        self.restore_settings()
        self.refresh_summary()
        self.status_label.set_text(
            f"Settings rolled back to snapshot from {snapshot.get('taken_at', 'an earlier session')}."
        )

    def on_diagnostics(self, _button: Gtk.Button) -> None:
        self.status_label.set_text(
            "Diagnostics: systemctl status nmos-settings.service nmos-app-isolation-policy.service "
            "nmos-device-policy.service nmos-logging-policy.service; "
            "journalctl -u nmos-settings.service -u nmos-app-isolation-policy.service "
            "-u nmos-device-policy.service -u nmos-logging-policy.service -n 50"
        )

    def _launch_help_app(self) -> bool:
        try:
            subprocess.Popen(["/usr/local/bin/nmos-help"])
            return True
        except OSError:
            try:
                subprocess.Popen(["python3", "-m", "nmos_help.main"])
                return True
            except OSError:
                return False

    def on_open_help(self, _button: Gtk.Button) -> None:
        if self._launch_help_app():
            self.status_label.set_text("Help opened.")
            return
        self.status_label.set_text("Help could not be launched from this session.")

    def on_open_user_guides(self, _button: Gtk.Button) -> None:
        if self._launch_help_app():
            self.status_label.set_text("User guides opened.")
            return
        self.status_label.set_text("User guides could not be launched from this session.")


class ControlCenterApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="org.nmos.ControlCenter")

    def do_activate(self) -> None:
        load_css()
        window = self.props.active_window
        if window is None:
            window = ControlCenterWindow(self)
        window.present()


def main() -> None:
    app = ControlCenterApplication()
    app.run([])


if __name__ == "__main__":
    main()
