from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "nmos_common"))

import nmos_common.update_engine as update_engine


def _configure_paths(monkeypatch, root: Path) -> None:
    run_dir = root / "run"
    state_dir = root / "state"
    monkeypatch.setattr(update_engine, "RUNTIME_DIR", run_dir)
    monkeypatch.setattr(update_engine, "STATE_DIR", state_dir)
    monkeypatch.setattr(update_engine, "RUNTIME_STATUS_FILE", run_dir / "update-engine-status.json")
    monkeypatch.setattr(update_engine, "RUNTIME_HEALTH_FILE", run_dir / "update-engine-health.json")
    monkeypatch.setattr(update_engine, "PERSISTENT_HISTORY_FILE", state_dir / "history.json")
    monkeypatch.setattr(update_engine, "PERSISTENT_SLOT_FILE", state_dir / "slot-state.json")
    monkeypatch.setattr(update_engine, "PERSISTENT_CATALOG_FILE", state_dir / "catalog-cache.json")
    monkeypatch.setattr(update_engine, "PERSISTENT_MANIFEST_FILE", state_dir / "manifest-cache.json")
    monkeypatch.setattr(update_engine, "PERSISTENT_MANIFEST_SIG_FILE", state_dir / "manifest-cache.sig")
    monkeypatch.setattr(update_engine, "PERSISTENT_ARTIFACT_DIR", state_dir / "artifacts")
    monkeypatch.setattr(update_engine, "BOOT_INTENT_FILE", state_dir / "boot-intent.json")
    monkeypatch.setattr(update_engine, "PERSISTENT_HEALTH_FILE", state_dir / "health-state.json")
    monkeypatch.setattr(update_engine, "SHARED_UPDATE_CATALOG_FILE", root / "missing-shared-catalog.json")
    monkeypatch.setattr(update_engine, "DEFAULT_DIST_FEED_FILE", root / "missing-dist-catalog.json")
    monkeypatch.setattr(update_engine, "DEFAULT_FEED_FILE", root / "missing-config-catalog.json")
    monkeypatch.setattr(update_engine, "SHARED_RELEASE_MANIFEST_FILE", root / "missing-shared-manifest.json")
    monkeypatch.setattr(update_engine, "DEFAULT_DIST_MANIFEST_FILE", root / "missing-dist-manifest.json")


def test_update_engine_status_bootstrap(monkeypatch, workspace_tmp_path: Path) -> None:
    _configure_paths(monkeypatch, workspace_tmp_path)
    status = update_engine.get_status()
    assert status["state"] == "idle"
    assert status["active_slot"] == "a"
    assert status["inactive_slot"] == "b"
    assert "guardrail_update" in status
    assert "guardrail_rollback" in status


def test_update_engine_health_timeout_triggers_rollback(monkeypatch, workspace_tmp_path: Path) -> None:
    _configure_paths(monkeypatch, workspace_tmp_path)
    status = update_engine.get_status()
    status.update(
        {
            "state": "awaiting_health_ack",
            "health_deadline_epoch": 1,
            "last_action": "waiting",
        }
    )
    update_engine._save_status(status)
    slot = update_engine._load_slot_state()
    slot.active_slot = "b"
    slot.inactive_slot = "a"
    slot.pending_slot = "b"
    slot.previous_slot = "a"
    slot.boot_attempts_remaining = 1
    update_engine._save_slot_state(slot)

    result = update_engine.process_boot_health(timeout_seconds=30)
    assert result["state"] == "rolled_back"
    assert result["active_slot"] == "a"
    assert "Rolled back" in str(result["last_action"])


def test_update_engine_manifest_required_fields_validation() -> None:
    with pytest.raises(update_engine.UpdateEngineError) as error:
        update_engine._require_manifest_fields({"version": "1.0.0"})
    assert error.value.reason == "manifest_required_fields_missing"

    manifest = {
        "version": "1.2.3",
        "release_sequence": 10203,
        "artifacts": {
            "slot_image": {"name": "slot.img", "sha256": "a" * 64, "url": "/tmp/slot.img"},
            "recovery_image": {"name": "recovery.img", "sha256": "b" * 64, "url": "/tmp/recovery.img"},
        },
        "upgrade_policy": {"minimum_source_version": "1.0.0", "supports_rollback": True},
        "migration": {"bundle_id": "bundle-1"},
    }
    details = update_engine._require_manifest_fields(manifest)
    assert details["version"] == "1.2.3"
    assert details["release_sequence"] == 10203
    assert details["migration_bundle_id"] == "bundle-1"


