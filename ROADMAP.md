# Roadmap <!-- fables-turn roadmap v1 -->

Executor-facing task spec. Each item is sized for ONE Sonnet session. Items are
the single source of truth — TODO.md carries only a summary line. Executors tick
checkboxes; only the reviewer adds, removes, or re-scopes items.

Central-ledger mirror: items below reuse the `id:` tokens of their counterparts in
`~/src/zkm/TODO.md` (W-prefix section) where one exists.

## Items

- [x] Fix day-file rewrite data loss: persist text/quoted/media in manifest [ROUTINE] <!-- id:w6f -->
  - **Acceptance**: When a new same-day message triggers a day-file rewrite, all
    previously written body lines survive byte-identically: text bodies, `↩ (re: …)`
    reply prefixes, and `[media: <mime> → <cas_rel>]` lines. Mechanism: `messages:`
    manifest entries persist `text` (omit for media/revoked), `quoted_key_id` (omit
    when none) and `media: {mime, sha256}` (omit when no media); `_reconstitute()`
    rebuilds full message dicts from them; the media CAS path is re-derived as
    `chat/whatsapp/<tid>/originals/_objects/<sha[:2]>/<sha[2:]>`. Old manifests
    without the new keys must still load without error (bodies stay blank — healing
    pre-existing files is OUT of scope). Revoked entries must NOT persist text.
  - **Tests**: `tests/test_rewrite_persistence.py` — `test_rewrite_preserves_text_body`,
    `test_rewrite_preserves_reply_prefix`, `test_rewrite_preserves_media_line`,
    `test_manifest_media_entry_has_mime_and_sha256`,
    `test_manifest_text_persisted_except_revoked`,
    `test_old_manifest_without_new_keys_still_loads` — all `# roadmap:w6f`, all 6
    currently RED
  - **Done-check**: `uv run pytest tests/test_rewrite_persistence.py`
  - **Context**: `convert.py:_render_file` (manifest construction), `_reconstitute`,
    `_load_existing_manifest`. See ARCHITECTURE.md "Day-file rewrite" for the chosen
    fix direction and rejected alternatives. Verified data loss 2026-06-12 (worse than
    the central-ledger media-only framing). Keep determinism: identical re-runs still
    return `[]`.

- [x] W8: auto-detect owner_jid from the DB when config omits it [ROUTINE] <!-- id:f5b7 -->
  - **Acceptance**: `owner_jid` becomes optional. When absent from config, derive it:
    `SELECT user || '@' || server FROM jid WHERE _id = (SELECT sender_jid_row_id FROM
    message WHERE from_me=1 AND sender_jid_row_id IS NOT NULL GROUP BY
    sender_jid_row_id ORDER BY COUNT(*) DESC LIMIT 1)`. Explicit config always
    overrides the derived value. If underivable (no qualifying rows), fall back to the
    current default `owner@s.whatsapp.net`. Update `plugin.yaml` (`owner_jid`
    `required: false`, description mentions auto-detection) and README.
  - **Tests**: `tests/test_owner_jid.py` — `test_owner_jid_derived_when_config_absent`,
    `test_owner_jid_derivation_picks_most_frequent_sender`,
    `test_plugin_yaml_owner_jid_optional` (all RED) +
    `test_owner_jid_fallback_when_underivable` (already-green regression guard for
    the fallback branch) — all `# roadmap:f5b7`. Explicit-config override is guarded
    by the pre-existing `test_convert_owner_jid_in_participants`.
  - **Done-check**: `uv run pytest tests/test_owner_jid.py`
  - **Context**: `convert.py:convert` (config read), new helper `_detect_owner_jid(con)`.
    The shared conftest db has only `sender_jid_row_id=NULL` for `from_me` rows; the
    test file builds its own db copy with an attributed from_me row.

