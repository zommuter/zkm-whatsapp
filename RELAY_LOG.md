# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-12 21:26 — reviewer (claude-fable-5)

Handoff: CLAUDE.md refresh + ARCHITECTURE.md; ROADMAP 3 ROUTINE + 4 HARD (w6f day-file rewrite blanks ALL prior bodies — verified worse than ledger note; W8 owner JID f5b7; W11 number-change; W10 d058 gated); 12 red spec tests on synthetic SQLite fixtures; @manual Gherkin; 6 REVIEW_ME entries. C5 shipped W-key: keysource.py resolves bitwarden:<id>/keyring:<svc>:<acct>, wa_decrypt_pilot.py --key-source, 12 tests, no key material on disk.

## 2026-06-12 — executor (sonnet)

Worked id:w6f — fixed day-file rewrite data loss by persisting `text`, `quoted_key_id`, and `media: {mime, sha256}` in manifest entries (`_render_file`) and recovering them in `_reconstitute` (thread_id kwarg added to re-derive cas_rel). All 6 `test_rewrite_persistence.py` tests now pass; full suite green on prior-green tests, no regressions. Friction: tests cannot run via `uv run` from the worktree (relative `../../` zkm editable path fails outside the repo tree); ran via `.venv/bin/python -m pytest` from worktree root instead — works fine.

## 2026-06-12 23:13 — executor (sonnet, relay-loop)

feat(convert): persist text/quoted/media in manifest to fix rewrite data loss (id:w6f) — all 6 test_rewrite_persistence tests now pass

## 2026-06-13 — executor (sonnet)

Worked id:f5b7 — added `_detect_owner_jid(con)` helper (most-frequent attributed from_me sender query); convert() resolves owner_jid from config first, auto-detect second, default fallback third; plugin.yaml `owner_jid` set to `required: false` with updated description; all 4 test_owner_jid.py tests pass.
Worked id:w11 — added `has_number_change_table` probe and LEFT JOIN on `message_system_number_change` in `_query_messages`; messages with nc rows get `number_change: {old, new}` dict; `_render_file` renders `«number change: old → new»` body and persists `status: system` + `number_change` in manifest; `_reconstitute` recovers number_change from manifest so lines survive rewrites; all 4 test_number_change.py tests pass; full suite 49 passed 1 skipped (pre-existing WAL skip), zero regressions.
Friction: none.

## 2026-06-13 10:02 — executor (sonnet, relay-loop)

executor (sonnet): owner_jid auto-detect (id:f5b7) + number-change system events (id:w11) — 8 new spec tests pass, full suite 49 passed 1 skipped

## 2026-06-13 14:59 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260613-1450: 1 docs-only commit audited clean, 49 tests green, acted on owner REVIEW_ME decisions (w6f/D5 conditional-pattern doc, w11/cfd1 reopened as message_type rename), contract pointer v1→v2

## 2026-06-13 — executor (sonnet)

Worked id:cfd1 — renamed manifest field `status: system` → `message_type: system` for number-change entries. In `_render_file`, number-change entries now set `message_type: "system"` (messaging-namespaced) rather than `status: "system"` (core-owned iCal enum). `_reconstitute` now detects system events via `entry.get("message_type") == "system"` and only recovers `number_change` dict for such entries. Updated `test_number_change_manifest_entry` per ROADMAP spec: asserts `entry["message_type"] == "system"` and `entry.get("status") != "system"`. Full suite 49 passed 1 skipped, zero regressions.
Friction: none.

## 2026-06-13 15:24 — executor (sonnet, relay-loop)

feat(convert): rename manifest status:system → message_type:system (id:cfd1) — 49 passed 1 skipped

## 2026-06-13 23:17 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260613-2304: 1 commit audited clean (REVIEW_ME triage), 49 tests green, 0 open [ROUTINE], pruned 2 boxes + fixed stale TODO count

## 2026-06-15 11:04 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260615-1104: 3 commits since fable-ckpt-20260613-2317 audited — 2 REVIEW_ME triage + 1 feat (systemd --user auto-decrypt units, id:d058 W10). No test files added/deleted/modified in window → test-integrity audit clean by construction; full suite 49 passed 1 skipped (pre-existing WAL env skip, not a gate). W10 BUILT (scripts/systemd/zkm-whatsapp-decrypt.{sh,service,path}+README: .path watcher → idempotent flock'd decrypt via --key-source keyring → zkm convert --no-amenders; journal-visible, no retry loop) but HELD OPEN: [HARD]+@manual-only journey is not a green pass (review §2.6) — needs human unit review + live Syncthing/systemd run; re-scoped d058 with Status note, relabelled features/manual.feature scenario, new REVIEW_ME d058 box. Spec-drift: added Automated-ingestion section to README (systemd units were undocumented). Refreshed stale CLAUDE.md relay-contract pointer v2→v3 (fables-executor→/relay executor). No §5b additions (TODO/ROADMAP unchanged in window). 0 open [ROUTINE]; 3 open [HARD] (d058 built-pending-verify, 367f, bf12).

