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
```

## Usage

```bash
zkm convert whatsapp
```

Produces `chat/whatsapp/<thread_id>/YYYY-MM-DD.md` files — one per chat per day.
