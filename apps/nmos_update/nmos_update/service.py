from __future__ import annotations

import logging
import shutil
import subprocess

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
from nmos_common.platform_adapter import get_gdm_user, get_settings_admin_group
from nmos_common.update_client import DBUS_NAME, DBUS_PATH, DBUS_READ_INTERFACE, DBUS_WRITE_INTERFACE
from nmos_common.update_engine import (
    UpdateEngineError,
    acknowledge_healthy_boot,
    check_for_updates,
    commit_staged_update,
    get_channels,
    get_history,
    get_status,
    rollback_to_previous_slot,
    stage_update,
)
from nmos_settings.authorization import build_write_uid_allowlist, is_write_authorized

LOGGER = logging.getLogger("nmos.update.service")
POLKIT_ACTION_ID = "org.nmos.update.write"


class UpdateService(dbus.service.Object):
    def __init__(self, bus: dbus.SystemBus) -> None:
        self._bus = bus
        self._write_allowed_uids = build_write_uid_allowlist(get_gdm_user(), get_settings_admin_group())
        name = dbus.service.BusName(DBUS_NAME, bus)
        super().__init__(name, DBUS_PATH)

    def _assert_write_authorized(self, sender: str | None) -> None:
        if not sender:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.AccessDenied",
                "missing sender identity for write operation",
            )
        sender_uid = int(self._bus.get_unix_user(sender))
        if is_write_authorized(sender_uid, self._write_allowed_uids):
            return
        if self._is_polkit_write_authorized(sender=sender, sender_uid=sender_uid):
            return
        raise dbus.exceptions.DBusException(
            "org.freedesktop.DBus.Error.AccessDenied",
            "update write access denied for this caller",
        )

    def _is_polkit_write_authorized(self, *, sender: str, sender_uid: int) -> bool:
        if shutil.which("pkcheck") is None:
            return False
        try:
            sender_pid = int(self._bus.get_unix_process_id(sender))
        except Exception:
            return False
        try:
            completed = subprocess.run(
                [
                    "pkcheck",
                    "--action-id",
                    POLKIT_ACTION_ID,
                    "--process",
                    str(sender_pid),
                    "--allow-user-interaction",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if completed.returncode == 0:
            LOGGER.info("Polkit authorized update write for uid=%s pid=%s", sender_uid, sender_pid)
            return True
        LOGGER.warning(
            "Polkit denied update write for uid=%s pid=%s returncode=%s stderr=%s",
            sender_uid,
            sender_pid,
            completed.returncode,
            (completed.stderr or "").strip(),
        )
        return False

    def _notify(self, payload: dict[str, object]) -> dict[str, object]:
        self.UpdateStateChanged(dict(payload))
        return payload

    @dbus.service.signal(DBUS_WRITE_INTERFACE, signature="a{sv}")
    def UpdateStateChanged(self, state: dict[str, object]) -> None:
        return None

    @dbus.service.method(DBUS_READ_INTERFACE, in_signature="", out_signature="a{sv}")
    def GetStatus(self) -> dict[str, object]:
        return get_status()

    @dbus.service.method(DBUS_READ_INTERFACE, in_signature="", out_signature="aa{sv}")
    def GetHistory(self) -> list[dict[str, object]]:
        return get_history()

    @dbus.service.method(DBUS_READ_INTERFACE, in_signature="", out_signature="a{sv}")
    def GetChannels(self) -> dict[str, object]:
        return get_channels()

    @dbus.service.method(DBUS_WRITE_INTERFACE, in_signature="s", out_signature="a{sv}", sender_keyword="sender")
    def CheckForUpdates(self, channel: str, sender: str | None = None) -> dict[str, object]:
        self._assert_write_authorized(sender)
        try:
            return self._notify(check_for_updates(channel))
        except UpdateEngineError as error:
            raise dbus.exceptions.DBusException("org.nmos.Update1.Error", f"{error.reason}: {error}") from error

    @dbus.service.method(DBUS_WRITE_INTERFACE, in_signature="s", out_signature="a{sv}", sender_keyword="sender")
    def StageUpdate(self, channel: str, sender: str | None = None) -> dict[str, object]:
        self._assert_write_authorized(sender)
        try:
            return self._notify(stage_update(channel))
        except UpdateEngineError as error:
            raise dbus.exceptions.DBusException("org.nmos.Update1.Error", f"{error.reason}: {error}") from error

    @dbus.service.method(DBUS_WRITE_INTERFACE, in_signature="", out_signature="a{sv}", sender_keyword="sender")
    def CommitStagedUpdate(self, sender: str | None = None) -> dict[str, object]:
        self._assert_write_authorized(sender)
        try:
            return self._notify(commit_staged_update())
        except UpdateEngineError as error:
            raise dbus.exceptions.DBusException("org.nmos.Update1.Error", f"{error.reason}: {error}") from error

    @dbus.service.method(DBUS_WRITE_INTERFACE, in_signature="", out_signature="a{sv}", sender_keyword="sender")
    def RollbackToPreviousSlot(self, sender: str | None = None) -> dict[str, object]:
        self._assert_write_authorized(sender)
        try:
            return self._notify(rollback_to_previous_slot(reason="manual"))
        except UpdateEngineError as error:
            raise dbus.exceptions.DBusException("org.nmos.Update1.Error", f"{error.reason}: {error}") from error

    @dbus.service.method(DBUS_WRITE_INTERFACE, in_signature="", out_signature="a{sv}", sender_keyword="sender")
    def AcknowledgeHealthyBoot(self, sender: str | None = None) -> dict[str, object]:
        self._assert_write_authorized(sender)
        try:
            return self._notify(acknowledge_healthy_boot())
        except UpdateEngineError as error:
            raise dbus.exceptions.DBusException("org.nmos.Update1.Error", f"{error.reason}: {error}") from error


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    UpdateService(bus)
    LOGGER.info("NM-OS update service ready")
    loop = GLib.MainLoop()
    loop.run()


if __name__ == "__main__":
    main()
