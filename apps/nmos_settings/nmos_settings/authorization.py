from __future__ import annotations


def resolve_unix_uid(username: str | None) -> int | None:
    name = str(username or "").strip()
    if not name:
        return None
    try:
        import pwd  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return int(pwd.getpwnam(name).pw_uid)  # type: ignore[attr-defined]
    except KeyError:
        return None


def resolve_group_member_uids(group_name: str | None) -> set[int]:
    name = str(group_name or "").strip()
    if not name:
        return set()
    try:
        import grp  # type: ignore[import-not-found]
        import pwd  # type: ignore[import-not-found]
    except ImportError:
        return set()
    try:
        target_group = grp.getgrnam(name)  # type: ignore[attr-defined]
    except KeyError:
        return set()

    members = set(target_group.gr_mem)
    users_with_primary_group = {
        entry.pw_name
        for entry in pwd.getpwall()  # type: ignore[attr-defined]
        if int(entry.pw_gid) == int(target_group.gr_gid)
    }
    usernames = members.union(users_with_primary_group)
    uids: set[int] = set()
    for username in usernames:
        try:
            uids.add(int(pwd.getpwnam(username).pw_uid))  # type: ignore[attr-defined]
        except KeyError:
            continue
    return uids


def build_write_uid_allowlist(gdm_user: str | None, admin_group: str | None = None) -> set[int]:
    allowed = {0}
    gdm_uid = resolve_unix_uid(gdm_user)
    if gdm_uid is not None:
        allowed.add(gdm_uid)
    allowed.update(resolve_group_member_uids(admin_group))
    return allowed


def is_write_authorized(uid: int, allowed_uids: set[int]) -> bool:
    return int(uid) in allowed_uids
