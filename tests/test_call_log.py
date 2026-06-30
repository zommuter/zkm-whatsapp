"""Red spec for id:5e19 — ingest WhatsApp's call_log into the per-chat-day transcript.

The plugin today reads only the ``message`` table; calls are dropped. id:5e19 renders each
``call_log`` row as a deterministic system-style line in the day file of the chat with that
jid, with a manifest entry (``message_type: "call"``, keyed by ``call_id``) so it survives a
day-file rewrite.

Synthetic ``call_log`` schema is defined here (the W11a number-change precedent); the
implementer confirms/maps the real columns against a decrypted msgstore.db. RED until id:5e19
lands. See ROADMAP.md id:5e19. Assertions are substring/semantic (not exact wording — the
line format is a REVIEW_ME judgment call).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

from convert import convert

OWNER_JID = "41791111111@s.whatsapp.net"
CONTACT_PHONE = "41792222222"
BASE_TS = 1744550200000  # 2026-04-13T14:30:00+02:00 (matches the conftest fixture)

CONNECTED_CALL_ID = "CALL_VID_OUT_1"
MISSED_CALL_ID = "CALL_VOICE_IN_1"


def _make_db(path: Path, *, with_call_log: bool) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT NOT NULL, server TEXT NOT NULL);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER NOT NULL, subject TEXT);
        CREATE TABLE message (
            _id INTEGER PRIMARY KEY, key_id TEXT NOT NULL, timestamp INTEGER NOT NULL,
            from_me INTEGER NOT NULL DEFAULT 0, text_data TEXT, chat_row_id INTEGER NOT NULL,
            sender_jid_row_id INTEGER, revoked INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO jid VALUES (1, '41791111111', 's.whatsapp.net');  -- owner
        INSERT INTO jid VALUES (2, '41792222222', 's.whatsapp.net');  -- contact
        INSERT INTO chat VALUES (1, 2, NULL);                         -- 1:1 with contact
        -- one ordinary message so the chat/day file exists; calls merge into it
        INSERT INTO message VALUES (1, 'MSG001', %d, 0, 'hi', 1, 2, 0);
        """
        % BASE_TS
    )
    if with_call_log:
        con.executescript(
            """
            CREATE TABLE call_log (
                _id INTEGER PRIMARY KEY,
                jid_row_id INTEGER NOT NULL,
                from_me INTEGER NOT NULL,
                call_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                video_call INTEGER NOT NULL DEFAULT 0,
                duration INTEGER NOT NULL DEFAULT 0
            );
            -- connected outgoing VIDEO call (duration > 0)
            INSERT INTO call_log VALUES (1, 2, 1, '%s', %d, 1, 222);
            -- missed incoming VOICE call (duration == 0 → not connected)
            INSERT INTO call_log VALUES (2, 2, 0, '%s', %d, 0, 0);
            """
            % (CONNECTED_CALL_ID, BASE_TS + 60000, MISSED_CALL_ID, BASE_TS + 120000)
        )
    con.commit()
    con.close()


def _day_bodies(store: Path) -> list[str]:
    """Body text (after frontmatter) of every emitted day file — by-id-layout-agnostic."""
    bodies = []
    for p in (store / "chat" / "whatsapp").rglob("*.md"):
        text = p.read_text()
        end = text.find("\n---\n", 4)
        bodies.append(text[end + 5:] if end != -1 else text)
    return bodies


def _manifest_entries(store: Path) -> list[dict]:
    entries: list[dict] = []
    for p in (store / "chat" / "whatsapp").rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        # Read from end-of-file footer (id:767e); fall back to frontmatter for legacy files.
        footer_start = text.find("<!-- zkm:manifest")
        if footer_start != -1:
            body_start = text.index("\n", footer_start) + 1
            footer_end = text.find("-->", body_start)
            data = yaml.safe_load(text[body_start:footer_end]) if footer_end != -1 else {}
            entries.extend((data or {}).get("messages", []) or [])
        else:
            end = text.find("\n---\n", 4)
            fm = yaml.safe_load(text[4:end]) if end != -1 else {}
            entries.extend((fm or {}).get("messages", []) or [])
    return entries


def test_connected_call_rendered(store: Path, tmp_path: Path):  # roadmap:5e19
    db = tmp_path / "calls.db"
    _make_db(db, with_call_log=True)
    convert(store, {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": "Europe/Zurich"})
    body = "\n".join(_day_bodies(store)).lower()
    # connected outgoing video call line present (duration 222s)
    assert "call" in body and "video" in body, body


def test_missed_call_rendered(store: Path, tmp_path: Path):  # roadmap:5e19
    db = tmp_path / "calls.db"
    _make_db(db, with_call_log=True)
    convert(store, {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": "Europe/Zurich"})
    body = "\n".join(_day_bodies(store)).lower()
    assert "call" in body and "missed" in body, body


def test_call_manifest_entry_message_type(store: Path, tmp_path: Path):  # roadmap:5e19
    db = tmp_path / "calls.db"
    _make_db(db, with_call_log=True)
    convert(store, {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": "Europe/Zurich"})
    entries = _manifest_entries(store)
    call_entries = [e for e in entries if isinstance(e, dict) and e.get("message_type") == "call"]
    assert call_entries, f"no message_type:call manifest entry in {entries}"
    ids = {e.get("call_id") or e.get("key_id") for e in call_entries}
    assert CONNECTED_CALL_ID in ids, ids


def test_no_call_log_table_is_harmless(store: Path, tmp_path: Path):  # roadmap:5e19
    # regression-guard (passes today): a DB without call_log converts normally, no call lines.
    db = tmp_path / "nocalls.db"
    _make_db(db, with_call_log=False)
    written = convert(store, {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": "Europe/Zurich"})
    assert written
    assert "missed" not in "\n".join(_day_bodies(store)).lower()
