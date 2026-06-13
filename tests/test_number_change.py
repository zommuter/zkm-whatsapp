"""Spec for roadmap:w11 — W11a: message_system_number_change → system-event lines.

WhatsApp records internal number migrations in `message_system_number_change`
(message_row_id, old_jid_row_id, new_jid_row_id). Such messages must render as

    «number change: <old_jid> → <new_jid>»

body lines (normal [HH:MM] sender: ... <!-- key_id: ... --> framing) and persist
`status: system` + `number_change: {old, new}` in the manifest so the line
survives day-file rewrites. Absent table → behaviour unchanged (probe like
`message_quoted`). Informal "here's my new number" text heuristics are OUT of
scope (id:bf12).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from conftest import MEDIA_BYTES, _create_test_db

from convert import _thread_id, convert

CHAT_JID = "41792222222@s.whatsapp.net"
OLD_JID = "41792222222@s.whatsapp.net"  # jid _id = 2
NEW_JID = "41799999999@s.whatsapp.net"  # added below as jid _id = 5
OWNER_JID = "41791111111@s.whatsapp.net"
TZ = "Europe/Zurich"
NC_KEY_ID = "NUMCHANGE01"


def _private_db(tmp_path: Path) -> Path:
    media = tmp_path / "photo.jpg"
    media.write_bytes(MEDIA_BYTES)
    db = tmp_path / "msgstore.db"
    _create_test_db(db, media)
    con = sqlite3.connect(db)
    con.executescript(f"""
        CREATE TABLE message_system_number_change (
            message_row_id INTEGER PRIMARY KEY,
            old_jid_row_id INTEGER,
            new_jid_row_id INTEGER
        );
        INSERT INTO jid VALUES (5, '41799999999', 's.whatsapp.net');
        -- system message row in the 1:1 chat, same day as the other fixtures
        INSERT INTO message VALUES (60, '{NC_KEY_ID}', 1744550500000, 0, NULL, 1, 2, 0);
        INSERT INTO message_system_number_change VALUES (60, 2, 5);
    """)
    con.commit()
    con.close()
    return db


def _setup(tmp_path: Path) -> tuple[Path, Path, dict]:
    db = _private_db(tmp_path)
    store = tmp_path / "knowledge"
    store.mkdir()
    return db, store, {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": TZ}


def _day_file(store: Path) -> Path:
    files = list((store / "chat" / "whatsapp" / _thread_id(CHAT_JID)).glob("*.md"))
    assert len(files) == 1
    return files[0]


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    end = text.find("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_number_change_rendered_in_body(tmp_path: Path):  # roadmap:w11
    _db, store, config = _setup(tmp_path)
    convert(store, config)
    text = _day_file(store).read_text()
    assert f"«number change: {OLD_JID} → {NEW_JID}»" in text
    assert f"<!-- key_id: {NC_KEY_ID} -->" in text


def test_number_change_manifest_entry(tmp_path: Path):  # roadmap:w11 roadmap:w11x
    _db, store, config = _setup(tmp_path)
    convert(store, config)
    fm = _frontmatter(_day_file(store))
    entry = next(m for m in fm["messages"] if m["key_id"] == NC_KEY_ID)
    # message_type: system is the messaging-namespaced marker (roadmap:cfd1).
    assert entry["message_type"] == "system"
    # status: must not be "system" — it is core-owned (iCal lifecycle enum).
    assert entry.get("status") != "system"
    assert entry["number_change"] == {"old": OLD_JID, "new": NEW_JID}


def test_number_change_survives_rewrite(tmp_path: Path):  # roadmap:w11
    db, store, config = _setup(tmp_path)
    convert(store, config)
    # New same-day message → day-file rewrite via manifest reconstitution.
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES (80, 'AABBCC_LATE', 1744551000000, 0, 'late', 1, 2, 0)"
    )
    con.commit()
    con.close()
    convert(store, config)
    text = _day_file(store).read_text()
    assert f"«number change: {OLD_JID} → {NEW_JID}»" in text


def test_no_number_change_table_is_harmless(tmp_path: Path):  # roadmap:w11 (guard)
    """Standard fixture db (no message_system_number_change) stays unaffected.
    Already-green regression guard for the probe's absent-table branch."""
    media = tmp_path / "photo.jpg"
    media.write_bytes(MEDIA_BYTES)
    db = tmp_path / "msgstore.db"
    _create_test_db(db, media)
    store = tmp_path / "knowledge"
    store.mkdir()
    written = convert(store, {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": TZ})
    assert written
    assert "«number change:" not in "\n".join(p.read_text() for p in written)
