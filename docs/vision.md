# Product Direction

NM-OS is a privacy-focused Linux desktop for people who want stronger protection without becoming security experts.

The goal is to give privacy-conscious people a computer that works immediately, feels personal,
and can grow as strict or as open as they need it to be.

## Core Principles

### Human-first computing

The computer works for the person, not the other way around.

Every feature must answer the question: does this make someone's life easier or safer
in a way they can actually feel? If the answer is no, it does not belong in the default experience.

Users should never need to understand the system to use it.
They should only need to understand it when they *want* to.

### Fluid modes, not fixed personas

NM-OS does not categorize users. A student, a journalist, and a developer are all the same
person at different moments  -  and the system should move with them.

Switching between a comfortable everyday desktop and a hardened private workspace
should take one action, not a reinstall.

- Profiles are starting points, not locks.
- Every individual setting can be toggled independently.
- Mode changes are fast, visible, and reversible.

### Everything reachable, nothing forced

No capability is hidden in NM-OS. Every setting  -  including the deepest security controls  - 
is reachable from the Control Center.

But nothing beyond language and a starting profile is required during setup.
Every configuration step can be skipped and revisited later.

### Explainable choices

When NM-OS changes something, it says so clearly.
Users see what changed, what they gain, and what they give up.

- Profile switching shows a plain-language tradeoff summary.
- Individual toggles explain what they do before the user enables them.
- Changes that require a reboot are flagged before they apply.

### Progressive depth

The same platform should serve:

- someone opening a computer for the first time
- someone who wants Tor-first networking and an encrypted vault by default
- someone who wants to audit service boundaries, logging policy, and device trust

A first-time user never sees complexity they did not ask for.
An advanced user never hits a wall they cannot pass.

### Visible trust boundaries

Whenever NM-OS restricts something, the boundary is visible and understandable:

- network policy shows whether the system is direct, Tor-first, or offline
- device policy shows whether removable hardware is broadly trusted, gated, or blocked
- app isolation describes what gets tighter or broader access
- logging policy explains what is retained and what is deliberately discarded

### Independence through layers

NM-OS does not need to begin as a new kernel to become a real operating system project.

Its identity comes from its own policy model, installer behavior, security UX, trust boundaries,
and platform defaults. Over time, more of those layers move under NM-OS control.

## What NM-OS Should Not Become

- a skin over another system with no behavioral identity of its own
- a security product that only experts can understand or use
- a locked-down environment that hides the cost of each restriction
- a convenience-focused desktop that uses security language without real enforcement
- a system that forces users into a category before they can start working

## Near-Term Product Priorities

1. Make everyday use feel complete: productivity apps, browser choice, media, photos.
2. Make mode-switching fast, visible, and always reversible.
3. Make the Control Center the single place for every setting  -  no hunting.
4. Keep profiles readable and explainable with plain-language tradeoff summaries.
5. Tie every security setting to a real enforcement layer or mark it explicitly partial.
6. Treat installer, recovery, and updates as part of the platform identity.
