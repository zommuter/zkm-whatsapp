# 2026-06-25 — Human-readable chat folder names (id:3b8a)

**Started:** 2026-06-25 15:36
**Session:** 92b0d42b-080e-4f0e-9048-5195b88269cf
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity)
**Topic:** Make `chat/<network>/<thread_id>/` paths browsable without breaking the "no hashes in filenames" convention, the stable-ID dedup contract, or the name-is-not-a-UID doctrine.

> Item `id:3b8a` lives in `~/src/zkm/TODO.md` (cross-cutting; whatsapp is the trigger). Meeting held from the whatsapp repo; ledger updates routed to zkm / zkm-stt (see Action items).

## Surfaced discoveries
- [2026-05-07 zkm] inbox CAS+symlink split: `_objects/<aa>/<rest>` is the stable canonical store; date-sharded symlinks are a regenerable navigation view — directly analogous to the chosen approach.
- [2026-05-10 .claude] name-is-not-a-UID / manual-merge doctrine: identical names are real; prefer reversible manual triage over hard heuristic merge.

## Agenda
1. Canonical-vs-view: rename the canonical path, or keep opaque thread_id canonical and generate a regenerable human-readable *view*?
2. Name derivation + collision/rename policy.
3. Privacy posture (names in paths leak more than hashes).
4. Cross-cutting scope: lock at `messaging-spec.md`; does calendar thread-index (id:9fb8) follow?

## Discussion

### Item 1 — Canonical vs view
Archie: `thread_id = sha256(chat_jid)[:16]` (`convert.py:60`) is the dedup anchor, git-history anchor, and media-CAS path root (`convert.py:753`). The inbox CAS+symlink split is the precedent: keep `thread_id` canonical, add a regenerable name *view*. Renames re-point a symlink — zero history churn, no identity-merge risk in the source of truth.
Riku: Option C (rename canonical on resolution) churns git, breaks `git log --follow`, stales baked CAS paths, dangles future cross-refs, and violates the existing W7 constraint (id:367f, "MUST NOT rewrite thread_id"). Effectively pre-rejected.
Petra: Option A (slug+hex canonical) still bakes a name into the dedup/CAS root and either churns the slug on rename or freezes it stale. Buys one fewer directory at the cost of the stability property.
→ **DECIDED: approach B.** User refinements: (a) move canonical under `by-id/` too (symmetry, declutter); (b) the view must handle one identity → multiple canonicals (number change, DM+group); (c) canonical/CAS stability is load-bearing because **zkm-stt** will write voicemail transcripts against these paths.

### Item 2 — layout / label derivation / collisions / multi-canonical identity
Riku: linking two threads to the same human is an identity-resolution act — name≠UID; the plugin has no deterministic signal that a number-changed Anna is old-Anna. Auto-merge would guess and silently collide two real "Anna Müller"s.
Petra: split into two layers. Layer 1 (this item, deterministic): `by-name/<label>/<leaf> → by-id/<tid>/`, label mechanical from frontmatter, leaf makes each link unique so collisions/number-changes coexist honestly with no merge claim. Layer 2 (deferred, manual): true person-aggregation = NER person pages / `same-as` map, Phase 3.
→ **DECIDED.** Leaf = phone number (DM) / group-short-id (group), upgradeable to a NER/contacts label later (user refinement). Fallbacks: `«group»` (unnamed group), phone number (nameless DM); slug-sanitised; UTF-8/emoji kept. `message_system_number_change` (`convert.py:136,542`) is already captured — the future Layer-2 hook.

### Amendment (new topics, forward-flagged)
- **Call logs not archived today** — plugin reads only `message` (+quoted/media/number-change); `call_log` untouched. → new W-item to ingest + render calls into the daily WA files.
- **Cross-channel merged timeline** (Instagram reel + WhatsApp voice msg + call as one per-person conversation) — Layer-2 entity-timeline, cross-cutting `entity-model.md` / Phase 3+. → logged to zkm general.

### Item 3+4 — privacy / persistence / migration / scope
Riku: names already committed in frontmatter (`convert.py:259-267`), so committing the view doesn't materially increase leak — the deciding axis is churn, not privacy.
Archie: committing `by-name/` reintroduces rename churn (symlink delete+add) — exactly what B avoids. Gitignore the regenerable view; commit only `by-id/`.
Petra: N=2 for the chat doc-type satisfied (whatsapp + Telegram/Signal/Threema). Calendar (id:9fb8) is a different singleton-file doc-type — scope out.
→ **DECIDED.** Gitignore `chat/*/by-name/`; lock layout in `messaging-spec.md` for chat plugins; calendar out (separate session). Migration: one-time `git mv` to `by-id/`; update `cas_rel` (`convert.py:753`), originals subdir (`convert.py:851`), existing-file scan; coordinate with zkm-stt to land in lockstep.

## Decisions
1. **Approach B**: opaque `thread_id` stays canonical (dedup + git + CAS root); browsability via a regenerable view. *Out of scope:* renaming canonical (option C, violates id:367f); slug-in-canonical (option A).
2. **Layout**: `chat/<network>/by-id/<thread_id>/` (canonical) + `chat/<network>/by-name/<label>/<leaf> → ../../by-id/<thread_id>/` (view, regenerated each convert run). Label mechanical from frontmatter with fallbacks (`«group»` / phone number), slug-sanitised, UTF-8 kept. **Leaf = phone number (DM) / group-short-id (group)**, upgradeable to a NER/contacts label later. *Out of scope:* any auto-merge of threads into one person.
3. **Identity aggregation** (one human ↔ many threads) = deferred manual **Layer 2** (NER person pages / `same-as` map, Phase 3); `message_system_number_change` is the future hook. *Out of scope here.*
4. **View persistence**: `by-name/` gitignored; `by-id/` committed.
5. **Scope**: locked at `messaging-spec.md` chat doc-type; calendar (id:9fb8) out, deferred to its own session.

## Action items
- [ ] Implement approach B in zkm-whatsapp: `by-id/`+`by-name/` layout, mechanical label derivation + fallbacks, phone-number leaf, view regenerated each run; one-time migration of existing dirs; gitignore `chat/*/by-name/`. Resolves id:3b8a. → routed to zkm <!-- routed:809a -->
- [ ] Update `messaging-spec.md`: lock `by-id/`+`by-name/` per-chat-day layout, leaf-naming + label-derivation rules, Layer-1-vs-Layer-2 identity split. → routed to zkm <!-- routed:8a41 -->
- [ ] zkm-stt coordination: voicemail transcripts must target `chat/whatsapp/by-id/<tid>/` canonical and land in lockstep with the migration. → routed to zkm-stt <!-- routed:220a -->
- [ ] NEW W-item: ingest WhatsApp `call_log` table and render call entries inline into the per-chat-day transcript files. → routed to zkm <!-- routed:5e19 -->
- [ ] Forward-flag: cross-channel merged conversation timeline per person (Instagram + WhatsApp voice + calls) = Layer-2 entity-timeline, Phase 3+. → routed to zkm <!-- routed:9ee1 -->
- [ ] Calendar by-name applicability (id:9fb8) — discuss in a separate session. (deferred; no id)
