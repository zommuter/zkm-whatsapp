# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-12 21:26 — reviewer (claude-fable-5)

Handoff: CLAUDE.md refresh + ARCHITECTURE.md; ROADMAP 3 ROUTINE + 4 HARD (w6f day-file rewrite blanks ALL prior bodies — verified worse than ledger note; W8 owner JID f5b7; W11 number-change; W10 d058 gated); 12 red spec tests on synthetic SQLite fixtures; @manual Gherkin; 6 REVIEW_ME entries. C5 shipped W-key: keysource.py resolves bitwarden:<id>/keyring:<svc>:<acct>, wa_decrypt_pilot.py --key-source, 12 tests, no key material on disk.

## 2026-06-12 — executor (sonnet)

Worked id:w6f — fixed day-file rewrite data loss by persisting `text`, `quoted_key_id`, and `media: {mime, sha256}` in manifest entries (`_render_file`) and recovering them in `_reconstitute` (thread_id kwarg added to re-derive cas_rel). All 6 `test_rewrite_persistence.py` tests now pass; full suite green on prior-green tests, no regressions. Friction: tests cannot run via `uv run` from the worktree (relative `../../` zkm editable path fails outside the repo tree); ran via `.venv/bin/python -m pytest` from worktree root instead — works fine.

## 2026-06-12 23:13 — executor (sonnet, relay-loop)

feat(convert): persist text/quoted/media in manifest to fix rewrite data loss (id:w6f) — all 6 test_rewrite_persistence tests now pass
