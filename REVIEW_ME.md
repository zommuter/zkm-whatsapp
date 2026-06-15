# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [x] tests/test_keysource.py::test_keyring_scheme_calls_secret_tool (roadmap:w-key)
  — `keyring:<service>:<account>` maps to `secret-tool lookup service <service>
  account <account>` (libsecret CLI, no Python keyring dep). Confirm the attribute
  names (`service`/`account`) match how you store the key. — CONFIRMED by user 2026-06-15: `service`/`account` IS the user's
  standard libsecret scheme (same as their mbsync `PassCmd`, e.g. `service mail/gmx account ...`).
  Store via `secret-tool store --label="zkm whatsapp backup key" service zkm/whatsapp account backup`;
  reference `--key-source keyring:zkm/whatsapp:backup`.