## 2026-06-15 11:22 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260615-1104: 3 commits audited clean (test-integrity trivially clean, 49 pass/1 env-skip); W10/d058 built but held @manual-pending; pointer v2→v3; README systemd doc

## 2026-06-16 21:31 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260615-1122 (a33eb84 W10/d058 meeting): clean gaming-scan, 49 pass/1 skip; refreshed contract pointer v3→v4, documented WA_REPO override; 0 open ROUTINE

## 2026-06-16 22:02 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited docs-only D3 amendment (e585e93); suite green (49 pass/1 skip), no gaming, ledger consistent, 0 open ROUTINE

## 2026-06-16 19:57 — reviewer (claude-opus-4-8, relay-20260616-195707-28479)

review since relay-ckpt-20260616-2202 (333b9c1 close W10/d058; 8e03cf2 systemd start-limit fix). Diff window touched only docs/ledger + the `.service` unit — no Python source/test changed; gaming-scan clean; suite 49 pass/1 skip (pre-existing WAL skip, unrelated to d058). VERIFIED-GREEN id:d058 (W10 auto-decrypt): closed legitimately on a human-confirmed `@manual` live journey on zomni (4 assertions + journal evidence + a real defect caught & fixed), NOT on a skipped/unverified test — the correct path for a `[HARD]` @manual item. The `StartLimitIntervalSec=0` fix (8e03cf2) is mechanically sound (key belongs in `[Unit]`, guards are the idempotency layer). Spec-drift fixes this turn: documented the burst/start-limit rationale in `scripts/systemd/README.md` Notes, and updated the `features/manual.feature` d058 scenario title (built→VERIFIED) plus added the burst-no-op assertion. Pruned the resolved d058 REVIEW_ME box. Contract pointer already v4 (canonical). ROADMAP: 2 open items, both genuinely `[HARD]`+gated (367f segmentation design, bf12 new-number heuristic) — 0 open ROUTINE; TODO id:a006 stub count (2) consistent. No reverse-handoff items added this window. routine_open=0.

## 2026-06-16 22:43 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260616-2202: d058 closed genuinely (human @manual live journey), start-limit fix sound, gaming-scan clean, 49 pass/1 skip; spec-drift docs fixed; 0 open ROUTINE

## 2026-06-21 16:26 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260616-2243 (single commit a7d80f1 "chore: sync uv.lock to zkm 0.15.0"). Diff window touched ONLY `uv.lock` — the editable parent-dep pin bumped 0.14.0→0.15.0; no Python source, test, doc, or BDD change. gaming-scan clean (no DELETED_TEST/ADDED_SKIP/REMOVED_ASSERT). Suite 49 pass / 1 skip (pre-existing WAL-checkpoint env skip in test_convert.py:255, unrelated to this window) — run in the real checkout because the worktree's `../../` editable zkm path can't resolve outside the repo tree (known worktree artifact, same friction noted by past executors). No spec drift: README/ARCHITECTURE/CLAUDE unaffected by a lockfile-only change; contract pointer already v4 (canonical). No reverse-handoff items added this window (only commit is the chore). ROADMAP unchanged: 2 open items, both genuinely `[HARD — strong model]` + explicitly gated (367f segmentation design note — gated on v1-live + retrieval pain; bf12 new-number heuristic — gated on w11 shipped + a real missed case + Phase-4 alias design). 0 open ROUTINE; TODO id:a006 stub count (2 open HARD, gated) consistent. routine_open=0. Nothing to verify-green this window (no item state changed); no flags, no reopens.

## 2026-06-21 16:26 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260616-2243: 1 lockfile-only commit (uv.lock zkm 0.14→0.15), gaming-scan clean, 49 pass/1 skip, no source/doc/test change, no drift; 2 open HARD-gated items, 0 open ROUTINE

## 2026-06-21 17:15 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260616-2243: 1 lockfile-only commit (uv.lock zkm 0.14→0.15), gaming-scan clean, 49 pass/1 skip, no source/doc/test change, no drift; 2 open HARD-gated, 0 open ROUTINE

## 2026-06-22 — reviewer (claude-opus-4-8, relay-loop)

