from __future__ import annotations

import json

from nmos_common.platform_adapter import get_runtime_dir
from nmos_common.runtime_state import ensure_runtime_state_path_safe, read_runtime_text, write_runtime_text

STATE_FILE = get_runtime_dir() / "greeter-state.json"
STATE_FILE_MODE = 0o660


def normalize_onboarding_page_index(value: object, page_count: int) -> int:
    if page_count <= 0:
        return 0
    if not isinstance(value, (bool, int, float, str, bytes, bytearray)):
        value = 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    return max(0, min(page_count - 1, parsed))


def load_onboarding_page_index(state: object, page_count: int) -> int:
    raw_state = state if isinstance(state, dict) else {}
    return normalize_onboarding_page_index(raw_state.get("onboarding_page_index", 0), page_count)


def next_onboarding_page_index(current: object, page_count: int) -> int:
    current_index = normalize_onboarding_page_index(current, page_count)
    if page_count <= 0:
        return 0
    return min(page_count - 1, current_index + 1)


def previous_onboarding_page_index(current: object, page_count: int) -> int:
    current_index = normalize_onboarding_page_index(current, page_count)
    return max(0, current_index - 1)


def skip_to_summary_page_index(page_count: int) -> int:
    if page_count <= 0:
        return 0
    return page_count - 1


def ensure_state_path_safe() -> bool:
    try:
        ensure_runtime_state_path_safe(STATE_FILE)
    except OSError:
        return False
    return True


def write_state_payload(payload: str) -> None:
    write_runtime_text(STATE_FILE, payload, mode=STATE_FILE_MODE)


def load_state() -> dict:
    try:
        raw = read_runtime_text(STATE_FILE).strip()
    except OSError:
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_state(state: dict) -> None:
    write_state_payload(json.dumps(state, indent=2))


def clear_state() -> None:
    write_state_payload("{}\n")
