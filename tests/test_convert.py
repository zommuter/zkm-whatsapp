"""Tests for zkm-whatsapp convert.py (W2–W5, W9)."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from convert import (
    _DELETED_SENTINEL,
    _REPLY_INDICATOR,
    PLUGIN_NAME,
    PLUGIN_VERSION,
    _thread_id,
    _wal_safe_source,
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
        # path: chat/whatsapp/by-id/<thread_id>/<YYYY-MM-DD>.md
        assert p.suffix == ".md"
        assert p.parent.parent.name == "by-id"
        assert p.parent.parent.parent.name == "whatsapp"
        assert len(p.parent.name) == 16  # thread_id hex prefix
        assert len(p.stem) == 10         # YYYY-MM-DD


def _footer_manifest(path: Path) -> list[dict]:
    """Parse the end-of-file ``<!-- zkm:manifest ... -->`` block (id:767e)."""
    text = path.read_text(encoding="utf-8")
    start = text.find("<!-- zkm:manifest")
    assert start != -1, "no <!-- zkm:manifest ... --> footer block found"
    body_start = text.index("\n", start) + 1
    end = text.find("-->", body_start)
    assert end != -1, "footer manifest block not terminated"
    data = yaml.safe_load(text[body_start:end]) or {}
    return data.get("messages", []) if isinstance(data, dict) else []


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
        # manifest moved to footer (id:767e) — must NOT be in frontmatter
        assert "messages" not in fm
        assert "<!-- zkm:manifest" in text


def test_convert_messages_manifest_has_key_ids(store: Path, config: dict):
    written = convert(store, config)
    for p in written:
        for entry in _footer_manifest(p):  # manifest now lives in footer (id:767e)
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
    day_files = list((store / "chat" / "whatsapp" / "by-id" / tid).glob("*.md"))
    assert len(day_files) == 1
    text = day_files[0].read_text()

    assert _DELETED_SENTINEL in text
    manifest = _footer_manifest(day_files[0])  # manifest now lives in footer (id:767e)
    revoked = [m for m in manifest if m["status"] == "revoked"]
    assert len(revoked) == 1
    assert revoked[0]["key_id"] == "AABBCC003"


def test_convert_reply_indicator(store: Path, config: dict):
    """W3: in_reply_to → ↩ (re: <quoted_key_id>) prefix in body."""
    convert(store, config)
    jid = "41792222222@s.whatsapp.net"
    tid = _thread_id(jid)
    day_files = list((store / "chat" / "whatsapp" / "by-id" / tid).glob("*.md"))
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
    day_files = list((store / "chat" / "whatsapp" / "by-id" / tid).glob("*.md"))
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
    day_files = list((store / "chat" / "whatsapp" / "by-id" / tid).glob("*.md"))
    assert len(day_files) == 1
    text = day_files[0].read_text()
    end = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    assert fm.get("chat_name") == "Test Group"


# ── W9: WAL handling ──────────────────────────────────────────────────────────

def test_wal_safe_source_no_wal(tmp_path: Path):
    """Fast path: no -wal → returns original path unchanged, tempdir=None."""
    db = tmp_path / "test.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (x INT)")
    con.close()

    result, tmpdir = _wal_safe_source(db)
    assert result == db
    assert tmpdir is None


def test_wal_safe_source_empty_wal(tmp_path: Path):
    """Empty -wal file (already checkpointed) → treated same as no WAL, fast path."""
    db = tmp_path / "test.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (x INT)")
    con.close()
    wal = db.with_name(db.name + "-wal")
    wal.write_bytes(b"")  # zero-length WAL

    result, tmpdir = _wal_safe_source(db)
    assert result == db
    assert tmpdir is None


def _make_wal_db(path: Path) -> bool:
    """Create a WAL-mode db at *path* with a row committed only to the WAL.

    Returns True if the WAL file is non-empty after setup (some SQLite builds
    auto-checkpoint on connection close — those skip WAL-specific assertions).
    """
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")
    con.execute("CREATE TABLE t (key_id TEXT, ts INTEGER, body TEXT)")
    con.execute("INSERT INTO t VALUES ('PRE_WAL_KEY', 1744550000000, 'before wal')")
    con.commit()
    # Open a second connection holding a read snapshot so the writer
    # cannot checkpoint its subsequent write.
    con_reader = sqlite3.connect(path)
    con_reader.execute("BEGIN")  # hold a read snapshot
    con.execute("INSERT INTO t VALUES ('WAL_ONLY_KEY', 1744550001000, 'wal-only message')")
    con.commit()
    con.close()
    # WAL now contains frames the reader's snapshot predate → checkpoint blocked.
    con_reader.commit()
    con_reader.close()
    wal = path.with_name(path.name + "-wal")
    return wal.exists() and wal.stat().st_size > 0


def test_wal_safe_source_with_wal(tmp_path: Path):
    """When -wal is non-empty: returns a temp-dir copy, source path unchanged."""
    db = tmp_path / "msgstore.db"
    has_wal = _make_wal_db(db)
    if not has_wal:
        pytest.skip("SQLite checkpointed on close; WAL-specific path not reachable")

    orig_size = db.stat().st_size
    orig_mtime = db.stat().st_mtime_ns

    result, tmpdir = _wal_safe_source(db)
    try:
        assert result != db
        assert tmpdir is not None
        assert result.parent == tmpdir
        assert result.name == db.name
        # Source not modified
        assert db.stat().st_size == orig_size
        assert db.stat().st_mtime_ns == orig_mtime
        # WAL file still present in original location
        assert db.with_name(db.name + "-wal").exists()
        # Temp copy is a valid readable db containing the WAL-only row
        con = sqlite3.connect(result)
        rows = con.execute("SELECT key_id FROM t ORDER BY ts").fetchall()
        con.close()
        key_ids = [r[0] for r in rows]
        assert "WAL_ONLY_KEY" in key_ids
        assert "PRE_WAL_KEY" in key_ids
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_wal_frames_visible(store: Path, tmp_path: Path, config: dict):
    """W9: convert() reads messages committed only to WAL (not in main db file)."""
    from conftest import _create_test_db, MEDIA_FILENAME, MEDIA_BYTES

    # Build a full schema db (same schema as test_db) in WAL mode
    wal_db = tmp_path / "msgstore_wal.db"
    media_file = tmp_path / MEDIA_FILENAME
    media_file.write_bytes(MEDIA_BYTES)
    _create_test_db(wal_db, media_file)

    # Add a WAL-only message (different timestamp so it's a new row)
    has_wal = False
    con = sqlite3.connect(wal_db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")
    con_reader = sqlite3.connect(wal_db)
    con_reader.execute("BEGIN")
    con.execute(
        "INSERT INTO message VALUES (200, 'WAL_TEST_KEY', 1744553000000, 0, 'wal-only content', 1, 2, 0)"
    )
    con.commit()
    con.close()
    con_reader.commit()
    con_reader.close()
    wal_file = wal_db.with_name(wal_db.name + "-wal")
    has_wal = wal_file.exists() and wal_file.stat().st_size > 0

    wal_config = dict(config, source_db=str(wal_db))
    written = convert(store, wal_config)
    all_text = "\n".join(p.read_text() for p in written)

    if has_wal:
        # WAL-only message must be visible
        assert "WAL_TEST_KEY" in all_text or "wal-only content" in all_text
        # Original db file not mutated
        assert not wal_db.with_name(wal_db.name + "-wal.orig").exists()
    else:
        # SQLite checkpointed on close; all messages in main db either way
        assert len(written) >= 1
