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