Reviewed 1 commit since relay-ckpt-20260621-1715 (4e89ebb, docs-only): meeting-note
token alignment `<!-- id:12fc -->` → `<!-- routed:12fc -->` on the routed
fetch-orchestrator action item so orphan-scan skips it by design (it lives in the core
inbox, not this repo's TODO). Verified: gaming-scan clean (no DELETED_TEST/ADDED_SKIP/
REMOVED_ASSERT); no code/test changes in window; full suite 49 passed, 1 skipped
(pre-existing WAL-path skip, not a window pass); orphan-scan correlates clean; relay
contract pointer at v4 (current, no drift); no TODO/ROADMAP additions to qualify (§5b).
The 12fc token now appears only in the meeting note with the `routed:` prefix — fix is
genuine and achieves its stated purpose. No items closed (window has no executor work);
ROADMAP unchanged: 2 open [HARD] (id:367f W7 segmentation, id:bf12 W11b informal-number
heuristic), 0 open [ROUTINE]. Worktree `uv run` fails on the relative editable zkm dep
(known friction, line 9) — ran tests in the main checkout (read-only) instead.

## 2026-06-22 01:03 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

Reviewed docs-only token-alignment commit (4e89ebb); gaming-scan clean, suite green (49/1 skip), no items closed; ROADMAP unchanged (2 HARD, 0 ROUTINE)

## 2026-06-22 16:01 — reviewer (claude-opus-4-8, relay-loop)

Reviewed 1 commit since relay-ckpt-20260622-0103 (4d4c045, ROADMAP-only): the id:78ff
[HARD] explicit-lane-tag migration. Both open HARD items retagged `[HARD — strong model]`
→ `[HARD — meeting]` (id:367f W7 segmentation design-note; id:bf12 W11b informal
new-number heuristic) — both correct meeting-lane classifications (367f is design-only
and gated on v1+retrieval-pain; bf12 needs a non-existent human-confirmation flow +
multi-language false-positive judgment, gated on id:w11). The two already-closed [x] HARD
items keep their historical `[HARD — strong model]` tags (correct — completed under the
old scheme, never rewritten). Verified: gaming-scan clean (no DELETED_TEST/ADDED_SKIP/
REMOVED_ASSERT); no code/test change in window; no formerly-red→green transitions to
audit; relay contract pointer at v4 (current); §5b reverse-handoff — the two `+- [ ]`
lines are retags of pre-existing ids, not new unqualified work, so nothing to qualify.
No items closed; ROADMAP unchanged in count: 2 open [HARD — meeting], 0 open [ROUTINE].

## 2026-06-22 16:27 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260622-0103: 1 ROADMAP-only commit (id:78ff HARD lane-tag migration to [HARD — meeting]), gaming-scan clean, no code/test change, contract pointer v4 current; 2 open [HARD — meeting], 0 open [ROUTINE]

## 2026-06-22 21:26 — maintenance (manual, uv.lock cascade)

uv.lock cascade refresh to zkm 0.16.0 — mechanical version-pin only (id:bae5), audit-exempt class (no code/spec change).

## 2026-06-23 08:32 — reviewer (claude-opus-4-8, relay-loop)

review since relay-ckpt-20260622-2126: 2 manual feat commits (v0.4.0 media_root id:1c7d, v0.5.0 reprocess backfill id:4b8e). gaming-scan clean; suite 54 passed / 1 skipped (pre-existing WAL skip, not gaming). Test-integrity audit PASSED — both features genuinely green: `test_media_root.py` asserts real CAS object bytes + manifest `media.sha256`/`mime` (media_root) and non-destructive text-preservation + heal + idempotency + no-op-without-root (reprocess); no deleted tests / added skips / weakened asserts; no fixture special-casing; `reprocess()` conforms to core's `run_reprocess` shape (conformance.py ≥3 positional + `progress` kwarg, verified wired in core cli.py). Reverse-handoff (D6): both ids already tracked + closed `[x]` in central `~/src/zkm/TODO.md` (W12 id:1c7d, W13 id:4b8e) — mirrored them into this repo's ROADMAP.md as closed (single-id-two-views, reused central tokens, no mint). Spec-drift FIXED inline: README gained `media_root` config + `--reprocess-all` usage; ARCHITECTURE Media section gained media_root path-resolution + reprocess backfill subsections (both were undocumented user-facing surface). Contract pointer v4 current. Note: central also filed id:b7e2 (CAS processed-by-version tracking) — a zkm-core design item, stays central, not whatsapp roadmap. 0 open [ROUTINE]; 2 open [HARD — meeting] (W7 id:367f, W11b id:bf12, both still gated).

## 2026-06-23 08:46 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: verified v0.4.0 media_root (id:1c7d) + v0.5.0 reprocess backfill (id:4b8e) genuinely green, closed both in ROADMAP, fixed README+ARCHITECTURE drift

## 2026-06-23 08:56 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: verified docs-only merge-old-backup runbook (8c66c52) accurate vs code; no gaming/drift; 55 passed/1 skipped; 0 open ROUTINE

## 2026-06-23 09:37 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited v0.7.0 fail-loud-on-bad-decrypt fix (ab4e6a4) — genuine, gaming-scan clean, 56 pass/1 pre-existing skip; no reopen, routine_open=0
