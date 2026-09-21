from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_network_bootstrap(repo_root: Path):
    path = repo_root / "config/system-overlay/usr/local/lib/nmos/network_bootstrap.py"
    spec = importlib.util.spec_from_file_location("nmos_network_bootstrap_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tor_firewall_redirects_tcp_and_dns_without_direct_user_egress(repo_root: Path) -> None:
    network_bootstrap = _load_network_bootstrap(repo_root)

    rules = network_bootstrap.render_tor_firewall_rules(123)

    assert "udp dport 53 redirect to :5353" in rules
    assert "tcp flags & (fin | syn | rst | ack) == syn redirect to :9040" in rules
    assert "meta skuid 123 accept" in rules
    assert "chain output" in rules and "policy drop" in rules
    assert "meta skuid 0 tcp dport 53 accept" not in rules


def test_tor_mode_keeps_enforcement_after_bootstrap(repo_root: Path, monkeypatch) -> None:
    network_bootstrap = _load_network_bootstrap(repo_root)
    calls: list[str] = []
    monkeypatch.setattr(network_bootstrap, "load_effective_system_settings", lambda: {"network_policy": "tor"})
    monkeypatch.setattr(network_bootstrap, "ensure_online_bootstrap_services", lambda: calls.append("services"))
    monkeypatch.setattr(network_bootstrap, "clear_ready_marker", lambda: calls.append("clear"))
    monkeypatch.setattr(network_bootstrap, "write_status", lambda **_kwargs: None)
    monkeypatch.setattr(network_bootstrap, "write_tor_firewall_rules", lambda: calls.append("firewall"))
    monkeypatch.setattr(network_bootstrap, "wait_for_tor", lambda: calls.append("wait"))
    monkeypatch.setattr(network_bootstrap, "remove_firewall_gate", lambda: calls.append("removed"))
    monkeypatch.setattr(network_bootstrap, "mark_ready", lambda *_args, **_kwargs: calls.append("ready"))

    network_bootstrap.main()

    assert calls == ["services", "clear", "firewall", "wait", "ready"]


def test_balanced_profile_uses_direct_network_with_browser_privacy_defaults(repo_root: Path) -> None:
    from nmos_common.system_settings import PROFILE_DEFAULTS

    firefox_policy_path = repo_root / "config/system-overlay/usr/lib/firefox-esr/distribution/policies.json"
    chromium_policy_path = repo_root / "config/system-overlay/etc/chromium/policies/managed/nmos-privacy.json"
    firefox_policy = json.loads(firefox_policy_path.read_text(encoding="utf-8"))["policies"]
    chromium_policy = json.loads(chromium_policy_path.read_text(encoding="utf-8"))

    assert PROFILE_DEFAULTS["balanced"]["network_policy"] == "direct"
    assert PROFILE_DEFAULTS["hardened"]["network_policy"] == "tor"
    assert firefox_policy["EnableTrackingProtection"]["Value"] is True
    assert firefox_policy["Preferences"]["network.cookie.cookieBehavior"]["Value"] == 5
    assert chromium_policy["BlockThirdPartyCookies"] is True
    assert chromium_policy["MetricsReportingEnabled"] is False
