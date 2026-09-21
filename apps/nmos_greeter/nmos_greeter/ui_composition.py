from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from nmos_common.i18n import (
    display_language_name,
    display_network_policy_name,
    explain_brave_visibility,
    explain_network_policy,
    format_posture_shift,
    posture_explanation_lines,
    posture_meter_lines,
    resolve_supported_locale,
)
from nmos_common.passphrase_policy import passphrase_feedback_text
from nmos_common.system_settings import (
    ACCENT_LABELS,
    DENSITY_LABELS,
    MOTION_LABELS,
    PROFILE_METADATA,
    THEME_PROFILE_LABELS,
    compute_posture_score_shift,
    compute_posture_scores,
    describe_posture_preview,
)
from nmos_common.ui_theme import apply_window_theme

from nmos_greeter.browser_model import BROWSER_OPTIONS, browser_description, browser_label, browser_to_default_setting

KEYBOARD_OPTIONS = ["us", "tr", "de", "fr"]
NETWORK_POLICY_OPTIONS = ["tor", "direct", "offline"]


def _combo(values: list[str]) -> Gtk.DropDown:
    model = Gtk.StringList.new(values)
    return Gtk.DropDown(model=model)


def _page(window, page_key: str, title_text: str, subtitle_text: str, controls: list[Gtk.Widget]) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    title = Gtk.Label(label=title_text, xalign=0)
    title.add_css_class("title-3")
    subtitle = Gtk.Label(label=subtitle_text, xalign=0)
    subtitle.set_wrap(True)
    subtitle.add_css_class("dim-label")
    setattr(window, f"{page_key}_title_label", title)
    setattr(window, f"{page_key}_subtitle_label", subtitle)
    box.append(title)
    box.append(subtitle)
    for control in controls:
        box.append(control)
    return box


def _profile_page(window) -> Gtk.Widget:
    return _page(
        window,
        "profile",
        "Security profile",
        "Choose a starting point. You can still fine-tune it later from the desktop.",
        [
            window.profile_combo,
            window.profile_summary_label,
            window.profile_guidance_label,
            window.profile_tradeoff_label,
            window.profile_details_label,
        ],
    )


def _browser_page(window) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    window.browser_title_label = Gtk.Label(label="Web Browser", xalign=0)
    window.browser_title_label.add_css_class("title-3")
    window.browser_subtitle_label = Gtk.Label(label="Choose your default web browser.", xalign=0)
    window.browser_subtitle_label.set_wrap(True)
    window.browser_subtitle_label.add_css_class("dim-label")
    box.append(window.browser_title_label)
    box.append(window.browser_subtitle_label)
    box.append(window.browser_combo)
    box.append(window.browser_explanation_label)
    return box


def _network_page(window) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    window.network_title_label = Gtk.Label(label="Network Policy", xalign=0)
    window.network_title_label.add_css_class("title-3")
    window.network_subtitle_label = Gtk.Label(label="Choose how NM-OS should treat network access.", xalign=0)
    window.network_subtitle_label.set_wrap(True)
    window.network_subtitle_label.add_css_class("dim-label")
    box.append(window.network_title_label)
    box.append(window.network_subtitle_label)
    box.append(window.network_policy_combo)
    box.append(window.network_explanation_label)
    box.append(window.allow_brave_browser_switch)
    box.append(window.allow_brave_browser_label)
    return box


def _appearance_page(window) -> Gtk.Widget:
    return _page(
        window,
        "appearance",
        "Appearance",
        "Customize the visual language to your liking.",
        [
            window.theme_profile_combo,
            window.accent_combo,
            window.density_combo,
            window.motion_combo,
        ],
    )


def _summary_page(window) -> Gtk.Widget:
    passphrase_hint_label = Gtk.Label(label="Vault passphrase check (optional)", xalign=0)
    passphrase_hint_label.add_css_class("dim-label")
    return _page(
        window,
        "summary",
        "Ready to start",
        "These settings will be applied now. You can change them later from the Control Center.",
        [
            window.summary_label,
            window.summary_meter_label,
            window.summary_shift_label,
            window.summary_posture_label,
            passphrase_hint_label,
            window.vault_passphrase_entry,
            window.vault_passphrase_strength,
        ],
    )


