# zkm-whatsapp architecture

Design decisions with rationale and rejected alternatives. Scope meeting:
`~/src/zkm/docs/meeting-notes/2026-06-03-0952-zkm-whatsapp-scope.md`.

## Boundary: ingest-only, decryption is fetch-role

The plugin reads an already-**decrypted** `msgstore.db` (`source_db` config). Decrypting
`msgstore.db.crypt15` happens outside `convert()` (pilot: `scripts/wa_decrypt_pilot.py`
using wa-crypt-tools).

- **Rationale**: keeps secrets out of the convert path; `zkm convert whatsapp` stays
  deterministic and hermetically testable; wa-crypt-tools is a heavy optional dep that
  must not burden the plugin install.
- **Rejected**: in-plugin decryption (would force the 64-char hex backup key through
  plugin config and make every convert run touch secret material).
- Key *resolution* for the fetch step lives in `keysource.py` (`bitwarden:` /
  `keyring:` schemes via subprocess) — see "Secrets" below.

## Parser: stdlib sqlite3, schema-probed

All reads go through `sqlite3` from the stdlib; optional schema features are probed
(`PRAGMA table_info` for the `revoked` column, `sqlite_master` for `message_quoted`,
`message_media`, `group_participant_user`) and degrade gracefully when absent.

- **Rationale**: zero extra DB deps; msgstore.db schema drifts across WhatsApp versions,
  so probing beats pinning one schema version.
- **Rejected**: SQLAlchemy/ORM (dependency weight, no benefit for read-only queries);
  hard-coding one schema version (breaks silently on older/newer backups).

## Segmentation: one file per chat per day

Output is `chat/whatsapp/by-id/<thread_id>/<YYYY-MM-DD>.md` (the `by-id/` canonical — see
"Folder naming" below for the by-id/by-name split, shipped 2026-06-25).

- **Rationale**: bounded file size, stable paths, natural temporal granularity for the
  git-as-temporal-index model; day boundary is computed in the configured (or system)
  timezone.
- **Rejected**: one file per thread (unbounded growth, constant rewrite churn defeats
  git diffing); one file per message (inode explosion, useless retrieval granularity).
- **Future (W7, gated)**: smarter burst/temporal-density re-segmentation must be
  *additive* and MUST NOT rewrite chat-level `thread_id`.

## Folder naming: opaque canonical + regenerable name view (IMPLEMENTED id:058c + id:8040; 2026-06-25)

Meeting `~/src/zkm/docs/meeting-notes/2026-06-25-1536-human-readable-chat-folder-names.md`.
Shipped 2026-06-25 (seams id:058c canonical move + id:8040 name view). The live `~/knowledge`
store migration + zkm-stt path lockstep remains the `[HARD — hands]` seam id:da9f. The layout:

- **Canonical** stays the opaque `thread_id` but moves under a `by-id/` subdir:
  `chat/whatsapp/by-id/<thread_id>/<YYYY-MM-DD>.md` (+ `…/by-id/<thread_id>/originals/_objects/…`).
  Stable: it is the dedup anchor, the git-history anchor, and the media-CAS root, and
  **zkm-stt writes voicemail transcripts against it** — so it must not churn.
- **Browsable view** is a regenerable, **gitignored** symlink tree:
  `chat/whatsapp/by-name/<label>/<leaf> → ../../by-id/<thread_id>/`, rebuilt every convert run.
  `<label>` is derived mechanically from frontmatter (group subject / DM contact name) with
  fallbacks (`«group»` / phone number), slug-sanitised, UTF-8 kept. `<leaf>` is the phone
  number (DM) / group-short-id — unique, so a number-changed contact and two distinct
  same-named contacts coexist as separate symlinks with **no merge claim**.
- **Rationale**: renames re-point a symlink → zero git-history churn; mirrors the inbox
  CAS+symlink split. Browsability without baking a mutable name into the dedup/CAS root.
- **Rejected**: (A) slug+hex canonical `chat/whatsapp/<slug>-<short-id>/` — bakes a name into
  the CAS root, slug churns or goes stale on rename; (C) rename canonical on identity
  resolution — churns git, breaks `git log --follow`, stales baked CAS paths, violates W7
  (id:367f "MUST NOT rewrite thread_id").
- **Out of scope (Layer 2, deferred)**: aggregating multiple threads into one *person*
  (number change = same human) — manual identity layer (NER person pages / `same-as` map,
  Phase 3). The plugin makes **no** identity guesses. `message_system_number_change`
  (already captured, id:w11) is the future hook.
