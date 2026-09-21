# Security Settings

NM-OS now treats security as a spectrum instead of a boot-only mode switch.

The current alpha ships four presets:

## `Relaxed`

- direct networking by default
- broadest comfort profile
- lighter sandbox expectations
- best when ease of use matters more than stricter defaults

Who it is for:
People who want the easiest daily desktop experience.

Tradeoff:
You gain convenience and compatibility, but the default trust boundaries are lighter.

## `Balanced`

- default NM-OS profile
- direct networking for broad website compatibility
- strong Firefox and Chromium tracking-protection defaults
- focused app isolation, prompt-gated removable storage, and minimal logging
- recommended starting point for privacy-conscious daily users

Who it is for:
People who want a practical privacy baseline without a harsh learning curve.

Tradeoff:
It does not hide the public IP address from websites; Hardened mode is available when Tor routing is needed.

## `Hardened`

- enforced Tor routing for TCP and DNS traffic
- tighter sandbox and device defaults
- reduced motion and denser UI defaults
- stronger posture for daily use with less convenience

Who it is for:
People who want stronger daily protection and are comfortable with extra friction.

Tradeoff:
You get tighter defaults, but compatibility and convenience start to narrow.

## `Maximum`

- offline by default
- strict device and logging posture
- strongest practical baseline in the current product slice

Who it is for:
High-sensitivity situations where minimizing exposure matters more than convenience.

Tradeoff:
This profile is intentionally restrictive and expects the user to work around missing convenience.

## Overrides

Every preset can be customized with per-setting overrides.

Current override surfaces include:

- language and keyboard
- network policy
- Brave visibility
- sandbox default
- vault preferences
- device policy
- logging policy
- theme profile, accent, density, and motion

## Pending reboot behavior

Some changes can apply immediately.

Some changes are tracked in `pending_reboot`, especially:

- `network_policy`
- `sandbox_default`
- `device_policy`
- `logging_policy`

This is why both the greeter summary and the control center show reboot hints.

## Current limits

- presets do not yet map to full per-app permission editing
- the current alpha does not claim amnesic guarantees
- the visual theme is curated and intentionally limited, not a full theme editor
