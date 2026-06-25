# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

## id:5e19 — call line wording

Current rendered body line format (roadmap:5e19):

```
«call: incoming voice, missed»
«call: outgoing video, 222s»
```

The ROADMAP flags this as a judgment call. Questions for the reviewer:
1. Is `«call: …»` the right sentinel style (vs `[call: …]` or a plain phrase)?
2. Should "missed" be the exact word for duration==0, or another term (e.g. "not connected", "unanswered")?
3. Should duration be in seconds (`222s`) or formatted (`3:42`)?
4. The `<!-- call_id: … -->` comment (vs `<!-- key_id: … -->`): is that the right marker style for calls?

The `call: {direction, kind, duration}` manifest shape is stable (feeds _reconstitute);
only the rendered string is a judgment call — changing it does not require a schema migration.