def build_ui(window) -> None:
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
    root.set_margin_top(24)
    root.set_margin_bottom(24)
    root.set_margin_start(24)
    root.set_margin_end(24)
    window.root_container = root

    header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    window.header_title_label = Gtk.Label(label="NM-OS Setup")
    window.header_title_label.add_css_class("title-1")
    window.header_title_label.set_xalign(0)
    window.header_subtitle_label = Gtk.Label(xalign=0)
    window.header_subtitle_label.set_wrap(True)
    window.header_subtitle_label.add_css_class("dim-label")
    header.append(window.header_title_label)
    header.append(window.header_subtitle_label)
    root.append(header)

    window.session_status = Gtk.Label(xalign=0)
    window.session_status.set_wrap(True)
    window.session_status.add_css_class("caption")
    root.append(window.session_status)

    window.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
    window.stack.set_vexpand(True)

    window.language_combo = _combo([display_language_name(locale) for locale in window.language_values])
    window.keyboard_combo = _combo(KEYBOARD_OPTIONS)
    window.profile_combo = _combo([PROFILE_METADATA[profile]["label"] for profile in window.profile_values])
    window.profile_combo.connect("notify::selected", window.on_profile_changed)
    window.profile_summary_label = Gtk.Label(xalign=0)
    window.profile_summary_label.set_wrap(True)
    window.profile_summary_label.add_css_class("dim-label")
    window.profile_guidance_label = Gtk.Label(xalign=0)
    window.profile_guidance_label.set_wrap(True)
    window.profile_guidance_label.add_css_class("dim-label")
    window.profile_tradeoff_label = Gtk.Label(xalign=0)
    window.profile_tradeoff_label.set_wrap(True)
    window.profile_tradeoff_label.add_css_class("dim-label")
    window.network_policy_combo = _combo([display_network_policy_name(window.ui_locale, value) for value in NETWORK_POLICY_OPTIONS])
    window.network_policy_combo.connect("notify::selected", window.on_network_changed)
    window.network_explanation_label = Gtk.Label(xalign=0)
    window.network_explanation_label.set_wrap(True)
    window.network_explanation_label.add_css_class("dim-label")
    window.allow_brave_browser_switch = Gtk.Switch()
    window.allow_brave_browser_switch.connect("notify::active", window.on_network_changed)
    window.allow_brave_browser_label = Gtk.Label(xalign=0)
    window.allow_brave_browser_label.set_wrap(True)
    window.allow_brave_browser_label.add_css_class("dim-label")
    window.browser_combo = _combo([browser_label(b) for b in BROWSER_OPTIONS])
    window.browser_combo.connect("notify::selected", window.on_browser_changed)
    window.browser_explanation_label = Gtk.Label(xalign=0)
    window.browser_explanation_label.set_wrap(True)
    window.browser_explanation_label.add_css_class("dim-label")

    window.theme_profile_combo = _combo([THEME_PROFILE_LABELS[value] for value in window.theme_profile_values])
    window.theme_profile_combo.connect("notify::selected", window.on_theme_preview_changed)
    window.accent_combo = _combo([ACCENT_LABELS[value] for value in window.accent_values])
    window.accent_combo.connect("notify::selected", window.on_theme_preview_changed)
    window.density_combo = _combo([DENSITY_LABELS[value] for value in window.density_values])
    window.density_combo.connect("notify::selected", window.on_theme_preview_changed)
    window.motion_combo = _combo([MOTION_LABELS[value] for value in window.motion_values])
    window.motion_combo.connect("notify::selected", window.on_theme_preview_changed)

    window.summary_label = Gtk.Label(xalign=0)
    window.summary_label.set_wrap(True)
    window.summary_meter_label = Gtk.Label(xalign=0)
    window.summary_meter_label.set_wrap(True)
    window.summary_meter_label.add_css_class("dim-label")
    window.summary_shift_label = Gtk.Label(xalign=0)
    window.summary_shift_label.set_wrap(True)
    window.summary_shift_label.add_css_class("dim-label")
    window.summary_posture_label = Gtk.Label(xalign=0)
    window.summary_posture_label.set_wrap(True)
    window.vault_passphrase_entry = Gtk.Entry()
    window.vault_passphrase_entry.set_visibility(False)
    window.vault_passphrase_entry.set_placeholder_text("Enter a vault passphrase to check strength")
    window.vault_passphrase_entry.connect("changed", window.on_vault_passphrase_changed)
    window.vault_passphrase_strength = Gtk.Label(xalign=0)
    window.vault_passphrase_strength.set_wrap(True)
    window.vault_passphrase_strength.add_css_class("dim-label")

    window.page_widgets = {
        "language": _page(window, "language", "Language", "Choose the interface language.", [window.language_combo, window.keyboard_combo]),
        "profile": _profile_page(window),
        "network": _network_page(window),
        "browser": _browser_page(window),
        "appearance": _appearance_page(window),
        "summary": _summary_page(window),
    }

    for index, key in enumerate(window.page_order):
        self_page = Gtk.Frame()
        self_page.add_css_class("card")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        inner.set_margin_top(18)
        inner.set_margin_bottom(18)
        inner.set_margin_start(18)
        inner.set_margin_end(18)
        inner.append(window.page_widgets[key])
        self_page.set_child(inner)
        window.stack.add_titled(self_page, f"page-{index}", f"Page {index + 1}")

    root.append(window.stack)

    nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    window.back_button = Gtk.Button()
    window.next_button = Gtk.Button()
    window.skip_button = Gtk.Button()
    window.finish_button = Gtk.Button()
    window.finish_button.add_css_class("suggested-action")
    window.back_button.connect("clicked", window.on_back)
    window.next_button.connect("clicked", window.on_next)
    window.skip_button.connect("clicked", window.on_skip)
    window.finish_button.connect("clicked", window.on_finish)
    nav.append(window.back_button)
    nav.append(window.next_button)
    nav.append(window.skip_button)
    nav.append(window.finish_button)
    root.append(nav)

    window.set_content(root)


