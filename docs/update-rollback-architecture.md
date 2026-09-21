# Update And Rollback Architecture

This document defines the NM-OS update and rollback model as a release-gated architecture.

## Scope

- update channel selection (`stable`, `beta`, `nightly`)
- update metadata verification (`release-manifest.json`, `update-catalog.json`)
- rollback expectations and operator workflow
- failure handling policy for interrupted or invalid updates

## Atomic Strategy Decision

NM-OS now uses an **A/B staged update engine** strategy for experimental installs:

1. Update engine validates signed channel metadata.
2. The target slot overlay is extracted into the inactive rootfs when an A/B slot device is available, otherwise the artifact is preserved in NM-OS state as a safe fallback.
3. Boot intent is persisted and the next reboot switches to pending slot.
4. Post-boot health acknowledgement confirms the slot or triggers rollback.

Legacy overlay installs remain explicitly unsupported for in-place migration in this sprint.

## Signed Artifact And Manifest Requirements

Release metadata must provide:

- installer artifact identity
- checksum/signature mode
- build/channel/version metadata
- a positive, monotonically increasing `release_sequence`
- rollback capability signal

Minimum required files:

- `dist/release-manifest.json`
- `dist/update-catalog.json`

Verification rules:

- metadata format and required keys must pass CI checks
- checksum/signature mode must be present and readable
- trust-chain status must be user-visible from Control Center
- a signed version older than the installed version is rejected
- metadata below the highest accepted `release_sequence` is rejected as a replay
- slot archives reject links, device nodes, and paths outside the inactive slot

## Rollback UX And State

Rollback is modeled as an explicit user action:

1. Update history tracks `from` and `to` versions.
2. Rollback action restores previous version metadata intent.
3. Operator reboots and validates actual package/image state.

Control Center must surface:

- active channel and installed version
- last action (check/apply/rollback)
- rollback availability based on history

## Failure Recovery UX

If update apply fails or metadata is invalid:

- keep current installed version as authoritative
- preserve rollback history without destructive rewrites
- surface failure guidance in Control Center status text
- require explicit operator retry instead of silent background mutation

If rollback cannot proceed:

- keep existing update state unchanged
- show actionable diagnostics guidance

## Release Gate Checklist

Every release must satisfy all of the following:

1. Architecture doc exists and stays aligned with implementation.
2. Update metadata files are generated and verified in CI.
3. Control Center exposes update + rollback state and actions.
4. Rollback path is test-covered.
5. Trust-chain metadata and verification status are visible.
