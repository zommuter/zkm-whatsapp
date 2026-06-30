"""Spec for roadmap:w6f — day-file rewrite must not lose message bodies.

Verified 2026-06-12: a rewrite triggered by a new same-day message blanks the
text bodies, reply prefixes and media lines of all previously written messages,
because `_reconstitute()` only gets key_id/timestamp/sender_jid/status from the
manifest. Fix: persist `text`, `quoted_key_id` and `media: {mime, sha256}` in
the `messages:` manifest entries (see ROADMAP.md id:w6f and ARCHITECTURE.md
"Day-file rewrite").
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from conftest import MEDIA_BYTES, MEDIA_KEY_ID, MEDIA_MIME, _create_test_db

from convert import _thread_id, convert

CHAT_JID = "41792222222@s.whatsapp.net"
OWNER_JID = "41791111111@s.whatsapp.net"
TZ = "Europe/Zurich"
# Later than every fixture message, same local day (fixture spans ~15:16-15:21).
LATE_TS_MS = 1744551000000


def _private_setup(tmp_path: Path) -> tuple[Path, Path, dict]:
    """Build a per-test db + store (the session db must not be mutated)."""
    media = tmp_path / "photo.jpg"
    media.write_bytes(MEDIA_BYTES)
    db = tmp_path / "msgstore.db"
    _create_test_db(db, media)
    store = tmp_path / "knowledge"
    store.mkdir()
    config = {"source_db": str(db), "owner_jid": OWNER_JID, "timezone": TZ}
    return db, store, config


def _add_late_message(db: Path) -> None:
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES (50, 'AABBCC_LATE', ?, 0, 'late message', 1, 2, 0)",
        (LATE_TS_MS,),
    )
    con.commit()
    con.close()


def _day_file(store: Path) -> Path:
    tid = _thread_id(CHAT_JID)
    files = list((store / "chat" / "whatsapp" / "by-id" / tid).glob("*.md"))
    assert len(files) == 1
    return files[0]


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    end = text.find("\n---\n", 4)
    return yaml.safe_load(text[4:end])


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


def _rewrite(tmp_path: Path) -> Path:
    """Convert, add a late same-day message, convert again; return the day file."""
    db, store, config = _private_setup(tmp_path)
    convert(store, config)
    _add_late_message(db)
    written = convert(store, config)
    day = _day_file(store)
    assert day in written  # the rewrite actually happened
    return day


def test_rewrite_preserves_text_body(tmp_path: Path):  # roadmap:w6f
    text = _rewrite(tmp_path).read_text()
    assert "Hello there" in text
    assert "With reply" in text
    assert "late message" in text


def test_rewrite_preserves_reply_prefix(tmp_path: Path):  # roadmap:w6f
    text = _rewrite(tmp_path).read_text()
    assert "↩ (re: AABBCC001)" in text


def test_rewrite_preserves_media_line(tmp_path: Path):  # roadmap:w6f
    text = _rewrite(tmp_path).read_text()
    sha = hashlib.sha256(MEDIA_BYTES).hexdigest()
    cas_rel = f"chat/whatsapp/by-id/{_thread_id(CHAT_JID)}/originals/_objects/{sha[:2]}/{sha[2:]}"
    assert f"[media: {MEDIA_MIME} → {cas_rel}]" in text


def test_manifest_media_entry_has_mime_and_sha256(tmp_path: Path):  # roadmap:w6f
    _db, store, config = _private_setup(tmp_path)
    convert(store, config)
    manifest = _footer_manifest(_day_file(store))  # manifest now lives in footer (id:767e)
    entry = next(m for m in manifest if m["key_id"] == MEDIA_KEY_ID)
    assert entry["media"]["mime"] == MEDIA_MIME
    assert entry["media"]["sha256"] == hashlib.sha256(MEDIA_BYTES).hexdigest()


def test_manifest_text_persisted_except_revoked(tmp_path: Path):  # roadmap:w6f
    _db, store, config = _private_setup(tmp_path)
    convert(store, config)
    manifest = _footer_manifest(_day_file(store))  # manifest now lives in footer (id:767e)
    by_key = {m["key_id"]: m for m in manifest}
    assert by_key["AABBCC001"]["text"] == "Hello there"
    assert by_key["AABBCC004"].get("quoted_key_id") == "AABBCC001"
    # Revoked messages must NOT leak text into the manifest.
    assert "text" not in by_key["AABBCC003"]


def test_old_manifest_without_new_keys_still_loads(tmp_path: Path):  # roadmap:w6f
    """Pre-fix files (manifest without text/media keys) must merge without error.

    Their bodies stay blank (healing is out of scope), but the merged file's NEW
    entries must carry the persisted text.
    """
    db, store, config = _private_setup(tmp_path)
    tid = _thread_id(CHAT_JID)
    day = datetime.fromtimestamp(1744550200, tz=ZoneInfo(TZ)).strftime("%Y-%m-%d")
    out_dir = store / "chat" / "whatsapp" / "by-id" / tid
    out_dir.mkdir(parents=True)
    legacy_ts = datetime.fromtimestamp(1744550100, tz=ZoneInfo(TZ)).isoformat()
    legacy = {
        "source": "whatsapp",
        "date": day,
        "thread_id": tid,
        "chat_jid": CHAT_JID,
        "participants": [],
        "messages": [
            {
                "key_id": "LEGACY001",
                "timestamp": legacy_ts,
                "sender_jid": CHAT_JID,
                "status": "sent",
            }
        ],
    }
    (out_dir / f"{day}.md").write_text(
        "---\n" + yaml.dump(legacy, allow_unicode=True, sort_keys=False) + "---\n\nlegacy body\n"
    )

    convert(store, config)  # must not raise
    manifest = _footer_manifest(_day_file(store))  # manifest now lives in footer (id:767e)
    by_key = {m["key_id"]: m for m in manifest}
    assert "LEGACY001" in by_key  # legacy entry survived the merge
    assert by_key["AABBCC001"]["text"] == "Hello there"  # new entries persist text
