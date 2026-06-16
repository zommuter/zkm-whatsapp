# 2026-06-16 — W10 auto-decryption trigger: install-readiness & closure (id:d058)

**Started:** 2026-06-16 20:55
**Session:** 1e8f9a2b-c4c7-414f-834e-c37e6b8a233c
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🛠️ Sven (systemd/desktop-automation — new)
**Topic:** W10 (id:d058) is BUILT but held open — decide whether the systemd `.path`/oneshot units are sound to install as-is, whether to ship a backstop timer, whether a plugin-local unit is the right layer vs the future `zkm fetch` orchestrator, and what exactly closes the item.

## Surfaced discoveries
- [2026-06-01 zkm] zkm ingest-only-plugin + core-fetch-orchestrator pattern: a future core `zkm fetch` orchestrates source-specific fetch tools via config, **avoiding per-source systemd sprawl** — see docs/meeting-notes/2026-06-01-1334-contacts-calendar-plugins.md
- [2026-05-08 zkm] Tracked git-hook pattern: store script in repo, pipe output through `systemd-cat -t <tag>`, exit 0 — journald-queryable observability with zero coupling to the trigger.
- [2026-06-03 zkm] WhatsApp dedup correctness is on `key_id`; watermark is speed optimisation only — re-running convert on an unchanged db is safe (no dup risk).

## Agenda
1. Is the built design sound enough to install as-is?
2. Robustness gap: missed-edge — ship backstop `.timer` now, or leave documented?
3. Layer question: plugin-local systemd unit vs. "avoid per-source systemd sprawl → core `zkm fetch`" intent.
4. Closure criteria: what ticks the REVIEW_ME box and closes d058?

## Discussion

**Agenda 1 (design soundness):** 🏗️ Archie called the shape right — atomic `mktemp`+`mv -f`, `flock -n`, newer-than idempotency guard, `--no-amenders`. 🛠️ Sven noted `.path PathModified` is edge-triggered-while-active (correct; the `flock` protects the manual-start race, not the systemd coalesce). 😈 Riku's sharpest concern: keyring under `systemd --user` only works if the Secret Service is unlocked; on a headless boot or locked screen, `secret-tool` fails non-zero and the run aborts with `set -e` — fails safe (source db untouched, failure in journal), precondition documented in README. ✂️ Petra named what's out of scope: retry logic, notification hooks, state file additions. Room approved the content as-is.