def resolve_page_order(_window) -> list[str]:
    return ["language", "profile", "network", "browser", "appearance", "summary"]


def current_page_key(window) -> str:
    return window.page_order[window.page_index]


def _set_dropdown_values(dropdown: Gtk.DropDown, values: list[str], selected_index: int) -> None:
    dropdown.set_model(Gtk.StringList.new(values))
    dropdown.set_selected(selected_index)


def current_language_code(window) -> str:
    selected = window.language_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(window.language_values):
        window.language_combo.set_selected(0)
        return window.language_values[0]
    return window.language_values[selected]


def current_language_name(window) -> str:
    return display_language_name(current_language_code(window))


def current_profile(window) -> str:
    selected = window.profile_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(window.profile_values):
        window.profile_combo.set_selected(0)
        return window.profile_values[0]
    return window.profile_values[selected]


def current_profile_name(window) -> str:
    return window.tr(PROFILE_METADATA[current_profile(window)]["label"])


def current_profile_summary(window) -> str:
    return window.tr(PROFILE_METADATA[current_profile(window)]["summary"])


def current_browser(window) -> str:
    selected = window.browser_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(window.browser_values):
        window.browser_combo.set_selected(0)
        return window.browser_values[0]
    return window.browser_values[selected]


def current_browser_name(window) -> str:
    return window.tr(browser_label(current_browser(window)))


def current_default_browser(window) -> str:
    return browser_to_default_setting(current_browser(window))


def current_network_policy(window) -> str:
    selected = window.network_policy_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(NETWORK_POLICY_OPTIONS):
        window.network_policy_combo.set_selected(0)
        return NETWORK_POLICY_OPTIONS[0]
    return NETWORK_POLICY_OPTIONS[selected]


