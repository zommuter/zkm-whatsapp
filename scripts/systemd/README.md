# Auto-decrypt + convert (systemd --user example)

Event-driven automation: when your synced WhatsApp backup folder changes, decrypt the
latest `msgstore.db.crypt15` into the zkm inbox `source_db` and run `zkm convert whatsapp`,
so transcripts stay current with no manual step.

Pieces:

| File | Role |
|---|---|
| `zkm-whatsapp-decrypt.sh` | Wrapper: decrypt (via `scripts/wa_decrypt_pilot.py`) → atomic-rename into `source_db` → `zkm convert whatsapp`. Idempotent (newer-than guard), `flock`'d. Configurable via `WA_*` env. |
| `zkm-whatsapp-decrypt.service` | `oneshot` that runs the wrapper. |
| `zkm-whatsapp-decrypt.path` | Watches the backup folder (`PathModified`) and triggers the service on change. |

## Setup

1. **Store the backup key in the OS keyring** (libsecret — never on disk), same scheme as
   e.g. mbsync's `PassCmd`:
   ```bash
   secret-tool store --label="whatsapp backup key" service zkm/whatsapp account backup
   ```
   The wrapper resolves it via `--key-source keyring:zkm/whatsapp:backup`.

2. **Install the wrapper** and make it executable:
   ```bash
   install -m755 zkm-whatsapp-decrypt.sh ~/.local/bin/zkm-whatsapp-decrypt.sh
   ```
   Edit the `WA_*` defaults (backup path, `source_db`, keyring ref, store root) or set them
   as `Environment=` lines in the `.service`. **`WA_REPO` defaults to `$HOME/src/zkm-whatsapp`**
   (standalone checkout); if the plugin lives inside the zkm monorepo
   (e.g. `~/src/zkm/plugins/zkm-whatsapp`), you **must** override it:
   `Environment=WA_REPO=%h/src/zkm/plugins/zkm-whatsapp`.

3. **Install + enable the units**:
   ```bash
   cp zkm-whatsapp-decrypt.{service,path} ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now zkm-whatsapp-decrypt.path
   systemctl --user start zkm-whatsapp-decrypt.service   # optional: run once now
   ```

## Notes

- **`wa-crypt-tools`** is required by `wa_decrypt_pilot.py` but is intentionally *not* a
  plugin dependency (decryption is out of `convert()` scope); the wrapper provides it
  ephemerally via `uv run --with wa-crypt-tools` (fetched + cached on first run).
- **`--no-amenders`** keeps an unattended run from blocking on a local amender/expand model.
  Run a full `zkm convert whatsapp` by hand when you want amendments inline.
- **Keyring under `systemd --user`** works when your login session exposes the Secret
  Service (the same precondition as any `--user` job using `secret-tool`).
- **`PATH`** under `systemd --user` is minimal; set `ZKM_BIN` to an absolute path (e.g.
  `~/.local/bin/zkm`) if `zkm` isn't found.
- **Backstop:** if you prefer time-based to event-based (or as a safety net), add a
  `.timer` with `OnCalendar=daily` + `Persistent=true` pointing at the same `.service` —
  the wrapper's newer-than guard makes redundant ticks no-ops.
