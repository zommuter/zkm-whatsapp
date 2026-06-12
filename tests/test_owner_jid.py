"""Spec for roadmap:f5b7 — W8 owner_jid auto-detection from the db.

When `owner_jid` is absent from config, derive it from the most frequent
attributed `from_me` sender:

    SELECT user || '@' || server FROM jid WHERE _id = (
        SELECT sender_jid_row_id FROM message
        WHERE from_me = 1 AND sender_jid_row_id IS NOT NULL
        GROUP BY sender_jid_row_id ORDER BY COUNT(*) DESC LIMIT 1)

Explicit config always overrides (multi-account edge case — guarded by the
existing test_convert_owner_jid_in_participants). Underivable → fall back to
the current default `owner@s.whatsapp.net`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from conftest import MEDIA_BYTES, _create_test_db

from convert import convert

OWNER_JID = "41791111111@s.whatsapp.net"  # jid _id = 1 in the fixture
TZ = "Europe/Zurich"


def _private_db(tmp_path: Path, *, attribute_owner: bool) -> Path:
    media = tmp_path / "photo.jpg"
    media.write_bytes(MEDIA_BYTES)
    db = tmp_path / "msgstore.db"
    _create_test_db(db, media)
    if attribute_owner:
        # Real msgstore.db rows attribute from_me messages to the owner JID;
        # the shared fixture leaves them NULL, so attribute them here.
        con = sqlite3.connect(db)
        con.execute("UPDATE message SET sender_jid_row_id = 1 WHERE from_me = 1")
        con.commit()
        con.close()
    return db


def _all_frontmatter(store: Path) -> list[dict]:
    result = []
    for p in (store / "chat" / "whatsapp").rglob("*.md"):
        text = p.read_text()
        end = text.find("\n---\n", 4)
        result.append(yaml.safe_load(text[4:end]))
    return result


def test_owner_jid_derived_when_config_absent(tmp_path: Path):  # roadmap:f5b7
    db = _private_db(tmp_path, attribute_owner=True)
    store = tmp_path / "knowledge"
    store.mkdir()
    convert(store, {"source_db": str(db), "timezone": TZ})  # no owner_jid

    fms = _all_frontmatter(store)
    assert fms
    for fm in fms:
        addresses = {p["address"] for p in fm["participants"]}
        assert OWNER_JID in addresses
        assert "owner@s.whatsapp.net" not in addresses
        for entry in fm["messages"]:
            assert entry["sender_jid"] != "owner@s.whatsapp.net"


def test_owner_jid_derivation_picks_most_frequent_sender(tmp_path: Path):  # roadmap:f5b7
    db = _private_db(tmp_path, attribute_owner=True)
    # Add a single stray attributed from_me row pointing at contact B (jid _id=3):
    # the owner (2 rows) must still win the GROUP BY count.
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES (70, 'STRAY001', 1744550900000, 1, 'stray', 1, 3, 0)"
    )
    con.commit()
    con.close()

    store = tmp_path / "knowledge"
    store.mkdir()
    convert(store, {"source_db": str(db), "timezone": TZ})

    for fm in _all_frontmatter(store):
        addresses = {p["address"] for p in fm["participants"]}
        assert OWNER_JID in addresses
        assert "owner@s.whatsapp.net" not in addresses


def test_plugin_yaml_owner_jid_optional():  # roadmap:f5b7
    plugin_yaml = Path(__file__).parent.parent / "plugin.yaml"
    spec = yaml.safe_load(plugin_yaml.read_text())
    assert spec["config"]["owner_jid"]["required"] is False


def test_owner_jid_fallback_when_underivable(tmp_path: Path):  # roadmap:f5b7 (guard)
    """No attributed from_me rows → keep the documented default. Already-green
    regression guard for the fallback branch (current behaviour must survive)."""
    db = _private_db(tmp_path, attribute_owner=False)
    store = tmp_path / "knowledge"
    store.mkdir()
    convert(store, {"source_db": str(db), "timezone": TZ})

    fms = _all_frontmatter(store)
    assert fms
    for fm in fms:
        addresses = {p["address"] for p in fm["participants"]}
        assert "owner@s.whatsapp.net" in addresses