def current_posture_preview(window) -> dict:
    return describe_posture_preview(current_profile(window), collect_state(window))


def current_theme_profile(window) -> str:
    selected = window.theme_profile_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(window.theme_profile_values):
        window.theme_profile_combo.set_selected(0)
        return window.theme_profile_values[0]
    return window.theme_profile_values[selected]


def current_theme_profile_name(window) -> str:
    return window.tr(THEME_PROFILE_LABELS[current_theme_profile(window)])


def current_accent(window) -> str:
    selected = window.accent_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(window.accent_values):
        window.accent_combo.set_selected(0)
        return window.accent_values[0]
    return window.accent_values[selected]


def current_accent_name(window) -> str:
    return window.tr(ACCENT_LABELS[current_accent(window)])


def current_density(window) -> str:
    selected = window.density_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(window.density_values):
        window.density_combo.set_selected(0)
        return window.density_values[0]
    return window.density_values[selected]


def current_density_name(window) -> str:
    return window.tr(DENSITY_LABELS[current_density(window)])


def current_motion(window) -> str:
    selected = window.motion_combo.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= len(window.motion_values):
        window.motion_combo.set_selected(0)
        return window.motion_values[0]
    return window.motion_values[selected]


def current_motion_name(window) -> str:
    return window.tr(MOTION_LABELS[current_motion(window)])


def apply_translations(window) -> None:
    language_index = window.language_values.index(current_language_code(window))
    profile_index = window.profile_values.index(current_profile(window))
    theme_profile_index = window.theme_profile_values.index(current_theme_profile(window))
    accent_index = window.accent_values.index(current_accent(window))
    density_index = window.density_values.index(current_density(window))
    motion_index = window.motion_values.index(current_motion(window))
    browser_index = window.browser_values.index(current_browser(window))
    network_policy_index = NETWORK_POLICY_OPTIONS.index(current_network_policy(window))
    _set_dropdown_values(window.language_combo, [display_language_name(locale) for locale in window.language_values], language_index)
    _set_dropdown_values(
        window.profile_combo,
        [window.tr(PROFILE_METADATA[profile]["label"]) for profile in window.profile_values],
        profile_index,
    )
    _set_dropdown_values(
        window.browser_combo,
        [window.tr(browser_label(b)) for b in window.browser_values],
        browser_index,
    )
    _set_dropdown_values(
        window.network_policy_combo,
        [display_network_policy_name(window.ui_locale, value) for value in NETWORK_POLICY_OPTIONS],
        network_policy_index,
    )
    _set_dropdown_values(
        window.theme_profile_combo,
        [window.tr(THEME_PROFILE_LABELS[value]) for value in window.theme_profile_values],
        theme_profile_index,
    )
    _set_dropdown_values(
        window.accent_combo,
        [window.tr(ACCENT_LABELS[value]) for value in window.accent_values],
        accent_index,
    )
    _set_dropdown_values(
        window.density_combo,
        [window.tr(DENSITY_LABELS[value]) for value in window.density_values],
        density_index,
    )
    _set_dropdown_values(
        window.motion_combo,
        [window.tr(MOTION_LABELS[value]) for value in window.motion_values],
        motion_index,
    )

    window.set_title(window.tr("NM-OS Setup"))
    window.header_subtitle_label.set_text(window.tr("Review your basic preferences before you start."))
    window.language_title_label.set_text(window.tr("Language & Keyboard"))
    window.language_subtitle_label.set_text(window.tr("Choose the interface language and keyboard layout."))
    window.profile_title_label.set_text(window.tr("Security profile"))
    window.profile_subtitle_label.set_text(
        window.tr("Choose a starting point. You can still fine-tune it later from the desktop.")
    )
    window.network_title_label.set_text(window.tr("Network Policy"))
    window.network_subtitle_label.set_text(window.tr("Choose how NM-OS should treat network access."))
    window.allow_brave_browser_label.set_text(window.tr("Allow Brave Browser when installed"))
    window.browser_title_label.set_text(window.tr("Web Browser"))
    window.browser_subtitle_label.set_text(window.tr("Choose your default web browser."))
    window.appearance_title_label.set_text(window.tr("Appearance"))
    window.appearance_subtitle_label.set_text(
        window.tr("Customize the visual language to your liking.")
    )
    window.summary_title_label.set_text(window.tr("Ready to start"))
    window.summary_subtitle_label.set_text(
        window.tr("These settings will be applied now. You can change them anytime.")
    )
    window.back_button.set_label(window.tr("Back"))
    window.next_button.set_label(window.tr("Next"))
    window.skip_button.set_label(window.tr("Skip setup"))
    window.finish_button.set_label(window.tr("Start using NM-OS"))
    refresh_profile_explanation(window)
    refresh_network_explanation(window)
    refresh_summary(window)


