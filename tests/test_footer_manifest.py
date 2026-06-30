"""Spec for roadmap:767e — move the per-message manifest out of the frontmatter
into an end-of-file footer block.

Owner mandate (meeting 2026-06-26-1746, D1/D2): a short-chat day-file frontmatter
is ~27+ lines because the unbounded per-message `messages:` manifest lives inline.
It MUST shrink to ~<=10 lines, and the manifest MUST move to an end-of-file
`<!-- zkm:manifest\n<yaml>\n-->` footer in the SAME `.md` (NOT a sidecar). Keep
self-contained `.md`, single-file diff, byte-identical re-emit. `participants:`
stays inline, flow-compacted. `_load_existing_manifest`/`_reconstitute` read the
footer with a frontmatter fallback so pre-change files heal on the next rewrite
without data loss.

All four tests are RED until id:767e lands (the manifest is in the frontmatter
today). They are the executable contract — do not weaken them to pass.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from conftest import _create_test_db

from convert import _thread_id, convert

CHAT_JID = "41792222222@s.whatsapp.net"
OWNER_JID = "41791111111@s.whatsapp.net"
TZ = "Europe/Zurich"
LATE_TS_MS = 1744551000000  # later than every fixture message, same local day


def _private_setup(tmp_path: Path) -> tuple[Path, Path, dict]:
    media = tmp_path / "photo.jpg"
    media.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 12)
    db = tmp_path / "msgstore.db"
    _create_test_db(db, media)
    store = tmp_path / "knowledge"
    store.mkdir()
    config = {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": TZ}
    return db, store, config


def _day_file(store: Path) -> Path:
    tid = _thread_id(CHAT_JID)
    files = list((store / "chat" / "whatsapp" / "by-id" / tid).glob("*.md"))
    assert len(files) == 1, f"expected one day file, got {files}"
    return files[0]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    return yaml.safe_load(text[4:end]) or {}


def _frontmatter_line_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---\n", 4)
    # lines strictly between the opening "---" and the closing "---"
    return len(text[4:end].splitlines())


def _footer_manifest(path: Path) -> list[dict]:
    """Parse the end-of-file `<!-- zkm:manifest\n<yaml>\n-->` block."""
    text = path.read_text(encoding="utf-8")
    start = text.find("<!-- zkm:manifest")
    assert start != -1, "no `<!-- zkm:manifest ... -->` footer block found"
    body_start = text.index("\n", start) + 1
    end = text.find("-->", body_start)
    assert end != -1, "footer manifest block is not terminated with `-->`"
    data = yaml.safe_load(text[body_start:end]) or {}
    return data.get("messages", data) if isinstance(data, dict) else data


def test_manifest_lives_in_footer_not_frontmatter(tmp_path: Path):  # roadmap:767e
    db, store, config = _private_setup(tmp_path)
    convert(store, config)
    day = _day_file(store)
    fm = _frontmatter(day)
    assert "messages" not in fm, "manifest must leave the frontmatter (D1)"
    manifest = _footer_manifest(day)
    key_ids = {e.get("key_id") or e.get("call_id") for e in manifest}
    assert "AABBCC001" in key_ids, "footer manifest must carry the message entries"


def test_short_chat_frontmatter_at_most_10_lines(tmp_path: Path):  # roadmap:767e
    db, store, config = _private_setup(tmp_path)
    convert(store, config)
    day = _day_file(store)
    n = _frontmatter_line_count(day)
    assert n <= 10, f"short-chat frontmatter must be <=10 lines, got {n}"


def test_footer_manifest_survives_rewrite_losslessly(tmp_path: Path):  # roadmap:767e
    db, store, config = _private_setup(tmp_path)
    convert(store, config)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES (50, 'AABBCC_LATE', ?, 0, 'late message', 1, 2, 0)",
        (LATE_TS_MS,),
    )
    con.commit()
    con.close()
    written = convert(store, config)
    day = _day_file(store)
    assert day in written, "the rewrite must have actually re-emitted the day file"
    body = day.read_text(encoding="utf-8")
    # Pre-existing bodies preserved (reconstituted from the FOOTER manifest)...
    assert "Hello there" in body
    assert "late message" in body
    # ...and the manifest is still in the footer, not back in the frontmatter.
    assert "messages" not in _frontmatter(day)
    assert {"AABBCC001", "AABBCC_LATE"} <= {
        e.get("key_id") for e in _footer_manifest(day) if e.get("key_id")
    }


def test_pre_change_frontmatter_manifest_heals_on_rewrite(tmp_path: Path):  # roadmap:767e
    """A legacy day-file with the manifest in the frontmatter must load via the
    fallback and heal to a footer on the next rewrite with no message loss."""
    db, store, config = _private_setup(tmp_path)
    convert(store, config)
    day = _day_file(store)
    fm = _frontmatter(day)
    # Reconstruct a legacy-shaped file: manifest back in the frontmatter.
    legacy_fm = dict(fm)
    # (current convert already writes messages in fm pre-767e; post-767e this test
    # forges the legacy shape explicitly so the fallback path is exercised.)
    if "messages" not in legacy_fm:
        legacy_fm["messages"] = _footer_manifest(day)
    body = day.read_text(encoding="utf-8")
    transcript = body[body.find("\n---\n", 4) + 5 :]
    transcript = transcript.split("<!-- zkm:manifest")[0]
    day.write_text(
        "---\n"
        + yaml.dump(legacy_fm, allow_unicode=True, sort_keys=False)
        + "---\n"
        + transcript,
        encoding="utf-8",
    )
    # Trigger a rewrite.
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES (51, 'AABBCC_LATE2', ?, 0, 'second late', 1, 2, 0)",
        (LATE_TS_MS + 1000,),
    )
    con.commit()
    con.close()
    convert(store, config)
    healed = _day_file(store)
    healed_body = healed.read_text(encoding="utf-8")
    assert "Hello there" in healed_body, "legacy body must survive the heal"
    assert "second late" in healed_body
    assert "messages" not in _frontmatter(healed), "must heal into a footer"
