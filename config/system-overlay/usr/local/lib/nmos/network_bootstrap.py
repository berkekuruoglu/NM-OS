#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from nmos_common.network_status import parse_bootstrap_status
from nmos_common.platform_adapter import get_runtime_dir, get_tor_user
from nmos_common.runtime_state import write_runtime_json, write_runtime_text
from nmos_common.system_settings import load_effective_system_settings

READY_DIR = get_runtime_dir()
READY_FILE = READY_DIR / "network-ready"
STATUS_FILE = READY_DIR / "network-status.json"
TOR_CONTROL_PORT = 9051
TOR_TRANSPARENT_PORT = 9040
TOR_DNS_PORT = 5353
BOOTSTRAP_TIMEOUT_SECONDS = 300
SERVICE_START_TIMEOUT_SECONDS = 20


def log(message: str) -> None:
    print(message, flush=True)
    tty = Path("/dev/ttyS0")
    if tty.exists():
        try:
            tty.write_text(message + "\n", encoding="utf-8")
        except OSError:
            pass


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def ensure_nft_available() -> None:
    if shutil.which("nft") is None:
        raise RuntimeError("nft binary not found - cannot enforce network policy")


def now_utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_status(
    *,
    ready: bool,
    progress: int,
    summary: str,
    phase: str,
    last_error: str = "",
) -> None:
    READY_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_json(
        STATUS_FILE,
        {
            "ready": ready,
            "progress": progress,
            "phase": phase,
            "summary": summary,
            "last_error": last_error,
            "updated_at": now_utc_timestamp(),
        },
        mode=0o644,
    )


def render_tor_firewall_rules(tor_uid: int) -> str:
    return f"""
table inet nmosfilter {{
  chain redirect_output {{
    type nat hook output priority dstnat; policy accept;
    meta skuid {tor_uid} return
    oifname "lo" return
    udp dport 53 redirect to :{TOR_DNS_PORT}
    tcp flags & (fin | syn | rst | ack) == syn redirect to :{TOR_TRANSPARENT_PORT}
  }}
  chain input {{
    type filter hook input priority 0; policy drop;
    iifname "lo" accept
    ct state established,related accept
  }}
  chain output {{
    type filter hook output priority 0; policy drop;
    oifname "lo" accept
    ct state established,related accept
    meta skuid 0 udp dport {{ 67, 68, 123 }} accept
    meta skuid {tor_uid} udp dport {{ 53, 123 }} accept
    meta skuid {tor_uid} tcp dport 53 accept
    meta skuid {tor_uid} accept
  }}
}}
"""


def write_tor_firewall_rules() -> None:
    ensure_nft_available()
    import pwd

    getpwnam = getattr(pwd, "getpwnam", None)
    if getpwnam is None:
        raise RuntimeError("pwd.getpwnam is unavailable on this platform")
    tor_user = get_tor_user()
    tor_uid = int(getpwnam(tor_user).pw_uid)
    subprocess.run(["nft", "delete", "table", "inet", "nmosfilter"], check=False)
    rules = render_tor_firewall_rules(tor_uid)
    subprocess.run(["nft", "-f", "-"], input=rules, text=True, check=True)


def write_offline_firewall_rules() -> None:
    ensure_nft_available()
    subprocess.run(["nft", "delete", "table", "inet", "nmosfilter"], check=False)
    rules = """
table inet nmosfilter {
  chain input {
    type filter hook input priority 0; policy drop;
    iifname "lo" accept
    ct state established,related accept
  }
  chain output {
    type filter hook output priority 0; policy drop;
    oifname "lo" accept
    ct state established,related accept
  }
}
"""
    subprocess.run(["nft", "-f", "-"], input=rules, text=True, check=True)


def nft_table_exists() -> bool:
    ensure_nft_available()
    return (
        subprocess.run(
            ["nft", "list", "table", "inet", "nmosfilter"],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def remove_firewall_gate() -> None:
    if not nft_table_exists():
        return
    subprocess.run(
        ["nft", "delete", "table", "inet", "nmosfilter"],
        check=False,
        capture_output=True,
        text=True,
    )
    if nft_table_exists():
        raise RuntimeError("failed to remove temporary network bootstrap firewall table")


def ensure_online_bootstrap_services() -> None:
    for unit in ("NetworkManager.service", "tor.service", "tor@default.service"):
        try:
            subprocess.run(
                ["systemctl", "start", unit],
                check=False,
                capture_output=True,
                text=True,
                timeout=SERVICE_START_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            log(f"NMOS_NETWORK_WARN timeout starting {unit}")


def wait_for_tor() -> None:
    from stem.control import Controller

    deadline = time.monotonic() + BOOTSTRAP_TIMEOUT_SECONDS
    while True:
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
                controller.authenticate()
                status = controller.get_info("status/bootstrap-phase", "")
        except Exception as exc:
            write_status(
                ready=False,
                progress=0,
                summary="Waiting for Tor control",
                phase="bootstrap",
                last_error=str(exc),
            )
            time.sleep(2)
            if time.monotonic() >= deadline:
                raise RuntimeError("timed out waiting for Tor control port") from exc
            continue

        progress, summary = parse_bootstrap_status(status)
        write_status(ready=progress >= 100, progress=progress, summary=summary, phase="bootstrap")
        if progress >= 100:
            return

        if time.monotonic() >= deadline:
            raise RuntimeError("timed out waiting for Tor bootstrap")
        time.sleep(2)


def mark_ready(summary: str, phase: str = "ready") -> None:
    READY_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_text(READY_FILE, "ready\n", mode=0o644)
    write_status(ready=True, progress=100, summary=summary, phase=phase)
    log(f"NMOS_NETWORK_READY phase={phase}")
    run("systemctl", "start", "nmos-network-ready.target")


def clear_ready_marker() -> None:
    READY_FILE.unlink(missing_ok=True)


def apply_offline_mode() -> None:
    clear_ready_marker()
    write_offline_firewall_rules()
    write_status(
        ready=False,
        progress=0,
        summary="Network is disabled by current settings.",
        phase="disabled",
        last_error="",
    )
    log("NMOS_NETWORK_DISABLED")


def apply_direct_mode() -> None:
    remove_firewall_gate()
    mark_ready("Direct network access is enabled by system settings.", phase="open")


def main() -> None:
    settings = load_effective_system_settings()
    policy = str(settings.get("network_policy", "direct"))
    READY_DIR.mkdir(parents=True, exist_ok=True)
    if policy == "offline":
        apply_offline_mode()
        return
    if policy == "direct":
        apply_direct_mode()
        return
    ensure_online_bootstrap_services()
    clear_ready_marker()
    write_status(ready=False, progress=0, summary="Preparing network policy", phase="policy")
    try:
        write_tor_firewall_rules()
        write_status(ready=False, progress=0, summary="Waiting for Tor bootstrap", phase="bootstrap")
        wait_for_tor()
        mark_ready("Tor is ready; TCP and DNS traffic are routed through Tor.", phase="tor-routed")
    except Exception as exc:
        write_status(
            ready=False,
            progress=0,
            summary="Network bootstrap failed",
            phase="failed",
            last_error=str(exc),
        )
        log(f"NMOS_NETWORK_FAILED {exc}")
        raise


if __name__ == "__main__":
    main()