**Agenda 2 (timer):** 🛠️ Sven: `.path PathModified` misses a backup that lands while the unit is stopped; the README already describes a backstop `.timer` (README.md:50-52). 😈 Riku: a daily timer fires when the keyring may be unavailable → daily journal noise (the success path is a no-op but the keyring-unavailable path isn't). User applied **observe-before-preventing**: defer the timer entirely; revisit only if a real missed-backup is observed. Also raised the escalation: "basically every zkm plugin does timer runs; maybe delegate to a zkm-scheduler plugin or add to core."

**Agenda 3 (layer):** 🏗️ Archie surfaced the 2026-06-01 design intent: a future core `zkm fetch` orchestrating source-specific fetch tools to *avoid per-source systemd sprawl*. 🛠️ Sven clarified the right abstraction: keep systemd as the OS event source (can't move `PathModified` into Python); collapse the N bespoke wrapper scripts into `ExecStart=zkm fetch <source>` as the uniform systemd target. ✂️ Petra ran N=2: zkm-eml, whatsapp, vcard, calendar = N≥4 real consumers — abstraction warranted. But: W10 is one live-run away from done; blocking it on a new core subsystem is scope-inflation. 😈 Riku: throwaway is near-zero (W10's wrapper → `zkm fetch whatsapp` recipe ~verbatim); no real cost to shipping tactical now. Sven flagged the observability gap: wrapper currently `echo`s to stdout (captured by journal) rather than `systemd-cat -t <tag>` (the established project convention from 2026-05-08 mbsync-hook note); centralization is the right home for that fix. User chose: **ship W10 tactically, open a separate core design item for the scheduler**.

**Agenda 4 (closure):** 😈 Riku: `@manual` ≠ green test (relay §2.6); the meeting's design sign-off does NOT close d058. 🛠️ Sven enumerated the 4 live-assertion steps + keyring pre-flight. ✂️ Petra named explicit non-requirements: timer and scheduler are NOT in the closure gate. User confirmed the gate, asked to be walked through the steps directly (covered below). **Pre-install finding**: `zkm-whatsapp-decrypt.sh:25` defaults `WA_REPO=$HOME/src/zkm-whatsapp` — the dev checkout on zomni is `~/src/zkm/plugins/zkm-whatsapp`; override required at install.

## Decisions
- **D1 (timer):** Defer the backstop `.timer` (observe-first). Approve the three units as-is; add no timer now. Revisit only if a real missed-backup is observed. *Out of scope:* shipping/enabling any timer this round.
- **D2 (W10 disposition):** Ship W10's plugin-local systemd units as the tactical answer; install per `scripts/systemd/README.md`, overriding `WA_REPO`. No pre-install code changes required. *Out of scope:* blocking W10 on the scheduler.
- **D3 (scheduler):** Open a new core/cross-cutting **design** item — "unified fetch/schedule orchestrator (`zkm fetch`)" — seeded by the 2026-06-01 `zkm fetch` note, the zkm-eml mbsync precedent (`systemd-cat -t <tag>` observability convention), and this discussion. To decide: core-vs-`zkm-scheduler`-plugin; `ExecStart=zkm fetch <source>` as the uniform systemd target; the `systemd-cat` tagging convention. N=2 passes loudly (N≥4). *Out of scope:* deciding core-vs-plugin now; NOT an executor ticket. W10's wrapper becomes the `zkm fetch whatsapp` recipe ~verbatim when built (near-zero throwaway).
- **D4 (closure):** d058 + REVIEW_ME box stay OPEN. Gate = keyring pre-flight + 4 `@manual` assertions live on zomni. *Out of scope:* design sign-off; timer requirement; scheduler requirement.

## Action items
- [ ] W10 live verification — human runs install + 4-assertion live journey on zomni (Syncthing + `systemd --user`); tick REVIEW_ME box + ROADMAP id:d058 only on pass. Contract: `features/manual.feature` "Auto-decryption trigger" assertions hold. (id:d058 — already tracked in ROADMAP; not a new TODO line.) <!-- id:d058 -->
- [ ] Open "unified fetch/schedule orchestrator (`zkm fetch`)" design item in core (`~/src/zkm/TODO.md`) — routed from this meeting. <!-- id:12fc -->

## Amendment (post-meeting, Opus) — where decryption lives

User asked whether systemd still makes sense given D3, or whether `zkm convert whatsapp --decrypt` or a general core `zkm decrypt` would be more adequate. Resolution (sharpens D3, does not overturn it):

- **systemd stays — but only as the trigger.** Nothing replaces a filesystem watch; a CLI verb can't notice a synced file landing. Post-`zkm fetch`, the watch unit's target flips from the bespoke `zkm-whatsapp-decrypt.sh` to `ExecStart=zkm fetch whatsapp`. The watch unit is permanent; the wrapper is the throwaway prototype.
- **`zkm convert whatsapp --decrypt` — rejected.** Violates the ingest-only fetch boundary (CLAUDE.md:5–7). `convert()` is hermetic + dep-light; decryption needs `wa-crypt-tools` + key resolution + secret access, none of which belong in convert's surface or test suite.
- **General core `zkm decrypt` — rejected as a *general* tool.** crypt15 shares zero mechanism with PGP/age/etc.; no N=2 second consumer of a shared decrypt primitive. But the instinct (a CLI verb owns this, not a loose script) is correct.
- **Resolution — answers D3's open core-vs-plugin fork: BOTH.** Core owns the `fetch` verb + orchestration + config; each **plugin contributes its fetch recipe**. `zkm fetch whatsapp` → (plugin recipe: locate crypt15 → decrypt via `wa_decrypt_pilot` → land at `source_db`) → core optionally chains `zkm convert whatsapp`. Same pattern: `zkm fetch eml` runs mbsync, `zkm fetch vcard` runs vdirsyncer. The D3 design item should adopt this contributor pattern as its starting shape.
- **W10 disposition (D2) unchanged:** install + live-verify the bespoke wrapper now (freshness today); the `@manual` journey re-runs cheaply when `zkm fetch whatsapp` lands and the systemd target flips. The wrapper is explicitly the prototype of the whatsapp fetch recipe.
