# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] tests/test_rewrite_persistence.py::test_manifest_text_persisted_except_revoked
  (roadmap:w6f) — fix direction: message text is DUPLICATED into the frontmatter
  manifest (`text:` key) so rewrites are lossless and files self-contained; the
  alternative (re-query the DB without watermark on rewrite) was rejected because it
  loses messages that exist only in older backup snapshots. Revoked entries never
  persist text. Confirm the frontmatter-duplication trade-off.

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

- [ ] tests/test_keysource.py::test_keyring_scheme_calls_secret_tool (roadmap:w-key)
  — `keyring:<service>:<account>` maps to `secret-tool lookup service <service>
  account <account>` (libsecret CLI, no Python keyring dep). Confirm the attribute
  names (`service`/`account`) match how you store the key.

- [ ] tests/test_keysource.py::test_rejects_non_hex_output (roadmap:w-key) — key
  validation is strict: exactly 64 hex chars after stripping whitespace; anything
  else (0x prefix, spaces inside, 32-byte base64) is rejected with KeySourceError.
  Confirm strictness over permissive normalisation.