- [x] W11a: render message_system_number_change as system-event lines [ROUTINE] <!-- id:w11 -->
  - **Acceptance**: When a `message_system_number_change` table exists
    (`message_row_id, old_jid_row_id, new_jid_row_id`), messages joined to it render as
    `«number change: <old_jid> → <new_jid>»` body lines (same `[HH:MM] sender: … <!--
    key_id: … -->` framing) and their manifest entries carry `status: system` plus
    `number_change: {old: <old_jid>, new: <new_jid>}` so the line survives rewrites
    (`_reconstitute` rebuilds it). Absent table → behaviour unchanged (probe via
    `_table_exists`, same pattern as `message_quoted`). Informal "here's my new number"
    text heuristics are explicitly OUT of scope (separate item id:bf12).
  - **Tests**: `tests/test_number_change.py` — `test_number_change_rendered_in_body`,
    `test_number_change_manifest_entry`, `test_number_change_survives_rewrite`
    (all RED) + `test_no_number_change_table_is_harmless` (already-green regression
    guard for the absent-table branch) — all `# roadmap:w11`
  - **Done-check**: `uv run pytest tests/test_number_change.py`
  - **Context**: `convert.py:_query_messages` (add probed LEFT JOIN), `_render_file`,
    `_reconstitute`. Synthetic schema defined in the test file. Relates to entity
    alias linking (Phase 4) — emit nothing entity-shaped yet.

- [x] W11a-fix: rename manifest `status: system` → `message_type: system` [ROUTINE] <!-- id:cfd1 -->
  - **Why reopened**: 2026-06-13 owner review decision (frontmatter-schema mtg) on the
    W11a REVIEW_ME box. The `«number change»` rendering is accepted, but the chosen
    `status: system` manifest value collides with the core-owned iCal lifecycle `status:`
    enum (calendar plugin). `status:` must stay core-owned/enum; the WhatsApp
    system-event marker moves to a messaging-namespaced field `message_type: system`.
  - **Acceptance**: in `convert.py:_render_file`, number-change entries write
    `message_type: "system"` instead of `status: "system"` (non-system messages keep
    `status: sent`/`revoked` unchanged); `_reconstitute` reads `message_type` to rebuild
    the line; the `«number change: <old> → <new>»` body rendering is byte-identical to
    today. Update `tests/test_number_change.py::test_number_change_manifest_entry`
    (currently asserts `entry["status"] == "system"`) to assert
    `entry["message_type"] == "system"` and that `status` is not `"system"`.
  - **Tests**: `tests/test_number_change.py` (modify the manifest-entry assertion; the
    other three w11 tests stay green) — `# roadmap:w11x`
  - **Done-check**: `uv run pytest tests/test_number_change.py`
  - **Context**: central-ledger counterpart is `~/src/zkm/TODO.md` id:cfd1 (the
    cross-plugin D2/D3 schema-namespacing item, which also reconciles
    `messaging-spec.md`). This roadmap item is the zkm-whatsapp slice only; the
    `messaging-spec.md` reconciliation lives in the zkm core repo under id:cfd1.

- [x] W-key: resolve WhatsApp backup key from Bitwarden CLI or OS keyring [HARD — strong model] <!-- id:w-key -->
  - **Done**: 2026-06-12 relay handoff C5 — `keysource.py` + pilot `--key-source` +
    `plugin.yaml` `backup_key_source`; 12 hermetic tests in `tests/test_keysource.py`
    (fake `bw`/`secret-tool` on PATH). Two judgment calls queued in REVIEW_ME.md.
  - **Why HARD**: secret-handling surface — scheme syntax, error taxonomy and
    validation strictness are judgment calls; touches the fetch-role boundary
    (pilot script) rather than `convert()`.
  - **Acceptance**: `keysource.py:resolve_backup_key(source)` resolves
    `bitwarden:<item-id>` via `bw get password <item-id>` and
    `keyring:<service>:<account>` via `secret-tool lookup service <service> account
    <account>`; validates the result is exactly 64 hex chars (whitespace-stripped,
    case preserved); raises `KeySourceError` on unknown scheme, malformed source,
    missing binary, non-zero exit, or invalid key material (message never contains the
    key). `scripts/wa_decrypt_pilot.py` gains a `--key-source` alternative to the
    key-file argument. `plugin.yaml` documents optional `backup_key_source`.
    Hermetic tests via fake `bw`/`secret-tool` executables on PATH — no real secrets.
  - **Done-check**: `uv run pytest tests/test_keysource.py`

