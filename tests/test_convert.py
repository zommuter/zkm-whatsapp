"""Tests for zkm-whatsapp convert.py (W2–W5)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import yaml

from convert import (
    _DELETED_SENTINEL,
    _REPLY_INDICATOR,
    PLUGIN_NAME,
    PLUGIN_VERSION,
    _thread_id,
    convert,
)
from state import load_state

# ── Unit tests ─────────────────────────────────────────────────────────────────

def test_thread_id_stable():
    jid = "41792222222@s.whatsapp.net"
    assert _thread_id(jid) == hashlib.sha256(jid.encode()).hexdigest()[:16]


def test_thread_id_group_vs_individual_differ():
    assert _thread_id("111@s.whatsapp.net") != _thread_id("111@g.us")


# ── Integration tests ──────────────────────────────────────────────────────────

def test_convert_returns_paths(store: Path, config: dict):
    written = convert(store, config)
    assert len(written) >= 1
    assert all(p.exists() for p in written)


def test_convert_creates_chat_whatsapp_dir(store: Path, config: dict):
    convert(store, config)
    assert (store / "chat" / "whatsapp").is_dir()


def test_convert_per_chat_day_layout(store: Path, config: dict):
    written = convert(store, config)
    for p in written:
        # path: chat/whatsapp/<thread_id>/<YYYY-MM-DD>.md
        assert p.suffix == ".md"
        assert p.parent.parent.name == "whatsapp"
        assert len(p.parent.name) == 16  # thread_id hex prefix
        assert len(p.stem) == 10         # YYYY-MM-DD


def test_convert_frontmatter_fields(store: Path, config: dict):
    written = convert(store, config)
    for p in written:
        text = p.read_text()
        assert text.startswith("---\n")
        end = text.find("\n---\n", 4)
        fm = yaml.safe_load(text[4:end])
        assert fm["source"] == PLUGIN_NAME
        assert fm["processor"] == PLUGIN_NAME
        assert fm["processor_version"] == PLUGIN_VERSION
        assert "thread_id" in fm
        assert "chat_jid" in fm
        assert "date" in fm
        assert "participants" in fm
        assert "messages" in fm


def test_convert_messages_manifest_has_key_ids(store: Path, config: dict):
    written = convert(store, config)
    for p in written:
        text = p.read_text()
        end = text.find("\n---\n", 4)
        fm = yaml.safe_load(text[4:end])
        for entry in fm["messages"]:
            assert "key_id" in entry
            assert "timestamp" in entry
            assert "sender_jid" in entry
            assert "status" in entry


def test_convert_deleted_tombstone(store: Path, config: dict):
    """W5: revoked messages emit «deleted» sentinel, key_id preserved in manifest."""
    convert(store, config)
    # Find the 1:1 chat day file
    jid = "41792222222@s.whatsapp.net"
    tid = _thread_id(jid)
    day_files = list((store / "chat" / "whatsapp" / tid).glob("*.md"))
    assert len(day_files) == 1
    text = day_files[0].read_text()

    assert _DELETED_SENTINEL in text
    end = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    revoked = [m for m in fm["messages"] if m["status"] == "revoked"]
    assert len(revoked) == 1
    assert revoked[0]["key_id"] == "AABBCC003"


def test_convert_reply_indicator(store: Path, config: dict):
    """W3: in_reply_to → ↩ (re: <quoted_key_id>) prefix in body."""
    convert(store, config)
    jid = "41792222222@s.whatsapp.net"
    tid = _thread_id(jid)
    day_files = list((store / "chat" / "whatsapp" / tid).glob("*.md"))
    text = day_files[0].read_text()
    assert f"{_REPLY_INDICATOR} (re: AABBCC001)" in text


def test_convert_deterministic(store: Path, config: dict):
    """Re-running on same DB produces identical files (deterministic emission contract)."""
    written1 = convert(store, config)
    contents1 = {p: p.read_text() for p in written1}

    written2 = convert(store, config)
    # Second run: same key_ids → no files rewritten (idempotent)
    assert written2 == []  # no changes

    for p, text in contents1.items():
        assert p.read_text() == text


def test_convert_dedup_on_key_id(store: Path, config: dict, test_db: Path):
    """W4/W3: rowid renumber does not cause duplicate messages."""
    convert(store, config)
    # Add a duplicate key_id with a different rowid (simulates backup-restore rowid shift)
    con = sqlite3.connect(test_db)
    # Insert message with same key_id but new _id (rowid renumber scenario)
    try:
        con.execute(
            "INSERT INTO message VALUES (99, 'AABBCC002', 1744550260001, 1, 'Hi!', 1, NULL, 0)"
        )
        con.commit()
    except sqlite3.IntegrityError:
        pass  # key_id might be UNIQUE in real schema
    finally:
        con.close()

    # Re-run: AABBCC002 already in manifest → should not appear twice in body
    convert(store, config)
    jid = "41792222222@s.whatsapp.net"
    tid = _thread_id(jid)
    day_files = list((store / "chat" / "whatsapp" / tid).glob("*.md"))
    text = day_files[0].read_text()
    assert text.count("AABBCC002") == 2  # once in manifest, once in body line


def test_convert_state_watermark_updated(store: Path, config: dict, test_db: Path):
    """W4: watermark advances after a successful convert."""
    convert(store, config)
    state = load_state(store, test_db)
    assert state.get("watermark_ms", 0) > 0


def test_convert_thread_id_in_path(store: Path, config: dict):
    """W3: thread_id directory name matches sha256(chat_jid)[:16]."""
    written = convert(store, config)
    for p in written:
        tid_dir = p.parent.name
        text = p.read_text()
        end = text.find("\n---\n", 4)
        fm = yaml.safe_load(text[4:end])
        assert tid_dir == _thread_id(fm["chat_jid"])


def test_convert_owner_jid_in_participants(store: Path, config: dict):
    written = convert(store, config)
    owner_jid = config["owner_jid"]
    for p in written:
        text = p.read_text()
        end = text.find("\n---\n", 4)
        fm = yaml.safe_load(text[4:end])
        addresses = {par["address"] for par in fm["participants"]}
        assert owner_jid in addresses


def test_convert_group_chat_name(store: Path, config: dict):
    """Group chat should have chat_name in frontmatter."""
    convert(store, config)
    group_jid = "41791111111-1620000000@g.us"
    tid = _thread_id(group_jid)
    day_files = list((store / "chat" / "whatsapp" / tid).glob("*.md"))
    assert len(day_files) == 1
    text = day_files[0].read_text()
    end = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    assert fm.get("chat_name") == "Test Group"
