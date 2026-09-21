from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nmos_common.config_helpers import read_assignment_file
from nmos_common.platform_adapter import get_runtime_dir, get_state_dir
from nmos_common.runtime_state import read_runtime_json, write_runtime_json

SUPPORTED_CHANNELS = ("stable", "beta", "nightly")
SUPPORTED_STATES = {
    "idle",
    "checking",
    "available",
    "downloading",
    "verifying",
    "staged",
    "switching_on_reboot",
    "awaiting_health_ack",
    "healthy",
    "rollback_pending",
    "rolled_back",
    "failed",
}

RUNTIME_DIR = get_runtime_dir()
STATE_DIR = get_state_dir() / "update-engine"
RUNTIME_STATUS_FILE = RUNTIME_DIR / "update-engine-status.json"
RUNTIME_HEALTH_FILE = RUNTIME_DIR / "update-engine-health.json"
PERSISTENT_HISTORY_FILE = STATE_DIR / "history.json"
PERSISTENT_SLOT_FILE = STATE_DIR / "slot-state.json"
PERSISTENT_CATALOG_FILE = STATE_DIR / "catalog-cache.json"
PERSISTENT_MANIFEST_FILE = STATE_DIR / "manifest-cache.json"
PERSISTENT_MANIFEST_SIG_FILE = STATE_DIR / "manifest-cache.sig"
PERSISTENT_ARTIFACT_DIR = STATE_DIR / "artifacts"
BOOT_INTENT_FILE = STATE_DIR / "boot-intent.json"
PERSISTENT_HEALTH_FILE = STATE_DIR / "health-state.json"
SHARED_METADATA_DIR = Path("/usr/share/nmos")
SHARED_UPDATE_CATALOG_FILE = SHARED_METADATA_DIR / "update-catalog.json"
SHARED_RELEASE_MANIFEST_FILE = SHARED_METADATA_DIR / "release-manifest.json"
SHARED_SIGNING_KEYRING = SHARED_METADATA_DIR / "update-signing.gpg"
AB_LAYOUT_FILE = Path("/etc/nmos/ab-layout.env")
DEFAULT_FEED_FILE = Path(__file__).resolve().parents[3] / "config" / "update-catalog.json"
DEFAULT_DIST_FEED_FILE = Path(__file__).resolve().parents[3] / "dist" / "update-catalog.json"
DEFAULT_DIST_MANIFEST_FILE = Path(__file__).resolve().parents[3] / "dist" / "release-manifest.json"
DEFAULT_DIST_SIGNATURE_FILE = Path(__file__).resolve().parents[3] / "dist" / "release-manifest.json.sig"


class UpdateEngineError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


@dataclass
class SlotState:
    active_slot: str = "a"
    inactive_slot: str = "b"
    pending_slot: str = ""
    previous_slot: str = ""
    boot_attempts_remaining: int = 0
    installed_version: str = "unknown"
    staged_version: str = ""
    accepted_release_sequence: int = 0
    staged_release_sequence: int = 0
    last_boot_result: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return {
            "active_slot": self.active_slot,
            "inactive_slot": self.inactive_slot,
            "pending_slot": self.pending_slot,
            "previous_slot": self.previous_slot,
            "boot_attempts_remaining": int(self.boot_attempts_remaining),
            "installed_version": self.installed_version,
            "staged_version": self.staged_version,
            "accepted_release_sequence": int(self.accepted_release_sequence),
            "staged_release_sequence": int(self.staged_release_sequence),
            "last_boot_result": self.last_boot_result,
        }


def _timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())


