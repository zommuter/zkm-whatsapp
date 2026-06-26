# zkm-whatsapp

A converter plugin for [**zkm** — ze knowledge manager](https://github.com/zommuter/zkm):
turns a decrypted WhatsApp `msgstore.db` (SQLite) into per-chat-day transcript markdown
in your zkm store.

## Installation

This is a zkm plugin — install [zkm](https://github.com/zommuter/zkm) first, then add this
plugin by either path:

```bash
# Released wheel (end-user): resolved into zkm's sealed env
uv tool install zkm --with zkm-whatsapp

# Dev / local: clone + register against a source checkout of zkm
git clone https://github.com/zommuter/zkm-whatsapp.git
zkm plugin add ./zkm-whatsapp
```

Verify it is discovered: `zkm plugin list` should show `whatsapp`.

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

The transcripts can stay current with zero manual steps. The setup I run:

1. **[Syncthing](https://syncthing.net/)** mirrors the phone's WhatsApp backup folder
   (the daily `msgstore-YYYY-MM-DD.N.db.crypt15` snapshots) to a folder on the host —
   no cloud, no cables.
2. A **`systemd --user` `.path` unit** watches that folder and, on change, fires a
   `oneshot` service running an idempotent, `flock`'d wrapper: decrypt the newest snapshot
   → atomic-rename into the configured `source_db` → `zkm convert whatsapp`.
3. The backup **key lives in the OS keyring** (libsecret), never on disk — the wrapper
   resolves it via `--key-source keyring:<service>:<account>`.

The wrapper's newer-than guard + `flock` make redundant fires cheap no-ops (a Syncthing
sync arrives as a burst), so the watcher is safe to leave running. Full unit files,
the wrapper, and setup steps are in [`scripts/systemd/README.md`](scripts/systemd/README.md).
