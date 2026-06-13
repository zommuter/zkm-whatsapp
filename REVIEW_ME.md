# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] tests/test_owner_jid.py::test_owner_jid_fallback_when_underivable (roadmap:f5b7)
  — when owner_jid is absent AND underivable, convert silently falls back to the
  placeholder `owner@s.whatsapp.net` (current behaviour) instead of erroring or
  warning. Confirm silent fallback.

- [ ] tests/test_keysource.py::test_keyring_scheme_calls_secret_tool (roadmap:w-key)
  — `keyring:<service>:<account>` maps to `secret-tool lookup service <service>
  account <account>` (libsecret CLI, no Python keyring dep). Confirm the attribute
  names (`service`/`account`) match how you store the key.

- [ ] tests/test_keysource.py::test_rejects_non_hex_output (roadmap:w-key) — key
  validation is strict: exactly 64 hex chars after stripping whitespace; anything
  else (0x prefix, spaces inside, 32-byte base64) is rejected with KeySourceError.
  Confirm strictness over permissive normalisation.
