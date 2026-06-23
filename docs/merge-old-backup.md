# Merging an older WhatsApp backup into an existing store

Goal: fold a second WhatsApp source (e.g. an older phone's backup that has extra
messages and/or media the current `msgstore.db` lacks) into a store that already
contains converted day-files — **without losing existing text, replies, media, or
NER enrichment**.

This works because zkm-whatsapp dedups on `key_id` (overlapping messages collapse)
and the watermark is keyed per absolute `source_db` path (a different DB file starts
fresh). See `CLAUDE.md` § "Incremental backups".

## The trap (why you can't just point at the old DB and convert)

Day-files written before v0.3.0 (`processor_version: 0.2.0`) store **only**
`key_id/sender/status/timestamp` in the manifest — the message text lives only in the
body. When a merge adds a new message to an *existing* day, that day is rewritten by
reconstituting its existing messages **from the manifest** (`_reconstitute`). On a
0.2.0 file that **blanks all existing text/replies/media** (the w6f data-loss bug).

So you must **heal** existing day-files first (persist text/replies/media/number-change
into the manifest, sourced from the DB), after which any rewrite is lossless.

## Prerequisites

- The current store's `source_db` is configured and converted (the baseline).
- The old backup decrypted to a plain SQLite DB (see step 1).
- The old backup's `Media/` folder on disk, if you want its media/voice notes.
- A whisper.cpp `/inference` server if you'll transcribe voice notes afterwards
  (e.g. `stt_endpoint: http://127.0.0.1:8089/inference`).
- **A git commit (or backup) of `$ZKM_STORE` before you start.** Every step is
  designed to be safe, but this is irreplaceable data — snapshot first.

## Step 1 — Decrypt the old backup (fetch-role, out of convert scope)

crypt12/14/15 are all supported; the version is auto-detected. The key may be a
64-char hex string **or** the raw Java-serialized `key` file (rooted-phone
`/data/data/com.whatsapp/files/key`):

```bash
cd ~/src/zkm/plugins/zkm-whatsapp
uv run --with wa-crypt-tools python scripts/wa_decrypt_pilot.py \
    /path/to/key  /path/to/msgstore.db.crypt14  /tmp/old-msgstore.db
```

Sanity-check the result:
```bash
sqlite3 /tmp/old-msgstore.db 'SELECT count(*) FROM message;'
```

## Step 2 — Heal existing day-files (make the merge lossless)

Run against the **current** `source_db` (the one that produced the existing files):

```bash
zkm convert whatsapp --reprocess-all
```

This re-derives text/quoted/media/number-change from the DB by `key_id` and writes
the missing manifest fields in place (body untouched except media lines, which gain
the CAS link if `media_root` is set). It is surgical, idempotent, and
watermark-independent. **Eyeball one healed file before trusting the whole sweep:**

```bash
git -C "$ZKM_STORE" diff --stat | tail
git -C "$ZKM_STORE" diff -- chat/whatsapp/<some-thread>/<some-day>.md   # text intact?
git -C "$ZKM_STORE" add -A && git -C "$ZKM_STORE" commit -m "heal whatsapp manifests pre-merge"
```

## Step 3 — Merge the old DB (oldest source first)

Point `source_db` at the decrypted old DB and (optionally) `media_root` at its media
tree. A different DB path → fresh watermark → all its messages are considered;
overlapping `key_id`s dedup, genuinely-new messages are added. Existing days that gain
a message rewrite **losslessly** (manifests were healed in step 2); days the old DB
doesn't touch are unchanged.

```yaml
# zkm-config.yaml — temporarily point at the old source
whatsapp:
  source_db: /tmp/old-msgstore.db
  media_root: /path/to/old-whatsapp-data     # parent of Media/ (optional)
```
```bash
zkm convert whatsapp                 # merge messages (NER re-runs only on touched days)
zkm convert whatsapp --reprocess-all # CAS the old media + heal any newly-merged days
```

Then restore `source_db` to the current DB in `zkm-config.yaml`.

## Step 4 — Transcribe voice notes (optional)

```bash
zkm convert stt-wa                   # needs whisper.cpp /inference + media in CAS
```

## Notes

- **Order matters only for readability**, not correctness — `key_id` dedup is
  order-independent. Oldest-first keeps day-files growing chronologically.
- **NER**: the merge re-runs amenders only on day-files it touches, so existing
  enrichment is preserved and new messages get enriched. No full re-NER needed.
- **Repeatable**: you can merge several backups; just repeat steps 1 + 3 per source.
