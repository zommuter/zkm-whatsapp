# zkm-whatsapp

zkm plugin: convert decrypted WhatsApp `msgstore.db` (SQLite) to per-chat-day transcript markdown.

**Store dirs**: `chat/whatsapp/<thread_id>/`
**Fetch boundary**: ingest-only — reads a decrypted `msgstore.db` via `source_db` config.
Decryption (crypt15 → plain SQLite) is a separate fetch-role step (see `scripts/wa_decrypt_pilot.py`).

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

## Schema compatibility note

Written against the v5+ msgstore.db schema (jid table separate from chat). The `revoked`
column is detected via `PRAGMA table_info`; `message_quoted` and `message_media` are probed
with `sqlite_master`. Absent tables are skipped gracefully.
