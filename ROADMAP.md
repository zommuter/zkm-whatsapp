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

- [x] W12: media_root config — resolve relative msgstore media paths → CAS [ROUTINE] <!-- id:1c7d -->
  - **Done**: 2026-06-23 (v0.4.0, commit d8ba5a7). msgstore.db stores media as paths
    relative to the WhatsApp data dir; `_handle_media` checked `.exists()` against cwd so
    relative paths never resolved → media silently skipped (bare `[media: <mime>]`, no CAS
    bytes / no `media.{mime,sha256}` manifest), starving the stt-wa amender. New optional
    `media_root` config anchors relative `file_path` under the on-disk `Media/` tree
    (`_resolve_media_path`); `_handle_media` returns stored/not-found and `convert()` logs a
    missing-media summary (no longer silent); `except Exception: pass` replaced with a logged
    per-item warning (`exc_info`) — a real store failure is now distinct from "file absent".
  - **Tests**: `tests/test_media_root.py::test_media_root_resolves_relative_path_to_cas`,
    `::test_without_media_root_relative_path_unresolved` — assert real CAS object bytes +
    manifest `media.sha256`/`mime`. GREEN, verified this review (genuine impl, no gaming).
  - **Done-check**: `uv run pytest tests/test_media_root.py`
  - **Context**: central-ledger counterpart `~/src/zkm/TODO.md` W12 id:1c7d. Unblocks the
    STT chain (`zkm convert stt-wa` needs the CAS'd voice notes + manifest).

- [x] W13: reprocess() media backfill for existing day-files [ROUTINE] <!-- id:4b8e -->
  - **Done**: 2026-06-23 (v0.5.0, commit 70cf4ee). Non-destructive `reprocess()` hook
    (`zkm convert whatsapp --reprocess-all`, candidates passed by core `run_reprocess`)
    heals already-ingested day-files still carrying bare `[media: <mime>]` placeholders.
    Surgical, NOT a re-render: re-derives media from the DB by `key_id`, CASes any
    not-yet-stored file (via `media_root`), and patches ONLY the manifest `media:` entry +
    the matching `[media: …]` body line — message text and everything else preserved
    byte-for-byte (safe on pre-w6f files that don't persist text; a full re-render would
    blank them). Idempotent (skips messages already carrying `media.sha256`),
    watermark-independent, no-op+warn without `media_root`.
  - **Tests**: `tests/test_media_root.py::test_reprocess_backfills_media_non_destructively`
    (text preserved + media healed: manifest sha256 + body cas_rel + CAS object),
    `::test_reprocess_is_idempotent`, `::test_reprocess_without_media_root_is_noop`. GREEN,
    verified this review.
  - **Done-check**: `uv run pytest tests/test_media_root.py`
  - **Context**: central-ledger counterpart `~/src/zkm/TODO.md` W13 id:4b8e. Conforms to
    core's `reprocess(store_path, config, existing, *, progress)` shape (conformance.py).

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

- [ ] by-id canonical: move the chat store path under `by-id/` [ROUTINE] <!-- id:058c -->
  - **Seam of** id:3b8a (meeting 2026-06-25 human-readable-chat-folder-names; umbrella in
    `~/src/zkm/TODO.md`). See ARCHITECTURE.md "Folder naming".
  - **Acceptance**: day files are emitted at `chat/whatsapp/by-id/<thread_id>/<YYYY-MM-DD>.md`
    (was `chat/whatsapp/<thread_id>/…`); the media CAS root and originals subdir move with it
    (`chat/whatsapp/by-id/<tid>/originals/_objects/<aa>/<rest>`); the existing-file scan that
    `_load_existing_manifest`/`_reconstitute` walks reads from the new location. `thread_id`
    value, dedup (key_id), watermark keying, and determinism (identical re-run returns `[]`)
    are all UNCHANGED — only the on-disk path prefix gains `by-id/`. Existing layout tests
    that assert the bare `chat/whatsapp/<tid>/` path (e.g. `test_convert_per_chat_day_layout`,
    `test_convert_thread_id_in_path`, and the `.glob` locators in `test_convert.py`) are
    updated to the `by-id/` path as part of this item — that is the intended spec change
    from id:3b8a, not gaming. NO migration of an existing real store here (that is id:da9f).
  - **Tests**: `tests/test_by_id_layout.py` — `test_day_files_emitted_under_by_id`,
    `test_thread_id_dir_lives_under_by_id` (both `# roadmap:058c`, currently RED) +
    `test_determinism_preserved_under_by_id` (green regression guard).
  - **Done-check**: `uv run pytest tests/test_by_id_layout.py tests/test_convert.py`
  - **Context**: `convert.py:452-454` (out_dir), `:753` (cas_rel), `:851` (originals subdir),
    `_load_existing_manifest`. Keep the path prefix in ONE derivation so id:8040 + id:da9f reuse it.

- [ ] by-name view: regenerable human-readable symlink tree [ROUTINE] <!-- id:8040 -->
  - **Seam of** id:3b8a. **Depends on** id:058c (the view targets `by-id/<tid>/`).
  - **Acceptance**: each convert run (re)generates `chat/whatsapp/by-name/<label>/<leaf>`
    relative symlinks pointing to the canonical `by-id/<tid>/` dir. `<label>` derived
    mechanically: group `chat_name`/subject, DM contact `name`; fallbacks `«group»`
    (unnamed group) / phone number (nameless DM); slug-sanitised (strip `/`, NUL, leading
    dots; UTF-8/emoji kept). `<leaf>` = phone number for DMs, group-short-id for groups —
    leaf uniqueness lets a number-changed or same-named contact coexist as distinct symlinks
    with NO merge claim (no identity guessing — Layer-2/NER is out of scope). The view is
    idempotent: regenerating over an existing tree yields byte-identical links and stale
    links for removed threads are pruned. `chat/*/by-name/` is added to the store `.gitignore`
    (created if absent) — the view is derived, never committed.
  - **Tests**: `tests/test_name_view.py` — `test_by_name_symlink_resolves_to_by_id`,
    `test_group_label_from_subject`, `test_dm_leaf_is_phone_number`,
    `test_by_name_is_gitignored`, `test_view_regeneration_idempotent` (all `# roadmap:8040`, RED).
  - **Done-check**: `uv run pytest tests/test_name_view.py`
  - **Context**: new pure helpers `_chat_label(...)` / `_chat_leaf(...)` (unit-testable) +
    `_regenerate_name_view(store_path)` called at the end of `convert()`. Reuse the `by-id/`
    path prefix from id:058c. chat_name/participants are already in frontmatter to derive from.

- [ ] live-store migration + zkm-stt path lockstep [HARD — hands] <!-- id:da9f -->
  - **Seam of** id:3b8a. **Gated on** id:058c + id:8040 shipping. **Hands** (touches the
    user's `~/knowledge` store + cross-repo coordination — not CI-runnable).
  - **Acceptance**: one-time `git mv chat/whatsapp/<tid>/ → chat/whatsapp/by-id/<tid>/` across
    the existing store (history-preserving), regenerate the by-name view, and verify zkm-stt
    still resolves voicemail-transcript CAS paths against the new `by-id/` root (land the
    zkm-stt change in lockstep so neither repo breaks the other). The `messaging-spec.md`
    layout change is a SEPARATE zkm-core item (already in `~/src/zkm/TODO.md`), not this one.
  - **Why HARD — hands**: live user-store mutation + a cross-repo (zkm-stt) dependency that
    must be coordinated; no red test (verified by the migration journey, not a unit test).

- [ ] call-log ingest: render WhatsApp calls into the per-chat-day transcript [ROUTINE] <!-- id:5e19 -->
  - Central-ledger counterpart `~/src/zkm/TODO.md` id:5e19 (W call-log ingest). The plugin
    today reads only `message` (+quoted/media/number-change); the `call_log` table is untouched.
  - **Acceptance**: probe `call_log` via `_table_exists` (same pattern as `message_quoted` /
    `message_system_number_change`). For each call row, render a deterministic system-style
    body line in the day file of the chat-with-that-jid (call day in the configured tz),
    framed like other system events, conveying: **direction** (incoming/outgoing from
    `from_me`), **kind** (voice/video from `video_call`), and **duration-or-missed**
    (`duration` seconds; a not-connected call → "missed"). The manifest entry is keyed by the
    call's stable id (`call_id`), carries `message_type: "call"` (messaging-namespaced, NOT
    `status:` — roadmap:cfd1) plus `call: {direction, kind, duration}` so the line survives a
    day-file rewrite (`_reconstitute` rebuilds it). Calls merge into the per-day message
    stream sorted by `(timestamp, id)`; dedup on `call_id`. Absent `call_log` table →
    behaviour unchanged. Determinism preserved (identical re-run returns `[]`). The exact
    line WORDING is a judgment call → leave a `REVIEW_ME.md` box. **Cross-cutting**: the
    call/voice-event *rendering convention* belongs in `docs/messaging-spec.md` (zkm core,
    separate item) so telegram/signal/threema inherit one shape — THIS item is the whatsapp
    *ingest* only.
  - **Tests**: `tests/test_call_log.py` — `test_connected_call_rendered`,
    `test_missed_call_rendered`, `test_call_manifest_entry_message_type` (RED) +
    `test_no_call_log_table_is_harmless` (green regression guard) — all `# roadmap:5e19`.
    Synthetic `call_log` schema is defined in the test (the W11a number-change precedent);
    the implementer confirms/maps the REAL columns against a decrypted msgstore.db and
    documents the mapping in ARCHITECTURE.md (`call_result`/`video_call`/`duration` semantics).
  - **Done-check**: `uv run pytest tests/test_call_log.py`
  - **Context**: `convert.py:_query_messages` (add a probed `call_log` read merged into the
    per-day stream), `_render_file`, `_reconstitute`. Mirror the
    `message_system_number_change` (id:w11) integration shape end-to-end.
