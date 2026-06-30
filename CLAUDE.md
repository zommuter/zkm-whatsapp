# zkm-whatsapp

zkm plugin: convert decrypted WhatsApp `msgstore.db` (SQLite) to per-chat-day transcript markdown.

**Store dirs**: `chat/whatsapp/<thread_id>/`
**Fetch boundary**: ingest-only — reads a decrypted `msgstore.db` via `source_db` config.
Decryption (crypt15 → plain SQLite) is a separate fetch-role step (see `scripts/wa_decrypt_pilot.py`).

See `ARCHITECTURE.md` for design decisions with rationale and rejected alternatives.
See `ROADMAP.md` for the executor-facing task queue; this repo's `TODO.md` is a stub
pointing at the central ledger (`~/src/zkm/TODO.md`, `W` prefix).

## Commands

```bash
uv sync --extra dev          # dev env; zkm core resolved as editable ../../
uv run pytest                # full suite (hermetic — synthetic SQLite fixtures, no network)
uv run pytest -k <expr>      # one test / one roadmap item's done-check
uv run ruff check <files>    # lint (E, F, I, UP; line-length 100) — keep YOUR files clean
```

## Architecture

```
source_db (msgstore.db) ─┬─ jid map ─────────┐
                         ├─ chat query ──────►│
                         ├─ message query ───►├─ by_chat_day dict
                         ├─ message_quoted ──►│       │
                         └─ message_media ───►│       ▼
                                              convert() → _render_file() → write_atomic()
```

One `chat/whatsapp/<thread_id>/YYYY-MM-DD.md` per chat per day.

- **thread_id** = `sha256(chat_jid.encode())[:16]`
- **message_id** (body-level) = `whatsapp:<chat_jid>:<key_id>` — protocol-level stable ID
- **Dedup key** = `key_id` in the `messages:` manifest (not rowid, not content hash)
- **Source state** = `.zkm-state/zkm-whatsapp.json` — timestamp watermark per `source_db`

## Key decisions (from 2026-06-03-0952-zkm-whatsapp-scope.md)

- **SQLite parser only** — stdlib `sqlite3`, zero extra DB deps.
- **Deterministic emission** — sort by `(timestamp, key_id)`, fixed sentinels (`«deleted»`).
- **Revoked messages** → `«deleted»` in body; manifest entry keeps `status: revoked` + `key_id`.
- **Replies** → `↩ (re: <quoted_key_id>)` prefix from `message_quoted` table.
- **Media** (W6) → `write_object()` into CAS at `chat/whatsapp/<tid>/originals/_objects/`.
- **Source state** convention documented in `docs/plugin-spec.md`; shared module deferred to 3rd consumer.

## Development setup

```bash
cd plugins/zkm-whatsapp
uv sync --extra dev
uv run pytest
```

## Gotchas (hard-won; do not rediscover)

- **Plugin dir lands on `sys.path`** (convert.py inserts it so `state` imports work
  under zkm's importlib loader). Consequence: NEVER name a module here after a stdlib
  module (`secrets.py`, `json.py`, …) — it would shadow stdlib for everything imported
  afterwards. That's why the key-resolution module is `keysource.py`.
- **Tests are hermetic + published-generic**: synthetic SQLite fixtures built in
  `tmp_path` (`tests/conftest.py:_create_test_db`), placeholder phone numbers only
  (`4179111…`), no network, no `~/knowledge`, no real msgstore.db. The committed
  `tests/fixtures/msgstore.db` exists only for `plugin.yaml` `conformance.config`
  (core conformance suite) and is synthetic too.
- **`_reconstitute()` rebuilds messages from the manifest only** — anything not
  persisted in the `messages:` manifest is LOST when a day file is rewritten for new
  same-day messages. Verified 2026-06-12: text bodies, reply prefixes AND media lines
  all blank out on rewrite (worse than the central-ledger w6f note, which mentions
  media only). Fix = roadmap id:w6f (persist text/quoted/media in the manifest).
  When extending the manifest schema, keep `_load_existing_manifest` backward-readable.
- **Watermark is a speed optimisation only** — correctness comes from key_id dedup.
  Deleting `.zkm-state/zkm-whatsapp.json` is always safe.
- **WAL tests can self-skip**: some SQLite builds checkpoint on close; WAL-specific
  tests detect that and `pytest.skip` — a skip there is not a failure.
- **OS / tooling**: Manjaro — `pamac`, never `pacman -S`. Python via `uv` only.

## Schema compatibility note

Written against the v5+ msgstore.db schema (jid table separate from chat). The `revoked`
column is detected via `PRAGMA table_info`; `message_quoted` and `message_media` are probed
with `sqlite_master`. Absent tables are skipped gracefully.

**WAL handling (W9):** A live `msgstore.db` runs in WAL journal mode. `convert()` calls
`_wal_safe_source()`: if a non-empty sibling `-wal` exists, the db + `-wal` + `-shm`
trio is copied to a tempdir, checkpointed (TRUNCATE) there, and the copy is read instead.
The original source file is **never written**. The temp copy is removed in a `finally` block.
State keys remain on the original `source_db` path, so the watermark is unaffected.

## Incremental backups (W9 design note)

WhatsApp writes daily encrypted snapshots (`msgstore-YYYY-MM-DD.N.db.crypt15`) to its
backup directory. These are **not** ingested automatically — they require the same
fetch-role decryption step as the main `msgstore.db` (out of plugin scope).

**Why multi-source ingest is safe when you want it:** dedup is on `key_id` (`convert.py:303-310`
`new_by_key`/`existing` merge), and the watermark in `.zkm-state/zkm-whatsapp.json` is keyed
by **absolute `source_db` path** (`state.py:18`). The watermark is a speed optimisation only —
correctness comes from the dedup; the watermark can be 0 for a fresh run without data loss.

**Multi-source recipe (manual, future):** decrypt each backup file, then for each decrypted
`.db` (oldest-first), point `source_db` at it and run `zkm convert whatsapp`. Overlapping
messages from the main DB and backups collapse on `key_id` automatically.

**Automatic multi-source iteration** is deferred. Trigger: a concrete need to recover messages
absent from the current `msgstore.db` (e.g. after a phone wipe / re-install gap).

## Relay contract <!-- relay-executor contract v6 -->

This repo is managed by a reviewer/executor relay. Load `/relay executor` before
working on any item, then follow its rules exactly.