- [x] W10: auto-decryption trigger from Syncthing inbox [HARD — strong model] <!-- id:d058 -->
  - **Status 2026-06-15**: BUILT (commit 718f10b) — `scripts/systemd/`
    `zkm-whatsapp-decrypt.{sh,service,path}` + README serve as the design note and
    install artifacts: `.path` unit watches the synced backup dir, oneshot wrapper
    decrypts via `wa_decrypt_pilot.py --key-source keyring:…` → atomic-rename into
    `source_db` → `zkm convert whatsapp --no-amenders`; idempotency via a
    newer-than guard, `flock`'d, failures surface in the journal (oneshot, no retry
    loop).
  - **CLOSED 2026-06-16**: live `@manual` journey run on zomni (Syncthing +
    `systemd --user`). All 4 assertions verified: (1) fresh crypt15 → decrypt +
    `zkm convert whatsapp` once (real run, 71 files); (2) unchanged db → no-op;
    (3) bad key → exit 1, journal, no loop, nothing partial written; (4) original
    crypt15 untouched. Trigger-fires-on-real-delivery proven from the 06:33 journal.
    Live journey ALSO caught a real defect: the `.path` watcher died on the first
    Syncthing burst (`start-limit-hit` — 5 no-op fires/sec tripped systemd's default
    rate-limiter), silently stopping the watcher. Fixed: `StartLimitIntervalSec=0`
    on the `.service` (safe — flock + newer-than guard are the idempotency mechanism;
    commit 8e03cf2), burst-tested (8 rapid starts, watcher stays active, zero
    start-limit-hit). Decryption's long-term home is the `zkm fetch whatsapp` recipe
    (see meeting note); this wrapper is the verified prototype until then.
  - **Why HARD**: machine state (systemd `.path` unit or inotify hook on zomni),
    secret access at trigger time (depends on id:w-key, now available), and a
    checksum gate to avoid re-decrypting unchanged `.crypt15` files — not
    executor-runnable in CI. Gate: design note first; unit files reviewed by the
    human before install.
  - **Acceptance**: updated `msgstore.db.crypt15` landing in
    `~/knowledge/inbox/whatsapp/` triggers decryption (key via
    `resolve_backup_key`) and optionally `zkm convert whatsapp`; unchanged
    crypt15 (checksum match) is a no-op; failures surface visibly (journal), never
    loop. Manual journey: `features/manual.feature` "Auto-decryption trigger".

- [ ] W7: smarter segmentation design note [HARD — meeting] <!-- id:367f -->
  - **Why HARD**: design-only, explicitly GATED — do not start until v1 is live AND
    concrete retrieval pain from day-boundaries exists. Burst/temporal-density or
    per-thread re-segmentation must be additive and MUST NOT rewrite chat-level
    `thread_id`. See `~/src/zkm/docs/meeting-notes/2026-06-03-0952-zkm-whatsapp-scope.md`.
  - **Acceptance**: a design note (docs/), no code.

- [ ] W11b: heuristic detection of informal "new number" messages [HARD — meeting] <!-- id:bf12 -->
  - **Why HARD**: multi-language pattern judgment, false-positive cost, and a
    human-confirmation flow that does not exist yet; depends on id:w11 landing and on
    the Phase 4 entity alias/synonym design. Gate: id:w11 shipped + at least one real
    missed-number-change case.
  - **Acceptance**: flagging only (never auto-merge identities — see core
    "name is not a UID" policy); proposal doc before implementation.
