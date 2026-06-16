# Manual verification checklist — zkm-whatsapp
# CLI/library surface: no headless-automatable UI. These journeys need real
# machine state (secrets, Syncthing, systemd) and are checked by a human.

@manual
Feature: WhatsApp backup ingestion end-to-end

  @manual
  Scenario: Decrypt a crypt15 backup with a key file (pilot path)
    Given a msgstore.db.crypt15 backup and the 64-char hex backup key in a chmod-0600 file
    When I run "uv run python scripts/wa_decrypt_pilot.py <keyfile> <crypt15> <out.db>"
    Then a valid SQLite msgstore.db is written to <out.db>
    And the key never appears on the command line or in shell history

  @manual
  Scenario: Resolve the backup key from Bitwarden (roadmap:w-key)
    Given the backup key stored as a Bitwarden item and an unlocked bw session
    When I run the pilot with "--key-source bitwarden:<item-id>"
    Then decryption succeeds without any key material written to disk
    And a locked bw vault produces a clear error that does not contain key material

  @manual
  Scenario: Resolve the backup key from the OS keyring (roadmap:w-key)
    Given the backup key stored via "secret-tool store service whatsapp account backup"
    When I run the pilot with "--key-source keyring:whatsapp:backup"
    Then decryption succeeds without any key material written to disk

  @manual
  Scenario: Live ingest of a fresh backup
    Given a decrypted msgstore.db configured as source_db in zkm-config.yaml
    When I run "zkm convert whatsapp" twice
    Then the first run writes chat/whatsapp/<tid>/<day>.md files and auto-commits
    And the second run writes nothing (deterministic no-op)
    And "zkm search" finds message text from the transcripts after "zkm index"

  @manual
  Scenario: Auto-decryption trigger from Syncthing (roadmap:d058 — W10, VERIFIED live 2026-06-16 on zomni)
    Given Syncthing delivering msgstore.db.crypt15 into ~/knowledge/inbox/whatsapp/
    And the scripts/systemd/zkm-whatsapp-decrypt.{sh,service,path} units installed with a key source per roadmap:w-key
    When an updated crypt15 file arrives
    Then decryption and "zkm convert whatsapp" run exactly once
    And an unchanged crypt15 (same checksum) triggers nothing
    And a failed decryption surfaces in the journal without retry-looping
    And a Syncthing burst firing the service many times in one second stays a no-op (StartLimitIntervalSec=0; the watcher survives)
