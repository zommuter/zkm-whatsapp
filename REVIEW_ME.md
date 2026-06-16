# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [x] W10 auto-decrypt units — live verification (roadmap:d058) — CONFIRMED 2026-06-16
  — Live `@manual` journey run on zomni. All 4 assertions pass (fresh→decrypt+convert once
  [71 files]; unchanged→no-op; bad key→exit 1, journal, no loop; original untouched).
  Live run caught + fixed a real defect: the `.path` watcher died on the first Syncthing
  burst (`start-limit-hit`); fixed with `StartLimitIntervalSec=0` (commit 8e03cf2),
  burst-tested. Decryption's long-term home is the `zkm fetch whatsapp` recipe (meeting
  note 2026-06-16-2055); this wrapper is the verified prototype.