- **Cross-repo**: the `messaging-spec.md` layout change (Telegram/Signal/Threema inherit)
  lives in the zkm core repo; the live `~/knowledge` store migration + zkm-stt path lockstep
  is the `[HARD — hands]` seam id:da9f.

## Identity: key_id everywhere

- `thread_id = sha256(chat_jid)[:16]` — **rejected**: raw JID in paths (phone numbers in
  filenames violate the published-generic policy and leak PII into git paths).
- `message_id = whatsapp:<chat_jid>:<key_id>` — protocol-level `key_id` is stable across
  devices and WA-Web, enabling future merge with WA-Web exports.
- **Dedup key = `key_id`** in the per-file `messages:` manifest. **Rejected**: rowid
  (renumbers across backup-restore) and content hash (revoked/edited messages mutate).

## Source state: watermark as optimisation only

`.zkm-state/zkm-whatsapp.json` maps absolute `source_db` path → `watermark_ms`
(max imported timestamp). Correctness always comes from key_id dedup; the watermark only
limits the query. Deleting the state file is safe; multi-source ingest (daily backup
snapshots) works by pointing `source_db` at each decrypted snapshot oldest-first.

## Day-file rewrite + manifest reconstitution (v1 flaw FIXED → id:w6f)

When new same-day messages arrive, the whole day file is re-rendered: existing messages
are reconstituted from the `messages:` manifest and merged with new rows. Since id:767e
(2026-06-30) the manifest lives in an **end-of-file `<!-- zkm:manifest … -->` footer**
(moved out of the frontmatter to keep short-chat frontmatter ≤10 lines);
`_load_existing_manifest` reads the footer first with a frontmatter fallback for
pre-767e files. The v1
manifest stored only `key_id/timestamp/sender_jid/status`, so a rewrite **blanked text
bodies, reply prefixes and media lines** of prior messages (verified 2026-06-12 —
broader than the original media-only observation). Fixed in the w6f turn.

- **Fix (shipped)**: persist `text`, `quoted_key_id` and `media: {mime, sha256}`
  in manifest entries so reconstitution is lossless and the file is self-contained.
  The CAS path is derivable from sha256 (`originals/_objects/<sha[:2]>/<sha[2:]>`).
- **Rejected**: re-querying the DB without watermark for affected days (loses messages
  that exist only in older backup snapshots, breaking the multi-source dedup design);
  parsing body lines back (fragile round-trip through rendered markdown).
- Backward compat: `_load_existing_manifest` must keep reading old manifests without
  the new keys (their bodies stay blank — healing old files is out of scope).
- **Manifest `text:` duplication is a *conditional* pattern, not a store-wide default**
  (owner decision 2026-06-13, frontmatter-schema mtg D5): blessed here ONLY because
  (a) the WhatsApp source is ephemeral — no durable original to re-read — AND (b) the
  manifest is the rewrite source-of-truth. ~2× message-text disk is accepted; no new
  privacy exposure (text already lives in the same `.md` body). Pre-fix blanked files
  are NOT auto-healed; a watermark-less `--full-resweep` heal is queued centrally as
  `~/src/zkm/TODO.md` id:8d67. The conditional-pattern write-up belongs in core
  `plugin-spec.md` (tracked there).

## Manifest `status:` vs `message_type:` (id:cfd1, owner decision 2026-06-13)

`status:` is **core-owned** — reserved for the iCal lifecycle enum used by zkm-calendar.
The W11a number-change feature currently writes `status: system`, which collides with
that enum. Per the frontmatter-schema meeting, the WhatsApp system-event marker moves to
a messaging-namespaced field `message_type: system` (the `«number change»` body rendering
is unchanged). Open ROADMAP item id:cfd1 mirrors central `~/src/zkm/TODO.md` id:cfd1
(cross-plugin D2/D3 namespacing + `messaging-spec.md` reconciliation).

## Media: CAS + inbox symlink + sidecar (W6)

Media files go to `chat/whatsapp/by-id/<tid>/originals/_objects/` via core `zkm.cas.write_object`
(content-addressed, idempotent); a human-browsable symlink + `.origin.json` producer
sidecar lands in `inbox/whatsapp/<tid>/` via `zkm.inbox.symlink_with_sidecar`.

- **Rationale**: single core implementation of the object-storage contract
  (`~/src/zkm/docs/object-storage.md`); dedup across re-runs for free.
- **Rejected**: copying media next to the day file (duplicates on rewrite, no dedup).

### Path resolution: `media_root` (v0.4.0)

