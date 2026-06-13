# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] tests/test_rewrite_persistence.py::test_manifest_text_persisted_except_revoked
  (roadmap:w6f) — fix direction: message text is DUPLICATED into the frontmatter
  manifest (`text:` key) so rewrites are lossless and files self-contained; the
  alternative (re-query the DB without watermark on rewrite) was rejected because it
  loses messages that exist only in older backup snapshots. Revoked entries never
  persist text. Confirm the frontmatter-duplication trade-off.
  → RESOLVED 2026-06-13 (frontmatter-schema mtg, D5): ACCEPTED, scoped. Manifest
  `text:` duplication is blessed ONLY because (a) the WhatsApp source is ephemeral
  (no durable original to re-read) AND (b) the manifest is the rewrite
  source-of-truth — document those two conditions in `plugin-spec.md` as a
  *conditional* pattern, not a store-wide default. No new privacy exposure (text
  already in the same .md body); ~2× message-text disk accepted. Pre-fix blanked
  files are NOT auto-healed — a `--full-resweep` follow-up is queued (zkm id:8d67).

- [ ] tests/test_rewrite_persistence.py::test_old_manifest_without_new_keys_still_loads
  (roadmap:w6f) — pre-fix day files are NOT healed: their already-blanked bodies stay
  blank; only new entries gain persisted text. Healing would need a watermark-less
  re-sweep — confirm out-of-scope (or request a one-off `--full-resweep` follow-up item).

- [ ] tests/test_owner_jid.py::test_owner_jid_fallback_when_underivable (roadmap:f5b7)
  — when owner_jid is absent AND underivable, convert silently falls back to the
  placeholder `owner@s.whatsapp.net` (current behaviour) instead of erroring or
  warning. Confirm silent fallback.

- [ ] tests/test_number_change.py::test_number_change_rendered_in_body (roadmap:w11)
  — rendering chosen: `«number change: <old_jid> → <new_jid>»` guillemet sentinel
  (matching `«deleted»`) with manifest `status: system` + `number_change: {old, new}`.
  No entity/alias emission yet (Phase 4). Confirm format + the new `system` status value.
  → RESOLVED 2026-06-13 (frontmatter-schema mtg, zkm id:cfd1): `«number change»`
  rendering is fine. CHANGE: `status: system` is a different concept from
  calendar's lifecycle `status:` — move it OUT of `status:` to a messaging field
  `message_type: system` (reconcile with `messaging-spec.md`). `status:` stays
  core-owned for the iCal lifecycle enum only.

- [ ] tests/test_keysource.py::test_keyring_scheme_calls_secret_tool (roadmap:w-key)
  — `keyring:<service>:<account>` maps to `secret-tool lookup service <service>
  account <account>` (libsecret CLI, no Python keyring dep). Confirm the attribute
  names (`service`/`account`) match how you store the key.

- [ ] tests/test_keysource.py::test_rejects_non_hex_output (roadmap:w-key) — key
  validation is strict: exactly 64 hex chars after stripping whitespace; anything
  else (0x prefix, spaces inside, 32-byte base64) is rejected with KeySourceError.
  Confirm strictness over permissive normalisation.
