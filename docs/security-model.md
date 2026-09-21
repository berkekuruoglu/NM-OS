# Security Model

NM-OS treats security as a set of visible platform choices instead of a hidden mode switch.

The current direction is to let users move between a more comfortable desktop and a stricter system without losing clarity about what changed.

## Current Layers

### Settings authority model

`org.nmos.Settings1` is split into two D-Bus trust levels:

- `org.nmos.Settings1.Read`: read-only status and effective posture views
- `org.nmos.Settings1.Write`: mutating settings and commit operations

Current caller boundary:

- `root`: read and write
- `@NMOS_GDM_USER@`: read and write
- `@NMOS_SETTINGS_ADMIN_GROUP@`: read and write
- `at_console=true`: read-only

Method boundary:

- Read-only:
- `GetSettings`
- `GetEffectiveSettings`
- `GetPendingRebootChanges`
- Mutating:
- `ApplyPreset`
- `SetOverrides`
- `ResetToPreset`
- `Commit`

This keeps desktop visibility available while reducing the default mutation surface for arbitrary console sessions.

The settings service also enforces a runtime write boundary:

- mutating calls are validated against the D-Bus sender Unix UID
- only explicit write-authorized UIDs are accepted
- rejected callers receive `org.freedesktop.DBus.Error.AccessDenied`

This is a second-layer guard in addition to static D-Bus policy.

### Security profiles

Profiles are the top-level entry point for most people.

They should define a coherent default posture across:

- networking
- app isolation
- device trust
- logging retention
- vault behavior
- desktop comfort choices that affect distraction and friction

### Network policy

Network behavior is one of the clearest trust boundaries in NM-OS.

Current states:

- `direct`
- `tor`
- `offline`

Users should always understand which state is active and what it implies.

### App isolation

The long-term direction is a stronger application-boundary model that remains understandable from the UI.

The system should explain:

- what the default isolation level is
- what changes when it becomes stricter
- where compatibility may narrow

### Device trust

Removable devices and external hardware should have an explicit trust posture instead of silent broad access.

The system should make it clear whether devices are:

- broadly trusted
- prompt-gated
- tightly limited

### Logging posture

Diagnostics are useful, but retained traces are also part of the attack surface and privacy story.

NM-OS should expose logging as a user-visible tradeoff:

- more diagnostics
- less retained history
- strongest minimization

### Encrypted vault

The encrypted vault is a concrete example of explainable security:

- users can see whether it exists
- whether it is locked
- how auto-lock behaves
- what convenience tradeoffs come from unlock choices

## Profile Matrix

| Profile | Goal | Network | Isolation | Devices | Logging | Tradeoff |
| --- | --- | --- | --- | --- | --- | --- |
| Relaxed | Lowest friction | Direct | Standard | Shared | Balanced | Easiest to use, weakest default boundaries |
| Balanced | Default privacy-conscious daily baseline | Direct | Focused | Prompt | Minimal | Strong browser privacy and broad compatibility without hiding the public IP |
| Hardened | Stronger daily containment | Tor-first | Strict | Locked | Minimal | Less convenience and narrower compatibility |
| Maximum | Highest practical restriction | Offline | Strict | Locked | Sealed | Strongest posture, intentionally restrictive |

## Setting To Enforcement Matrix

| Setting | User-facing meaning | Enforcement layer today | Status |
| --- | --- | --- | --- |
| `network_policy` | Direct / Tor-routed / Offline network posture | `network_bootstrap.py` nftables TCP/DNS redirects + Tor `TransPort`/`DNSPort` + fail-closed output policy | Enforced |
| Browser tracking protection | Strong daily anti-tracking baseline | Firefox enterprise preferences + Chromium managed privacy policy in the system overlay | Enforced baseline |
| `sandbox_default` | Standard / Focused / Strict default app isolation intent | `config/system-overlay/usr/local/lib/nmos/app_isolation_policy.py` + `nmos-app-isolation-policy.service` global Flatpak override baseline | Enforced baseline (global defaults), per-app overrides roadmap |
| `app_overrides` | Per-application filesystem, network, and device isolation overrides | `app_isolation_policy.py` per-app `flatpak override --system <app-id>` rules + Control Center per-app editor + settings D-Bus `SetOverrides` | Enforced (per-app permission profile layer) |
| `device_policy` | Shared / Prompt / Locked external device trust posture | `config/system-overlay/usr/local/lib/nmos/device_policy.py` + `nmos-device-policy.service` udev baseline for removable USB storage trust | Enforced baseline (removable storage posture), HID/USB networking roadmap |
| `logging_policy` | Balanced / Minimal / Sealed retained trace posture | `config/system-overlay/usr/local/lib/nmos/logging_policy.py` + journald drop-in (`/etc/systemd/journald.conf.d/90-nmos-logging-policy.conf`) + startup vacuum policy | Enforced (boot-time policy application) |
| `allow_brave_browser` | Whether Brave can appear when allowed by build/network posture | `config/system-overlay/usr/local/lib/nmos/desktop_mode.py` and `brave_policy.py` runtime gating | Enforced (feature-gated + policy-aware) |
| `default_browser` | Which browser is used as the desktop default for web links | `config/system-overlay/usr/local/lib/nmos/desktop_mode.py` (`xdg-settings` + desktop defaults sync) | Enforced (post-login session policy) |
| `update channel + release manifest` | Which signed release stream is trusted and staged to inactive slot | `apps/nmos_update/nmos_update/service.py` + `apps/nmos_common/nmos_common/update_engine.py` detached-signature verification, staged slot writes, rollback state machine | Enforced (signed-manifest gate + A/B staging) |
| `vault` | Auto-lock and unlock-on-login defaults for encrypted vault behavior | Persistent storage service state + greeter/control-center orchestration | Enforced for current vault flow |
| `active_profile` + overrides | Explainable security baseline with explicit deviations | `nmos_common.system_settings` normalization + pending reboot classification | Enforced in settings model, maps to runtime components above |

This matrix is a release gate aid: every new security-facing setting should be mapped here with a concrete enforcement layer (or explicitly marked partial).

## Direction For Future Work

1. Make every security-facing setting map to a real enforcement layer.
2. Add clearer permission and policy feedback to the desktop UI.
3. Reduce hidden privilege boundaries in services and helper processes.
4. Keep stronger modes readable instead of mystical.
5. Build update, rollback, and recovery behavior into the security story.