def apply_settings_ui_policy(window) -> None:
    preview_theme(window)


def _select_string(dropdown: Gtk.DropDown, values: list[str], value: str) -> None:
    try:
        dropdown.set_selected(values.index(value))
    except ValueError:
        dropdown.set_selected(0)


def _select_language(window, locale: str) -> None:
    resolved = resolve_supported_locale(locale)
    _select_string(window.language_combo, window.language_values, resolved)


def _select_browser(window, browser: str) -> None:
    normalized = str(browser or "skip").strip().lower()
    if normalized == "none":
        normalized = "skip"
    _select_string(window.browser_combo, window.browser_values, normalized)


def _select_profile(window, profile: str) -> None:
    normalized = str(profile or "balanced").strip().lower()
    _select_string(window.profile_combo, window.profile_values, normalized)


def _select_network_policy(window, network_policy: str) -> None:
    normalized = str(network_policy or "direct").strip().lower()
    _select_string(window.network_policy_combo, NETWORK_POLICY_OPTIONS, normalized)


def current_string(dropdown: Gtk.DropDown, values: list[str] | None = None) -> str:
    model = dropdown.get_model()
    selected = dropdown.get_selected()
    if selected == Gtk.INVALID_LIST_POSITION or selected >= model.get_n_items():
        if model.get_n_items() == 0:
            return ""
        dropdown.set_selected(0)
        selected = 0
    if values is not None and selected < len(values):
        return values[selected]
    return model.get_string(selected)


def restore_state(window) -> None:
    locale = window.state.get("locale", "en_US.UTF-8")
    keyboard = window.state.get("keyboard", "us")
    profile = window.state.get("active_profile", "balanced")
    network_policy = window.state.get("network_policy", "direct")
    browser = window.state.get("default_browser", window.state.get("browser", "firefox-esr"))
    _select_language(window, locale)
    _select_string(window.keyboard_combo, KEYBOARD_OPTIONS, keyboard)
    _select_profile(window, profile)
    _select_network_policy(window, network_policy)
    _select_browser(window, browser)
    window.allow_brave_browser_switch.set_active(bool(window.state.get("allow_brave_browser", False)))
    _select_string(window.theme_profile_combo, window.theme_profile_values, str(window.state.get("ui_theme_profile", "nmos-classic")))
    _select_string(window.accent_combo, window.accent_values, str(window.state.get("ui_accent", "amber")))
    _select_string(window.density_combo, window.density_values, str(window.state.get("ui_density", "comfortable")))
    _select_string(window.motion_combo, window.motion_values, str(window.state.get("ui_motion", "full")))
    window.vault_passphrase_entry.set_text("")
    refresh_passphrase_strength(window)
    refresh_profile_explanation(window)
    refresh_network_explanation(window)
    refresh_browser_explanation(window)
    apply_settings_ui_policy(window)


def preview_theme(window) -> None:
    apply_window_theme(
        window.root_container,
        {
            "ui_theme_profile": current_theme_profile(window),
            "ui_accent": current_accent(window),
            "ui_density": current_density(window),
            "ui_motion": current_motion(window),
        },
    )


