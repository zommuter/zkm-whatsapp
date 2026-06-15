# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] W10 auto-decrypt units — live verification (roadmap:d058)
  — `scripts/systemd/zkm-whatsapp-decrypt.{sh,service,path}` are BUILT (commit 718f10b)
  but unverified on real machine state. Before relying on them: (1) review the three unit
  files + wrapper, then install per `scripts/systemd/README.md`; (2) run the `@manual`
  journey in `features/manual.feature` "Auto-decryption trigger" — a fresh crypt15 lands,
  decrypt + `zkm convert whatsapp` run exactly once, an unchanged crypt15 is a no-op, and a
  failed decryption surfaces in `journalctl --user` without a retry loop. Tick this and
  ROADMAP id:d058 only after the live journey passes. (A `@manual` scenario is not a green
  test, so the relay holds d058 open until you confirm.)
