# zkm-whatsapp

zkm plugin: convert decrypted WhatsApp `msgstore.db` to per-chat-day transcript markdown.

## Prerequisites

The plugin reads a **decrypted** `msgstore.db` (SQLite). Decryption from the `.crypt15` backup
is an out-of-scope fetch step — use `wa-crypt-tools` or equivalent, e.g. the bundled pilot:

```bash
# key from a chmod-0600 file…
uv run python scripts/wa_decrypt_pilot.py keyfile msgstore.db.crypt15 msgstore.db
# …or from a secret agent (never touches disk):
uv run python scripts/wa_decrypt_pilot.py --key-source bitwarden:<item-id> msgstore.db.crypt15 msgstore.db
uv run python scripts/wa_decrypt_pilot.py --key-source keyring:whatsapp:backup msgstore.db.crypt15 msgstore.db
```

## Configuration

In `$ZKM_STORE/zkm-config.yaml`:

```yaml
whatsapp:
  source_db: /path/to/decrypted/msgstore.db
  owner_jid: 41791234567@s.whatsapp.net
  timezone: Europe/Zurich    # optional, default: Europe/Zurich
  media_root: /path/to/WhatsApp    # optional; the dir holding Media/
```

`msgstore.db` stores media (images, voice notes, …) as paths **relative** to the
WhatsApp data dir (e.g. `Media/WhatsApp Voice Notes/…/x.opus`). Set `media_root` to
that dir (the parent of `Media/`) so those files resolve into CAS; without it, media
is emitted as a bare `[media: <mime>]` placeholder with no stored bytes (and
downstream transcription/amenders have nothing to consume).

## Usage

```bash
zkm convert whatsapp
```

Produces one transcript file per chat per day, plus voice/video **call-log** entries
inline in the same per-day transcript.

### Output layout

```
chat/whatsapp/
├── by-id/<thread_id>/YYYY-MM-DD.md      # canonical — opaque, stable thread_id
│   └── originals/_objects/…             # media stored in CAS
└── by-name/<label>/ → ../../by-id/<thread_id>/   # regenerable human-readable view
```

- **`by-id/`** is canonical: `thread_id = sha256(chat_jid)[:16]`, stable across runs.
- **`by-name/`** is a convenience symlink view keyed by display name, rebuilt on every
  convert run. It is regenerable — safe to delete, gitignored.

To backfill media into day-files that were ingested **before** `media_root` was set
(they carry bare `[media: <mime>]` placeholders), run:

```bash
zkm convert whatsapp --reprocess-all
```

This is surgical and non-destructive: for each existing day-file it re-derives media
from the DB by `key_id`, stores any not-yet-ingested file into CAS, and patches only
the manifest `media:` entry and the matching `[media: …]` body line — message text
and everything else are preserved byte-for-byte. Idempotent (skips messages already
carrying `media.sha256`) and a no-op without `media_root`.

## Automated ingestion (optional)

To decrypt + convert automatically whenever a synced backup folder changes, see
`scripts/systemd/README.md` — a `systemd --user` `.path` unit watches the backup folder
and runs an idempotent, `flock`'d decrypt → `zkm convert whatsapp` wrapper (key resolved
from the OS keyring via `--key-source keyring:<service>:<account>`).
