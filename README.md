# zkm-whatsapp

zkm plugin: convert decrypted WhatsApp `msgstore.db` to per-chat-day transcript markdown.

## Prerequisites

The plugin reads a **decrypted** `msgstore.db` (SQLite). Decryption from the `.crypt15` backup
is an out-of-scope fetch step — use `wa-crypt-tools` or equivalent.

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
