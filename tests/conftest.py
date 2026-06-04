"""Shared fixtures for zkm-whatsapp tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def _create_test_db(path: Path) -> None:
    """Create a minimal msgstore.db fixture with known test data."""
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE jid (
            _id INTEGER PRIMARY KEY,
            user TEXT NOT NULL,
            server TEXT NOT NULL
        );
        CREATE TABLE chat (
            _id INTEGER PRIMARY KEY,
            jid_row_id INTEGER NOT NULL,
            subject TEXT
        );
        CREATE TABLE message (
            _id INTEGER PRIMARY KEY,
            key_id TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            from_me INTEGER NOT NULL DEFAULT 0,
            text_data TEXT,
            chat_row_id INTEGER NOT NULL,
            sender_jid_row_id INTEGER,
            revoked INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE message_quoted (
            message_row_id INTEGER PRIMARY KEY,
            key_id TEXT NOT NULL
        );
        CREATE TABLE message_media (
            message_row_id INTEGER PRIMARY KEY,
            mime_type TEXT,
            file_path TEXT
        );
        CREATE TABLE group_participant_user (
            group_jid_row_id INTEGER NOT NULL,
            user_jid_row_id INTEGER NOT NULL
        );

        -- JIDs
        INSERT INTO jid VALUES (1, '41791111111', 's.whatsapp.net');  -- owner
        INSERT INTO jid VALUES (2, '41792222222', 's.whatsapp.net');  -- contact A
        INSERT INTO jid VALUES (3, '41793333333', 's.whatsapp.net');  -- contact B
        INSERT INTO jid VALUES (4, '41791111111-1620000000', 'g.us'); -- group

        -- Chats
        INSERT INTO chat VALUES (1, 2, NULL);     -- 1:1 with contact A
        INSERT INTO chat VALUES (2, 4, 'Test Group');  -- group chat

        -- 1:1 messages (2026-04-13 in Europe/Zurich = UTC+2 → 12:00 UTC = 14:00 local)
        -- 2026-04-13T14:30:00+02:00 = 1744550200000 ms
        INSERT INTO message VALUES (1, 'AABBCC001', 1744550200000, 0, 'Hello there', 1, 2, 0);
        INSERT INTO message VALUES (2, 'AABBCC002', 1744550260000, 1, 'Hi!', 1, NULL, 0);
        INSERT INTO message VALUES (3, 'AABBCC003', 1744550320000, 0, NULL, 1, 2, 1);  -- revoked
        INSERT INTO message VALUES (4, 'AABBCC004', 1744550380000, 0, 'With reply', 1, 2, 0);

        -- reply link
        INSERT INTO message_quoted VALUES (4, 'AABBCC001');

        -- Group messages (same day)
        INSERT INTO message VALUES (5, 'BBCCDD001', 1744550400000, 0, 'Group message', 2, 3, 0);
        INSERT INTO message VALUES (6, 'BBCCDD002', 1744550460000, 1, 'From owner', 2, NULL, 0);
    """)
    con.commit()
    con.close()


@pytest.fixture(scope="session")
def test_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_path = tmp_path_factory.mktemp("fixtures") / "msgstore.db"
    _create_test_db(db_path)
    return db_path


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    store_path = tmp_path / "knowledge"
    store_path.mkdir()
    return store_path


@pytest.fixture()
def config(test_db: Path) -> dict:
    return {
        "source_db": str(test_db),
        "owner_jid": "41791111111@s.whatsapp.net",
        "timezone": "Europe/Zurich",
    }