def _normalize_state(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in SUPPORTED_STATES else "idle"


def _normalize_channel(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in SUPPORTED_CHANNELS else "stable"


def _safe_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (bool, int, float, str, bytes, bytearray)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_status() -> dict[str, object]:
    installed = _infer_installed_version()
    return {
        "state": "idle",
        "channel": _normalize_channel(_infer_channel(installed)),
        "installed_version": installed,
        "available_version": "",
        "available_release_sequence": 0,
        "staged_version": "",
        "active_slot": "a",
        "inactive_slot": "b",
        "pending_slot": "",
        "previous_slot": "",
        "last_checked_at": "never",
        "last_action": "No update action yet.",
        "last_error": "",
        "guardrail_update": "Update blocked: release manifest metadata is unavailable.",
        "guardrail_rollback": "Rollback blocked: current release policy does not declare rollback support.",
        "manifest_signature_verified": False,
        "health_deadline_epoch": 0,
        "slot_image_path": "",
        "recovery_image_path": "",
    }


def _load_status() -> dict[str, object]:
    status = read_runtime_json(RUNTIME_STATUS_FILE, default=_default_status())
    merged = dict(_default_status())
    if isinstance(status, dict):
        merged.update(status)
    merged["state"] = _normalize_state(merged.get("state"))
    merged["channel"] = _normalize_channel(merged.get("channel"))
    return merged


def _save_status(status: dict[str, object]) -> dict[str, object]:
    merged = dict(_default_status())
    merged.update(status)
    merged["state"] = _normalize_state(merged.get("state"))
    merged["channel"] = _normalize_channel(merged.get("channel"))
    write_runtime_json(RUNTIME_STATUS_FILE, merged, mode=0o664)
    return merged


def _load_history() -> list[dict[str, object]]:
    payload = read_runtime_json(PERSISTENT_HISTORY_FILE, default={"entries": []})
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return []
    return [item for item in entries if isinstance(item, dict)]


def _save_history(history: list[dict[str, object]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_json(PERSISTENT_HISTORY_FILE, {"entries": history[-100:]}, mode=0o660)


def _append_history(action: str, details: dict[str, object]) -> None:
    history = _load_history()
    history.append(
        {
            "at": _timestamp(),
            "action": action,
            "details": dict(details),
        }
    )
    _save_history(history)


def _load_slot_state() -> SlotState:
    payload = read_runtime_json(PERSISTENT_SLOT_FILE, default={})
    data = payload if isinstance(payload, dict) else {}
    active = str(data.get("active_slot", "a")).strip().lower()
    inactive = str(data.get("inactive_slot", "b")).strip().lower()
    if active not in {"a", "b"}:
        active = "a"
    if inactive not in {"a", "b"} or inactive == active:
        inactive = "b" if active == "a" else "a"
    return SlotState(
        active_slot=active,
        inactive_slot=inactive,
        pending_slot=str(data.get("pending_slot", "")).strip().lower(),
        previous_slot=str(data.get("previous_slot", "")).strip().lower(),
        boot_attempts_remaining=max(0, _safe_int(data.get("boot_attempts_remaining"), 0)),
        installed_version=str(data.get("installed_version", _infer_installed_version())).strip() or "unknown",
        staged_version=str(data.get("staged_version", "")).strip(),
        accepted_release_sequence=max(
            0,
            _safe_int(data.get("accepted_release_sequence"), _infer_installed_release_sequence()),
        ),
        staged_release_sequence=max(0, _safe_int(data.get("staged_release_sequence"), 0)),
        last_boot_result=str(data.get("last_boot_result", "unknown")).strip() or "unknown",
    )


def _save_slot_state(slot: SlotState) -> SlotState:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_json(PERSISTENT_SLOT_FILE, slot.to_dict(), mode=0o660)
    return slot


def _load_boot_intent() -> dict[str, object]:
    payload = read_runtime_json(BOOT_INTENT_FILE, default={})
    return payload if isinstance(payload, dict) else {}


def _clear_boot_intent() -> None:
    try:
        BOOT_INTENT_FILE.unlink()
    except OSError:
        pass


def _load_persistent_health() -> dict[str, object]:
    payload = read_runtime_json(PERSISTENT_HEALTH_FILE, default={})
    return payload if isinstance(payload, dict) else {}


def _save_persistent_health(payload: dict[str, object]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_json(PERSISTENT_HEALTH_FILE, payload, mode=0o660)


def _clear_persistent_health() -> None:
    try:
        PERSISTENT_HEALTH_FILE.unlink()
    except OSError:
        pass


def _load_ab_layout() -> dict[str, str]:
    defaults = {
        "NMOS_SLOT_A_LABEL": "NMOS_ROOT_A",
        "NMOS_SLOT_B_LABEL": "NMOS_ROOT_B",
        "NMOS_STATE_LABEL": "NMOS_STATE",
        "NMOS_EFI_LABEL": "NMOS_EFI",
    }
    try:
        values = read_assignment_file(AB_LAYOUT_FILE)
    except OSError:
        values = {}
    merged = dict(defaults)
    for key, default in defaults.items():
        value = str(values.get(key, "")).strip()
        merged[key] = value or default
    return merged


def _slot_label(slot_name: str) -> str:
    layout = _load_ab_layout()
    return layout["NMOS_SLOT_A_LABEL"] if slot_name == "a" else layout["NMOS_SLOT_B_LABEL"]


def _slot_device(slot_name: str) -> Path:
    return Path("/dev/disk/by-label") / _slot_label(slot_name)


def _safe_extract_tarball(archive_path: Path, destination: Path) -> None:
    resolved_destination = destination.resolve()
    directory_modes: list[tuple[Path, int]] = []
    with tarfile.open(archive_path, mode="r:*") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise UpdateEngineError(
                    "artifact_extract_failed",
                    f"refusing to extract archive link: {member.name}",
                )
            if not member.isdir() and not member.isreg():
                raise UpdateEngineError(
                    "artifact_extract_failed",
                    f"refusing to extract special archive member: {member.name}",
                )
            target = destination / member.name
            try:
                resolved_target = target.resolve()
            except OSError as exc:
                raise UpdateEngineError("artifact_extract_failed", f"unable to resolve staged path: {exc}") from exc
            if resolved_destination not in resolved_target.parents and resolved_target != resolved_destination:
                raise UpdateEngineError("artifact_extract_failed", f"refusing to extract path outside slot root: {member.name}")
            if member.isdir():
                resolved_target.mkdir(parents=True, exist_ok=True)
                directory_modes.append((resolved_target, member.mode & 0o777))
                continue
            resolved_target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise UpdateEngineError("artifact_extract_failed", f"unable to read archive member: {member.name}")
            with source, resolved_target.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            os.chmod(resolved_target, member.mode & 0o777)
    for path, mode in sorted(directory_modes, key=lambda item: len(item[0].parts), reverse=True):
        os.chmod(path, mode)


def _run_command(command: list[str], *, timeout: int = 30) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if completed.returncode == 0:
        return True, (completed.stdout or "").strip()
    detail = (completed.stderr or completed.stdout or f"exit={completed.returncode}").strip()
    return False, detail


def _render_slot_fstab(slot_name: str) -> str:
    layout = _load_ab_layout()
    root_label = layout["NMOS_SLOT_A_LABEL"] if slot_name == "a" else layout["NMOS_SLOT_B_LABEL"]
    inactive_slot = "b" if slot_name == "a" else "a"
    inactive_label = layout["NMOS_SLOT_A_LABEL"] if inactive_slot == "a" else layout["NMOS_SLOT_B_LABEL"]
    return (
        f"LABEL={root_label} / ext4 defaults 0 1\n"
        f"LABEL={layout['NMOS_STATE_LABEL']} /var/lib/nmos ext4 defaults 0 2\n"
        f"LABEL={layout['NMOS_EFI_LABEL']} /boot/efi vfat umask=0077 0 1\n"
        f"LABEL={inactive_label} /var/lib/nmos/slots/{inactive_slot} ext4 defaults,nofail 0 2\n"
    )


def _stage_slot_overlay(source: Path, target_slot: str, version: str) -> tuple[Path, str]:
    slot_device = _slot_device(target_slot)
    if not slot_device.exists():
        target = _write_slot_artifact(source, target_slot, version)
        return target, "inactive slot device not found; staged artifact in NM-OS state directory"
    if shutil.which("mount") is None or shutil.which("umount") is None:
        target = _write_slot_artifact(source, target_slot, version)
        return target, "mount tools unavailable; staged artifact in NM-OS state directory"
    mount_dir = STATE_DIR / f"mount-slot-{target_slot}"
    mount_dir.mkdir(parents=True, exist_ok=True)
    mounted = False
    try:
        ok, detail = _run_command(["mount", str(slot_device), str(mount_dir)], timeout=30)
        if not ok:
            target = _write_slot_artifact(source, target_slot, version)
            return target, f"mount failed ({detail}); staged artifact in NM-OS state directory"
        mounted = True
        _safe_extract_tarball(source, mount_dir)
        fstab_path = mount_dir / "etc" / "fstab"
        fstab_path.parent.mkdir(parents=True, exist_ok=True)
        fstab_path.write_text(_render_slot_fstab(target_slot), encoding="utf-8")
        marker_path = mount_dir / "etc" / "nmos-staged-release"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(f"version={version}\nslot={target_slot}\nstaged_at={_timestamp()}\n", encoding="utf-8")
        return slot_device, f"overlay extracted into inactive slot device {slot_device}"
    except (OSError, tarfile.TarError) as exc:
        target = _write_slot_artifact(source, target_slot, version)
        return target, f"slot extraction failed ({exc}); staged artifact in NM-OS state directory"
    finally:
        if mounted:
            _run_command(["umount", str(mount_dir)], timeout=30)
        try:
            os.rmdir(mount_dir)
        except OSError:
            pass


def _infer_installed_version() -> str:
    for path in (SHARED_RELEASE_MANIFEST_FILE, DEFAULT_DIST_MANIFEST_FILE):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            version = str(payload.get("version", "")).strip()
            if version:
                return version
    version_file = Path(__file__).resolve().parents[3] / "config" / "version"
    if version_file.exists():
        try:
            text = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        if text:
            return text
    return "unknown"


def _infer_installed_release_sequence() -> int:
    for path in (SHARED_RELEASE_MANIFEST_FILE, DEFAULT_DIST_MANIFEST_FILE):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            sequence = _safe_int(payload.get("release_sequence"), 0)
            if sequence > 0:
                return sequence
    return 0


def _infer_channel(version: str) -> str:
    lowered = str(version).lower()
    if "alpha" in lowered or "nightly" in lowered:
        return "nightly"
    if "beta" in lowered or "rc" in lowered:
        return "beta"
    return "stable"


def _parse_version(version: str) -> tuple[tuple[int, int, int], str]:
    text = str(version).strip()
    main, _, suffix = text.partition("-")
    parts = main.split(".")
    nums = []
    for raw in parts[:3]:
        try:
            nums.append(int(raw))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2]), suffix


def _version_less_than(lhs: str, rhs: str) -> bool:
    left_num, left_suffix = _parse_version(lhs)
    right_num, right_suffix = _parse_version(rhs)
    if left_num != right_num:
        return left_num < right_num
    return _compare_prerelease(left_suffix, right_suffix) < 0


def _compare_prerelease(lhs: str, rhs: str) -> int:
    if lhs == rhs:
        return 0
    if not lhs:
        return 1
    if not rhs:
        return -1
    left_parts = lhs.split(".")
    right_parts = rhs.split(".")
    for left, right in zip(left_parts, right_parts, strict=False):
        if left == right:
            continue
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left) < int(right) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left < right else 1
    if len(left_parts) == len(right_parts):
        return 0
    return -1 if len(left_parts) < len(right_parts) else 1


def _read_catalog_payload() -> dict[str, object]:
    for path in (SHARED_UPDATE_CATALOG_FILE, DEFAULT_DIST_FEED_FILE, DEFAULT_FEED_FILE):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _normalize_catalog(payload: object) -> dict[str, dict[str, str]]:
    raw = payload if isinstance(payload, dict) else {}
    channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
    if not isinstance(channels, dict):
        return {}
    catalog: dict[str, dict[str, str]] = {}
    for channel in SUPPORTED_CHANNELS:
        item = channels.get(channel, {})
        if not isinstance(item, dict):
            continue
        catalog[channel] = {
            "version": str(item.get("version", "")).strip(),
            "notes": str(item.get("notes", "")).strip(),
            "manifest_url": str(item.get("manifest_url", "")).strip(),
            "manifest_sha256": str(item.get("manifest_sha256", "")).strip(),
            "signature_url": str(item.get("signature_url", "")).strip(),
            "channel": channel,
        }
    return catalog


def _save_catalog_cache(catalog: dict[str, dict[str, str]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_json(PERSISTENT_CATALOG_FILE, {"channels": catalog}, mode=0o660)


def _load_catalog() -> dict[str, dict[str, str]]:
    live = _normalize_catalog(_read_catalog_payload())
    if live:
        _save_catalog_cache(live)
        return live
    cached = read_runtime_json(PERSISTENT_CATALOG_FILE, default={})
    normalized = _normalize_catalog(cached)
    if normalized:
        return normalized
    return {
        channel: {
            "version": "",
            "notes": "No catalog published.",
            "manifest_url": "",
            "manifest_sha256": "",
            "signature_url": "",
            "channel": channel,
        }
        for channel in SUPPORTED_CHANNELS
    }


def _load_cached_manifest() -> dict[str, object]:
    data = read_runtime_json(PERSISTENT_MANIFEST_FILE, default={})
    return data if isinstance(data, dict) else {}


def _save_cached_manifest(manifest: dict[str, object]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_json(PERSISTENT_MANIFEST_FILE, manifest, mode=0o660)


def _resolve_manifest_source(url_text: str) -> Path:
    url = str(url_text).strip()
    if not url:
        raise UpdateEngineError("manifest_missing_url", "channel feed does not provide a manifest URL")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"", "file"}:
        if parsed.scheme == "file":
            path = Path(urllib.request.url2pathname(parsed.path))
        else:
            path = Path(url)
        if not path.exists():
            raise UpdateEngineError("manifest_missing", f"manifest path is missing: {path}")
        return path
    if parsed.scheme not in {"http", "https"}:
        raise UpdateEngineError("manifest_scheme_unsupported", f"unsupported manifest URL scheme: {parsed.scheme}")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = STATE_DIR / "downloaded-manifest.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            target.write_bytes(response.read())
    except Exception as exc:
        raise UpdateEngineError("manifest_download_failed", f"failed to download manifest: {exc}") from exc
    return target


def _resolve_signature_source(url_text: str, manifest_source: Path) -> Path:
    url = str(url_text).strip()
    if not url:
        raise UpdateEngineError("signature_missing_url", "channel feed does not provide a detached signature URL")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"", "file"}:
        if parsed.scheme == "file":
            path = Path(urllib.request.url2pathname(parsed.path))
        else:
            path = Path(url)
        if not path.exists():
            raise UpdateEngineError("signature_missing", f"manifest signature is missing: {path}")
        return path
    if parsed.scheme not in {"http", "https"}:
        raise UpdateEngineError("signature_scheme_unsupported", f"unsupported signature URL scheme: {parsed.scheme}")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = PERSISTENT_MANIFEST_SIG_FILE
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            target.write_bytes(response.read())
    except Exception as exc:
        raise UpdateEngineError("signature_download_failed", f"failed to download detached signature: {exc}") from exc
    if target.stat().st_size == 0:
        raise UpdateEngineError("signature_empty", "downloaded detached signature is empty")
    if target.samefile(manifest_source):
        raise UpdateEngineError("signature_invalid", "detached signature path collides with manifest path")
    return target


def _verify_sha256(path: Path, expected: str) -> None:
    expected_text = str(expected).strip().lower()
    if not expected_text:
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest().lower()
    if digest != expected_text:
        raise UpdateEngineError(
            "manifest_checksum_mismatch",
            f"manifest checksum mismatch: expected {expected_text} got {digest}",
        )


def _verify_detached_signature(manifest_path: Path, signature_path: Path) -> None:
    keyring_paths = [SHARED_SIGNING_KEYRING, Path(__file__).resolve().parents[3] / "config" / "update-signing.gpg"]
    keyring = next((path for path in keyring_paths if path.exists()), None)
    if keyring is None:
        raise UpdateEngineError("signature_keyring_missing", "no update-signing keyring found")
    if shutil.which("gpgv") is None:
        raise UpdateEngineError("signature_verifier_missing", "gpgv is required to verify detached signatures")
    try:
        completed = subprocess.run(
            ["gpgv", "--keyring", str(keyring), str(signature_path), str(manifest_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateEngineError("signature_verification_failed", f"gpgv failed: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or f"exit={completed.returncode}").strip()
        raise UpdateEngineError("signature_verification_failed", f"detached signature verification failed: {detail}")


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise UpdateEngineError("manifest_parse_failed", f"unable to parse release manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise UpdateEngineError("manifest_invalid", "release manifest must be a JSON object")
    return payload


def _require_manifest_fields(manifest: dict[str, object]) -> dict[str, Any]:
    errors: list[str] = []
    version = str(manifest.get("version", "")).strip()
    if not version:
        errors.append("missing version")
    release_sequence = _safe_int(manifest.get("release_sequence"), 0)
    if release_sequence <= 0:
        errors.append("missing or invalid release_sequence")
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        errors.append("missing artifacts object")
        artifacts = {}
    slot_image = artifacts.get("slot_image", {})
    if not isinstance(slot_image, dict):
        errors.append("missing artifacts.slot_image object")
        slot_image = {}
    recovery_image = artifacts.get("recovery_image", {})
    if not isinstance(recovery_image, dict):
        errors.append("missing artifacts.recovery_image object")
        recovery_image = {}
    for key in ("name", "sha256", "url"):
        if not str(slot_image.get(key, "")).strip():
            errors.append(f"missing artifacts.slot_image.{key}")
    for key in ("name", "sha256", "url"):
        if not str(recovery_image.get(key, "")).strip():
            errors.append(f"missing artifacts.recovery_image.{key}")
    upgrade_policy = manifest.get("upgrade_policy", {})
    if not isinstance(upgrade_policy, dict):
        errors.append("missing upgrade_policy object")
        upgrade_policy = {}
    if not str(upgrade_policy.get("minimum_source_version", "")).strip():
        errors.append("missing upgrade_policy.minimum_source_version")
    supports_rollback = str(upgrade_policy.get("supports_rollback", "")).strip().lower()
    if supports_rollback not in {"1", "true", "yes", "on"}:
        errors.append("upgrade_policy.supports_rollback must be true")
    migration = manifest.get("migration", {})
    migration_bundle_id = ""
    if isinstance(migration, dict):
        migration_bundle_id = str(migration.get("bundle_id", "")).strip()
    if not migration_bundle_id:
        migration_bundle_id = str(manifest.get("migration_bundle_id", "")).strip()
    if not migration_bundle_id:
        errors.append("missing migration bundle identifier")
    if errors:
        raise UpdateEngineError("manifest_required_fields_missing", "; ".join(errors))
    return {
        "version": version,
        "release_sequence": release_sequence,
        "slot_image": slot_image,
        "recovery_image": recovery_image,
        "upgrade_policy": upgrade_policy,
        "migration_bundle_id": migration_bundle_id,
    }


def _apply_version_policy(installed_version: str, minimum_source_version: str) -> None:
    if not installed_version or installed_version == "unknown":
        return
    if _version_less_than(installed_version, minimum_source_version):
        raise UpdateEngineError(
            "version_policy_blocked",
            f"installed version {installed_version} is below required source {minimum_source_version}",
        )


def _enforce_anti_rollback(
    *,
    installed_version: str,
    available_version: str,
    accepted_release_sequence: int,
    available_release_sequence: int,
) -> None:
    if installed_version and installed_version != "unknown" and _version_less_than(available_version, installed_version):
        raise UpdateEngineError(
            "release_downgrade_blocked",
            f"refusing signed downgrade from {installed_version} to {available_version}",
        )
    if accepted_release_sequence > 0 and available_release_sequence < accepted_release_sequence:
        raise UpdateEngineError(
            "release_replay_blocked",
            "refusing release metadata older than the highest accepted release sequence",
        )


def _resolve_artifact_source(url_text: str) -> Path:
    url = str(url_text).strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"", "file"}:
        path = Path(urllib.request.url2pathname(parsed.path if parsed.scheme == "file" else url))
        if not path.exists():
            raise UpdateEngineError("artifact_missing", f"artifact path is missing: {path}")
        return path
    if parsed.scheme not in {"http", "https"}:
        raise UpdateEngineError("artifact_scheme_unsupported", f"unsupported artifact URL scheme: {parsed.scheme}")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PERSISTENT_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    target = PERSISTENT_ARTIFACT_DIR / "downloaded-slot-image.bin"
    try:
        with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except Exception as exc:
        raise UpdateEngineError("artifact_download_failed", f"failed to download slot image: {exc}") from exc
    return target


def _verify_artifact_sha256(path: Path, expected: str, label: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest().lower()
    normalized_expected = str(expected).strip().lower()
    if normalized_expected != digest:
        raise UpdateEngineError(
            "artifact_checksum_mismatch",
            f"{label} checksum mismatch: expected {normalized_expected} got {digest}",
        )


def _write_slot_artifact(source: Path, target_slot: str, version: str) -> Path:
    PERSISTENT_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    safe_version = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in version) or "unknown"
    target = PERSISTENT_ARTIFACT_DIR / f"slot-{target_slot}-{safe_version}.img"
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    return target


def _sync_grub_state(slot: SlotState, *, boot_ok: bool) -> str:
    if shutil.which("grub-editenv") is None:
        return "grub-editenv not available; boot intent persisted in NM-OS state"
    grubenv_path = Path("/boot/grub/grubenv")
    create_ok, create_detail = _run_command(["grub-editenv", str(grubenv_path), "create"], timeout=15)
    if not create_ok and "File exists" not in create_detail:
        return f"grub-editenv create failed: {create_detail}"
    ok, detail = _run_command(
        [
            "grub-editenv",
            str(grubenv_path),
            "set",
            f"nmos_active_slot={slot.active_slot}",
            f"nmos_pending_slot={slot.pending_slot}",
            f"nmos_previous_slot={slot.previous_slot}",
            f"nmos_boot_attempts_remaining={slot.boot_attempts_remaining}",
            f"nmos_boot_ok={1 if boot_ok else 0}",
        ],
        timeout=15,
    )
    if not ok:
        return f"grub-editenv failed: {detail}"
    return "grub slot state updated"


def _persist_boot_intent(slot: SlotState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_runtime_json(
        BOOT_INTENT_FILE,
        {
            "pending_slot": slot.pending_slot,
            "previous_slot": slot.previous_slot,
            "boot_attempts_remaining": slot.boot_attempts_remaining,
            "active_slot": slot.active_slot,
            "staged_version": slot.staged_version,
            "written_at": _timestamp(),
        },
        mode=0o660,
    )


def _sync_status_from_persistent(status: dict[str, object], slot: SlotState) -> dict[str, object]:
    boot_intent = _load_boot_intent()
    persistent_health = _load_persistent_health()
    status["active_slot"] = slot.active_slot
    status["inactive_slot"] = slot.inactive_slot
    status["pending_slot"] = slot.pending_slot
    status["previous_slot"] = slot.previous_slot
    status["installed_version"] = slot.installed_version or _infer_installed_version()
    status["staged_version"] = slot.staged_version
    if status.get("state") == "idle" and slot.pending_slot and boot_intent:
        status["state"] = "switching_on_reboot"
        status["last_action"] = f"Pending slot {slot.pending_slot} will be attempted on next boot."
    if persistent_health:
        health_state = _normalize_state(persistent_health.get("state"))
        if health_state in {"awaiting_health_ack", "rolled_back"}:
            status["state"] = health_state
            status["health_deadline_epoch"] = _safe_int(
                persistent_health.get("deadline_epoch"),
                _safe_int(status.get("health_deadline_epoch"), 0),
            )
    return status


def get_status() -> dict[str, object]:
    status = _load_status()
    slot = _load_slot_state()
    return _save_status(_sync_status_from_persistent(status, slot))


def get_history() -> list[dict[str, object]]:
    return _load_history()


def get_channels() -> dict[str, object]:
    catalog = _load_catalog()
    return {
        "channels": catalog,
        "loaded_at": _timestamp(),
    }


def _set_failed_status(status: dict[str, object], reason: str, message: str) -> dict[str, object]:
    status["state"] = "failed"
    status["last_error"] = message
    status["last_action"] = f"{reason}: {message}"
    return _save_status(status)


def check_for_updates(channel: str) -> dict[str, object]:
    normalized_channel = _normalize_channel(channel)
    status = _load_status()
    status["state"] = "checking"
    status["channel"] = normalized_channel
    status["last_checked_at"] = _timestamp()
    status["last_error"] = ""
    status["last_action"] = f"Checking updates for channel {normalized_channel}."
    _save_status(status)
    catalog = _load_catalog()
    entry = catalog.get(normalized_channel, {})
    if not entry:
        raise UpdateEngineError("channel_not_found", f"update channel not found: {normalized_channel}")
    try:
        manifest_source = _resolve_manifest_source(entry.get("manifest_url", ""))
        _verify_sha256(manifest_source, entry.get("manifest_sha256", ""))
        signature_source = _resolve_signature_source(entry.get("signature_url", ""), manifest_source)
        _verify_detached_signature(manifest_source, signature_source)
        manifest = _load_manifest(manifest_source)
        details = _require_manifest_fields(manifest)
        slot = _load_slot_state()
        installed_version = slot.installed_version or _infer_installed_version()
        minimum_source_version = str(details["upgrade_policy"].get("minimum_source_version", "")).strip()
        _apply_version_policy(installed_version, minimum_source_version)
        available_version = str(details["version"])
        available_release_sequence = _safe_int(details["release_sequence"], 0)
        _enforce_anti_rollback(
            installed_version=installed_version,
            available_version=available_version,
            accepted_release_sequence=slot.accepted_release_sequence,
            available_release_sequence=available_release_sequence,
        )
    except UpdateEngineError as exc:
        status = _set_failed_status(status, exc.reason, str(exc))
        _append_history("check_failed", {"channel": normalized_channel, "reason": exc.reason, "error": str(exc)})
        raise
    _save_cached_manifest(manifest)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if signature_source.resolve() != PERSISTENT_MANIFEST_SIG_FILE.resolve():
            shutil.copyfile(signature_source, PERSISTENT_MANIFEST_SIG_FILE)
    except (OSError, shutil.Error):
        pass
    status["manifest_signature_verified"] = True
    status["available_version"] = available_version
    status["available_release_sequence"] = available_release_sequence
    status["installed_version"] = installed_version
    status["guardrail_update"] = "Update metadata verified with detached signatures."
    status["guardrail_rollback"] = "Rollback is supported by current release policy."
    if available_version and available_version != installed_version:
        status["state"] = "available"
        status["last_action"] = f"Update available: {installed_version} -> {available_version}."
    else:
        status["state"] = "idle"
        status["last_action"] = "System is up to date for selected channel."
    saved = _save_status(status)
    _append_history(
        "check",
        {
            "channel": normalized_channel,
            "installed_version": installed_version,
            "available_version": available_version,
        },
    )
    return saved


def stage_update(channel: str) -> dict[str, object]:
    status = check_for_updates(channel)
    available_version = str(status.get("available_version", "")).strip()
    installed_version = str(status.get("installed_version", "")).strip()
    if not available_version or available_version == installed_version:
        raise UpdateEngineError("no_update_available", "no newer version available in the selected channel")
    manifest = _load_cached_manifest()
    details = _require_manifest_fields(manifest)
    slot = _load_slot_state()
    status["state"] = "downloading"
    status["last_action"] = f"Downloading slot image for {available_version}."
    _save_status(status)
    slot_image = details["slot_image"]
    recovery_image = details["recovery_image"]
    slot_source = _resolve_artifact_source(str(slot_image.get("url", "")))
    recovery_source = _resolve_artifact_source(str(recovery_image.get("url", "")))
    _verify_artifact_sha256(slot_source, str(slot_image.get("sha256", "")), "slot image")
    _verify_artifact_sha256(recovery_source, str(recovery_image.get("sha256", "")), "recovery image")
    status["state"] = "verifying"
    status["last_action"] = "Artifact checksums verified."
    _save_status(status)
    slot_target, slot_stage_detail = _stage_slot_overlay(slot_source, slot.inactive_slot, available_version)
    recovery_target = _write_slot_artifact(recovery_source, "recovery", available_version)
    slot.previous_slot = slot.active_slot
    slot.pending_slot = slot.inactive_slot
    slot.boot_attempts_remaining = 1
    slot.staged_version = available_version
    slot.staged_release_sequence = _safe_int(details["release_sequence"], 0)
    slot.last_boot_result = "pending"
    _save_slot_state(slot)
    _persist_boot_intent(slot)
    status["state"] = "staged"
    status["staged_version"] = available_version
    status["pending_slot"] = slot.pending_slot
    status["previous_slot"] = slot.previous_slot
    status["slot_image_path"] = str(slot_target)
    status["recovery_image_path"] = str(recovery_target)
    status["last_action"] = f"Update staged to slot {slot.pending_slot}. Reboot to switch. {slot_stage_detail}"
    saved = _save_status(status)
    _append_history(
        "stage",
        {
            "channel": _normalize_channel(channel),
            "from": installed_version,
            "to": available_version,
            "pending_slot": slot.pending_slot,
            "slot_image_path": str(slot_target),
        },
    )
    return saved


def commit_staged_update() -> dict[str, object]:
    status = _load_status()
    slot = _load_slot_state()
    if _normalize_state(status.get("state")) != "staged" or not slot.pending_slot:
        raise UpdateEngineError("nothing_staged", "no staged update is available to commit")
    detail = _sync_grub_state(slot, boot_ok=False)
    status["state"] = "switching_on_reboot"
    status["last_action"] = f"Committed staged update to slot {slot.pending_slot}. Reboot required. {detail}"
    status["health_deadline_epoch"] = 0
    _save_persistent_health({"state": "switching_on_reboot", "deadline_epoch": 0, "at": _timestamp()})
    saved = _save_status(status)
    _append_history(
        "commit",
        {
            "pending_slot": slot.pending_slot,
            "staged_version": slot.staged_version,
            "detail": detail,
        },
    )
    return saved


def rollback_to_previous_slot(reason: str = "manual") -> dict[str, object]:
    status = _load_status()
    slot = _load_slot_state()
    target = slot.previous_slot or ("b" if slot.active_slot == "a" else "a")
    if target not in {"a", "b"}:
        raise UpdateEngineError("rollback_target_missing", "unable to determine rollback target slot")
    slot.inactive_slot = slot.active_slot
    slot.active_slot = target
    slot.pending_slot = ""
    slot.previous_slot = ""
    slot.boot_attempts_remaining = 0
    slot.last_boot_result = "rolled_back"
    slot.staged_version = ""
    slot.staged_release_sequence = 0
    _save_slot_state(slot)
    _clear_boot_intent()
    _save_persistent_health(
        {
            "state": "rolled_back",
            "deadline_epoch": 0,
            "at": _timestamp(),
            "reason": reason,
            "active_slot": slot.active_slot,
        }
    )
    detail = _sync_grub_state(slot, boot_ok=True)
    status["state"] = "rolled_back"
    status["pending_slot"] = ""
    status["active_slot"] = slot.active_slot
    status["inactive_slot"] = slot.inactive_slot
    status["staged_version"] = ""
    status["last_action"] = f"Rolled back to slot {slot.active_slot} ({reason}). {detail}"
    saved = _save_status(status)
    _append_history("rollback", {"target_slot": slot.active_slot, "reason": reason})
    return saved


def acknowledge_healthy_boot() -> dict[str, object]:
    status = _load_status()
    slot = _load_slot_state()
    if not slot.pending_slot:
        status["state"] = "healthy"
        status["last_action"] = "Boot health acknowledged with no pending slot."
        _clear_boot_intent()
        _clear_persistent_health()
        return _save_status(status)
    slot.active_slot = slot.pending_slot
    slot.inactive_slot = "b" if slot.active_slot == "a" else "a"
    slot.pending_slot = ""
    slot.previous_slot = ""
    slot.boot_attempts_remaining = 0
    slot.installed_version = slot.staged_version or slot.installed_version
    if slot.staged_release_sequence > 0:
        slot.accepted_release_sequence = slot.staged_release_sequence
    slot.staged_version = ""
    slot.staged_release_sequence = 0
    slot.last_boot_result = "healthy"
    _save_slot_state(slot)
    _clear_boot_intent()
    _clear_persistent_health()
    detail = _sync_grub_state(slot, boot_ok=True)
    status["state"] = "healthy"
    status["installed_version"] = slot.installed_version
    status["active_slot"] = slot.active_slot
    status["inactive_slot"] = slot.inactive_slot
    status["pending_slot"] = ""
    status["staged_version"] = ""
    status["last_error"] = ""
    status["last_action"] = f"Boot health acknowledged. Slot {slot.active_slot} is now active. {detail}"
    saved = _save_status(status)
    _append_history("health_ack", {"active_slot": slot.active_slot, "installed_version": slot.installed_version})
    return saved


def process_boot_health(timeout_seconds: int = 300) -> dict[str, object]:
    status = _sync_status_from_persistent(_load_status(), _load_slot_state())
    slot = _load_slot_state()
    boot_intent = _load_boot_intent()
    now = int(time.time())
    state = _normalize_state(status.get("state"))
    if slot.pending_slot and boot_intent and state in {"idle", "switching_on_reboot", "healthy", "rolled_back", "failed"}:
        status["state"] = "awaiting_health_ack"
        status["health_deadline_epoch"] = now + max(30, int(timeout_seconds))
        status["last_action"] = (
            f"Booted staged slot {slot.pending_slot}; awaiting health acknowledgement before "
            f"{status['health_deadline_epoch']}."
        )
        _save_persistent_health(
            {
                "state": "awaiting_health_ack",
                "deadline_epoch": status["health_deadline_epoch"],
                "at": _timestamp(),
                "pending_slot": slot.pending_slot,
            }
        )
        saved = _save_status(status)
        write_runtime_json(
            RUNTIME_HEALTH_FILE,
            {"state": "awaiting_health_ack", "deadline_epoch": status["health_deadline_epoch"], "at": _timestamp()},
            mode=0o664,
        )
        return saved
    if state == "awaiting_health_ack":
        persistent_health = _load_persistent_health()
        deadline = _safe_int(
            persistent_health.get("deadline_epoch"),
            _safe_int(status.get("health_deadline_epoch"), 0),
        )
        if deadline and now > deadline:
            status["state"] = "rollback_pending"
            status["last_action"] = "Health acknowledgement timed out; automatic rollback scheduled."
            _save_status(status)
            rolled = rollback_to_previous_slot(reason="health-timeout")
            write_runtime_json(
                RUNTIME_HEALTH_FILE,
                {"state": "rolled_back", "deadline_epoch": deadline, "at": _timestamp(), "reason": "health-timeout"},
                mode=0o664,
            )
            return rolled
        _save_persistent_health(
            {
                "state": "awaiting_health_ack",
                "deadline_epoch": deadline,
                "at": _timestamp(),
                "pending_slot": slot.pending_slot,
            }
        )
        write_runtime_json(
            RUNTIME_HEALTH_FILE,
            {"state": "awaiting_health_ack", "deadline_epoch": deadline, "at": _timestamp()},
            mode=0o664,
        )
        return status
    _save_persistent_health({"state": state, "deadline_epoch": 0, "at": _timestamp()})
    write_runtime_json(
        RUNTIME_HEALTH_FILE,
        {"state": state, "at": _timestamp()},
        mode=0o664,
    )
    return status


def run_health_monitor(timeout_seconds: int = 300, poll_interval_seconds: int = 5) -> dict[str, object]:
    status = process_boot_health(timeout_seconds=timeout_seconds)
    while _normalize_state(status.get("state")) == "awaiting_health_ack":
        time.sleep(max(1, int(poll_interval_seconds)))
        status = process_boot_health(timeout_seconds=timeout_seconds)
    return status
