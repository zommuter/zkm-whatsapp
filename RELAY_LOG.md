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