def refresh_profile_explanation(window) -> None:
    posture = current_posture_preview(window)
    detail_lines = posture_explanation_lines(window.ui_locale, posture)
    window.profile_summary_label.set_text(window.tr(posture["summary"]))
    window.profile_guidance_label.set_text(window.tr(posture["ideal_for"]))
    window.profile_tradeoff_label.set_text(window.tr(posture["tradeoff"]))
    window.profile_details_label.set_text("\n".join(f"- {line}" for line in detail_lines))


def refresh_browser_explanation(window) -> None:
    desc = browser_description(current_browser(window))
    window.browser_explanation_label.set_text(window.tr(desc))


def refresh_network_explanation(window) -> None:
    network_policy = current_network_policy(window)
    allow_brave = window.allow_brave_browser_switch.get_active()
    details = [
        explain_network_policy(window.ui_locale, network_policy),
        explain_brave_visibility(window.ui_locale, allow_brave, network_policy),
    ]
    window.network_explanation_label.set_text("\n".join(details))


def refresh_summary(window) -> None:
    draft_state = collect_state(window)
    posture = describe_posture_preview(draft_state["active_profile"], draft_state)
    summary_lines = [
        window.tr("Profile: {profile}", profile=current_profile_name(window)),
        window.tr("Language: {language}", language=current_language_name(window)),
        window.tr(
            "Network: {policy}",
            policy=window.tr(display_network_policy_name(window.ui_locale, current_network_policy(window))),
        ),
        window.tr("Default browser: {browser}", browser=current_browser_name(window)),
        window.tr("Theme: {theme}", theme=current_theme_profile_name(window)),
        window.tr("Accent: {accent}", accent=current_accent_name(window)),
    ]
    window.summary_label.set_text("\n".join(summary_lines))
    window.summary_meter_label.set_text("\n".join(posture_meter_lines(window.ui_locale, posture)))
    baseline_scores = compute_posture_scores(window.state)
    shift = compute_posture_score_shift(baseline_scores, posture.get("scores", {}))
    window.summary_shift_label.set_text(format_posture_shift(window.ui_locale, shift))
    window.summary_posture_label.set_text(
        "\n".join(f"- {line}" for line in posture_explanation_lines(window.ui_locale, posture))
    )
    refresh_passphrase_strength(window)


def refresh_passphrase_strength(window) -> None:
    window.vault_passphrase_strength.set_text(passphrase_feedback_text(window.vault_passphrase_entry.get_text()))


def set_status(window, text: str, *, source: str = "event", force: bool = True) -> None:
    if not force and source == "network" and window.status_source not in {"", "network"}:
        return
    window.status_source = source
    window.session_status.set_text(text)


def collect_state(window) -> dict:
    return {
        "locale": current_language_code(window),
        "keyboard": current_string(window.keyboard_combo, KEYBOARD_OPTIONS),
        "active_profile": current_profile(window),
        "network_policy": current_network_policy(window),
        "allow_brave_browser": window.allow_brave_browser_switch.get_active(),
        "browser": current_browser(window),
        "default_browser": current_default_browser(window),
        "ui_theme_profile": current_theme_profile(window),
        "ui_accent": current_accent(window),
        "ui_density": current_density(window),
        "ui_motion": current_motion(window),
    }

def can_finish(window) -> bool:
    return True


def update_navigation(window) -> None:
    if current_page_key(window) == "summary":
        refresh_summary(window)
    window.back_button.set_sensitive(window.page_index > 0)
    window.next_button.set_visible(window.page_index < len(window.page_order) - 1)
    window.next_button.set_sensitive(True)
    window.skip_button.set_visible(window.page_index < len(window.page_order) - 1)
    window.skip_button.set_sensitive(True)
    window.finish_button.set_visible(window.page_index == len(window.page_order) - 1)
    window.finish_button.set_sensitive(can_finish(window))