def test_update_engine_rejects_version_downgrade_and_release_replay() -> None:
    assert update_engine._version_less_than("1.0.0-alpha.2", "1.0.0-alpha.10")
    assert not update_engine._version_less_than("1.0.0-alpha.10", "1.0.0-alpha.2")

    with pytest.raises(update_engine.UpdateEngineError) as downgrade_error:
        update_engine._enforce_anti_rollback(
            installed_version="2.0.0",
            available_version="1.9.9",
            accepted_release_sequence=200,
            available_release_sequence=201,
        )
    assert downgrade_error.value.reason == "release_downgrade_blocked"

    with pytest.raises(update_engine.UpdateEngineError) as replay_error:
        update_engine._enforce_anti_rollback(
            installed_version="2.0.0",
            available_version="2.1.0",
            accepted_release_sequence=200,
            available_release_sequence=199,
        )
    assert replay_error.value.reason == "release_replay_blocked"


def test_safe_extract_tarball_extracts_regular_files(workspace_tmp_path: Path) -> None:
    archive_path = workspace_tmp_path / "valid.tar"
    destination = workspace_tmp_path / "slot"
    payload = b"safe update payload\n"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("usr/share/nmos/release.txt")
        member.size = len(payload)
        member.mode = 0o644
        archive.addfile(member, io.BytesIO(payload))

    update_engine._safe_extract_tarball(archive_path, destination)

    assert (destination / "usr/share/nmos/release.txt").read_bytes() == payload


def test_safe_extract_tarball_rejects_symlink_escape(workspace_tmp_path: Path) -> None:
    archive_path = workspace_tmp_path / "malicious.tar"
    destination = workspace_tmp_path / "slot"
    with tarfile.open(archive_path, "w") as archive:
        link = tarfile.TarInfo("escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        archive.addfile(link)
        payload = b"must not escape\n"
        member = tarfile.TarInfo("escape/owned.txt")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    with pytest.raises(update_engine.UpdateEngineError) as error:
        update_engine._safe_extract_tarball(archive_path, destination)

    assert error.value.reason == "artifact_extract_failed"
    assert not (workspace_tmp_path / "outside/owned.txt").exists()


def test_safe_extract_tarball_rejects_parent_path_escape(workspace_tmp_path: Path) -> None:
    archive_path = workspace_tmp_path / "traversal.tar"
    destination = workspace_tmp_path / "slot"
    payload = b"must stay contained\n"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("../outside.txt")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    with pytest.raises(update_engine.UpdateEngineError) as error:
        update_engine._safe_extract_tarball(archive_path, destination)

    assert error.value.reason == "artifact_extract_failed"
    assert not (workspace_tmp_path / "outside.txt").exists()


def test_update_engine_boot_intent_recovers_after_reboot(monkeypatch, workspace_tmp_path: Path) -> None:
    _configure_paths(monkeypatch, workspace_tmp_path)
    slot = update_engine._load_slot_state()
    slot.pending_slot = "b"
    slot.previous_slot = "a"
    slot.boot_attempts_remaining = 1
    slot.staged_version = "1.2.0"
    update_engine._save_slot_state(slot)
    update_engine._persist_boot_intent(slot)

    result = update_engine.process_boot_health(timeout_seconds=45)
    assert result["state"] == "awaiting_health_ack"
    assert int(result["health_deadline_epoch"]) > 0
    persistent_health = update_engine._load_persistent_health()
    assert persistent_health["state"] == "awaiting_health_ack"


def test_acknowledge_healthy_boot_clears_boot_state(monkeypatch, workspace_tmp_path: Path) -> None:
    _configure_paths(monkeypatch, workspace_tmp_path)
    slot = update_engine._load_slot_state()
    slot.pending_slot = "b"
    slot.previous_slot = "a"
    slot.staged_version = "2.0.0"
    slot.staged_release_sequence = 20000
    update_engine._save_slot_state(slot)
    update_engine._persist_boot_intent(slot)
    update_engine._save_persistent_health({"state": "awaiting_health_ack", "deadline_epoch": 10})

    result = update_engine.acknowledge_healthy_boot()
    assert result["state"] == "healthy"
    assert update_engine._load_slot_state().accepted_release_sequence == 20000
    assert not update_engine.BOOT_INTENT_FILE.exists()
    assert not update_engine.PERSISTENT_HEALTH_FILE.exists()