`message_media.file_path` is stored **relative** to the WhatsApp data dir (e.g.
`Media/WhatsApp Voice Notes/…/x.opus`), so a bare `.exists()` against cwd never
resolved — media was silently skipped. `_resolve_media_path(raw, media_root)`: absolute
paths used as-is; relative ones anchored under the optional `media_root` config; cwd
fallback preserved. `_handle_media` returns a bool so `convert()` can count stored-vs-missing
and log an actionable summary (no longer silent). A store failure on a *resolved* file is
now logged per-item (`exc_info`), distinct from "file absent" — replacing the old
`except Exception: pass`.

### Backfill: `reprocess()` (v0.5.0, `--reprocess-all`)

The convert watermark path only CASes media for *newly*-ingested messages, so day-files
written before `media_root` was configured keep bare `[media: <mime>]` placeholders.
`reprocess()` (core's `run_reprocess` passes the managed day-files as `candidates`) heals
them **surgically**: re-derive media from the DB by `key_id`, CAS any not-yet-stored file,
and patch ONLY the manifest `media:` entry and the matching `[media: …]` body line.

- **Non-destructive by design**: message text and all other lines are preserved
  byte-for-byte — this is safe on pre-w6f files that don't persist text in the manifest,
  where a full re-render would blank them.
- **Idempotent** (skips messages already carrying `media.sha256`) and watermark-independent.
  No-op with a clear warning when `media_root` is unset.
- **Rejected**: re-rendering the day-file from the DB (would blank pre-w6f text bodies).

## WAL safety (W9)

A live msgstore.db runs in WAL mode. `_wal_safe_source()` copies db + `-wal` + `-shm`
to a tempdir and checkpoints (TRUNCATE) the *copy* when a non-empty `-wal` exists; the
original is never written.

- **Rejected**: opening the source read-only (SQLite may still recover/checkpoint into
  `-shm`/`-wal`); `file:...?immutable=1` URI (silently misses uncheckpointed WAL frames).

## Secrets (W-key)

`keysource.py:resolve_backup_key(source)` resolves the 64-char hex backup key from:

- `bitwarden:<item-id>` → `bw get password <item-id>`
- `keyring:<service>:<account>` → `secret-tool lookup service <service> account <account>`

Both shell out to existing agents; output is validated as exactly 64 hex chars.

- **Rationale**: `.zkm-secrets.yaml` + `*.key` files are gitignored, which blocks
  automation (W10) — an agent-backed source is scriptable and never lands on disk.
  Subprocess against `bw`/`secret-tool` keeps the plugin dependency-free and is
  hermetically testable with fake executables on PATH.
- **Rejected**: `keyring` Python package (extra dep inside zkm's sealed uv-tool env);
  plaintext key file as the *supported* path (stays possible for the pilot script but
  is not the automation story).
- Module is named `keysource.py`, NOT `secrets.py` — the plugin dir is inserted into
  `sys.path`, so a `secrets.py` would shadow the stdlib module.

## Call log ingest (id:5e19)

`call_log` is probed via `_table_exists` (same pattern as `message_quoted`). Absent
table → behaviour unchanged. When present, rows are queried with the same watermark and
merged into the per-day per-chat stream (sorted by `(timestamp, call_id)`).

**Column mapping** (confirmed against msgstore.db v5+ with call_log rows):

| column      | type    | semantics |
|-------------|---------|-----------|
| `jid_row_id`| INTEGER | identifies the OTHER party in the call (same as `chat_jid_row_id` for messages) |
| `from_me`   | INTEGER | 1 = outgoing call, 0 = incoming |
| `call_id`   | TEXT    | stable identifier (dedup key); stored as `call_id` in the manifest |
| `timestamp` | INTEGER | milliseconds UTC |
| `video_call`| INTEGER | 1 = video call, 0 = voice only |
| `duration`  | INTEGER | call duration in **seconds**; 0 means not connected (missed/declined) |

**Dedup**: `call_id` (not `key_id` — calls use a different protocol ID space).
**Manifest**: `message_type: "call"` (messaging-namespaced per roadmap:cfd1), plus
`call: {direction, kind, duration}` for reconstitution, plus `call_id` for identification.
**Reconstitution**: `_reconstitute` detects `message_type == "call"` and returns a
call-shaped dict so day-file rewrites preserve call lines.

**REVIEW_ME**: the exact rendered wording is a judgment call — see REVIEW_ME.md id:5e19.

## Determinism contract

Sort by `(timestamp, key_id)`; fixed sentinels (`«deleted»`, `↩ (re: …)`); no locale
strings in output; YAML dumped with `sort_keys=False, allow_unicode=True`. Re-running
on unchanged input writes nothing (`convert()` returns `[]`).
