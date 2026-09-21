#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from nmos_common.config_helpers import load_feature_flag
from nmos_common.system_settings import load_effective_system_settings

BRAVE_FEATURE_FILE = Path("/etc/nmos/features/brave")


def log_policy_message(message: str) -> None:
    try:
        subprocess.run(
            ["logger", "-t", "nmos-brave-policy", message],
            check=False,
            timeout=2,
        )
    except Exception:
        pass


def deny(message: str) -> int:
    print(message, file=sys.stderr)
    log_policy_message(message)
    return 126


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: brave_policy.py <target-binary> [args...]", file=sys.stderr)
        return 2

    target = Path(sys.argv[1])
    args = [str(target), *sys.argv[2:]]

    if not load_feature_flag(BRAVE_FEATURE_FILE):
        return deny("Brave is not enabled in this NM-OS build.")

    settings = load_effective_system_settings()
    if not bool(settings.get("allow_brave_browser", False)):
        return deny("Brave is disabled in system settings.")
    if str(settings.get("network_policy", "direct")) == "offline":
        return deny("Brave is unavailable while networking is disabled.")

    if not target.exists():
        print(f"Brave binary not found: {target}", file=sys.stderr)
        return 127
    if target.is_symlink():
        return deny("Brave binary path is a symlink - execution blocked.")

    os.execv(str(target), args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
