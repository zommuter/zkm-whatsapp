"""media_root — anchor relative message_media file_path to the on-disk media tree.

msgstore.db stores media as paths relative to the WhatsApp data dir
(e.g. "Media/WhatsApp Voice Notes/…/x.opus"). Without media_root those never
resolve and the media is emitted as a bare `[media: <mime>]` placeholder with no
CAS bytes — so downstream amenders (zkm-stt's stt-wa) have nothing to transcribe.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from conftest import MEDIA_BYTES, MEDIA_KEY_ID, MEDIA_MIME, _create_test_db

from convert import _thread_id, convert, reprocess

CHAT_JID = "41792222222@s.whatsapp.net"
REL_MEDIA = "Media/WhatsApp Voice Notes/202504/PTT-1.opus"


def _build(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return (store, db, media_root); the db references REL_MEDIA *relatively*."""
    media_root = tmp_path / "wa-data"
    blob = media_root / REL_MEDIA
    blob.parent.mkdir(parents=True)
    blob.write_bytes(MEDIA_BYTES)
    db = tmp_path / "msgstore.db"
    _create_test_db(db, Path(REL_MEDIA))  # relative file_path in message_media
    store = tmp_path / "knowledge"
    store.mkdir()
    return store, db, media_root


def _cfg(db: Path, **extra: str) -> dict:
    return {
        "source_db": str(db),
        "owner_jid": "41791111111@s.whatsapp.net",
        "timezone": "Europe/Zurich",
        **extra,
    }


def _manifest(day_path: Path) -> dict:
    fm = day_path.read_text().split("---\n", 2)[1]
    return yaml.safe_load(fm)


def _day_file(store: Path) -> Path:
    return next((store / "chat" / "whatsapp" / "by-id" / _thread_id(CHAT_JID)).glob("*.md"))


def test_media_root_resolves_relative_path_to_cas(tmp_path: Path) -> None:
    store, db, media_root = _build(tmp_path)
    convert(store, _cfg(db, media_root=str(media_root)))

    objects = store / "chat" / "whatsapp" / "by-id" / _thread_id(CHAT_JID) / "originals" / "_objects"
    cas_files = [p for p in objects.rglob("*") if p.is_file() and not p.name.endswith(".json")]
    assert len(cas_files) == 1
    assert cas_files[0].read_bytes() == MEDIA_BYTES

    # The manifest carries media.{mime,sha256} — exactly what stt-wa reads.
    media_msgs = [m for m in _manifest(_day_file(store))["messages"] if m.get("media")]
    assert media_msgs, "no media entry emitted in manifest"
    assert media_msgs[0]["media"].get("sha256")
    assert media_msgs[0]["media"].get("mime") == MEDIA_MIME


def test_without_media_root_relative_path_unresolved(tmp_path: Path) -> None:
    store, db, _ = _build(tmp_path)
    convert(store, _cfg(db))  # no media_root → relative path cannot resolve

    objects = store / "chat" / "whatsapp" / "by-id" / _thread_id(CHAT_JID) / "originals" / "_objects"
    cas_files = [p for p in objects.rglob("*") if p.is_file()] if objects.exists() else []
    assert cas_files == []
    # Bare placeholder in the manifest: no media dict, so amenders see nothing.
    assert all(not m.get("media") for m in _manifest(_day_file(store))["messages"])


def test_reprocess_backfills_media_non_destructively(tmp_path: Path) -> None:
    """--reprocess-all heals existing bare placeholders WITHOUT touching message text."""
    store, db, media_root = _build(tmp_path)
    convert(store, _cfg(db))  # first pass: no media_root → bare placeholder, no CAS
    day = _day_file(store)
    before = day.read_text()
    assert "Hello there" in before  # a text message shares this day-file
    assert f"[media: {MEDIA_MIME}]" in before

    changed = reprocess(store, _cfg(db, media_root=str(media_root)), [day])
    assert changed == [day]

    after = day.read_text()
    assert "Hello there" in after  # text preserved — non-destructive (no w6f blanking)
    assert "→ chat/whatsapp/" in after  # media body line healed (by-id path still starts with chat/whatsapp/)
    objects = store / "chat" / "whatsapp" / "by-id" / _thread_id(CHAT_JID) / "originals" / "_objects"
    cas = [p for p in objects.rglob("*") if p.is_file() and not p.name.endswith(".json")]
    assert len(cas) == 1 and cas[0].read_bytes() == MEDIA_BYTES
    entry = next(m for m in _manifest(day)["messages"] if m["key_id"] == MEDIA_KEY_ID)
    assert entry["media"]["sha256"]


def test_reprocess_is_idempotent(tmp_path: Path) -> None:
    store, db, media_root = _build(tmp_path)
    convert(store, _cfg(db))
    day = _day_file(store)
    cfg = _cfg(db, media_root=str(media_root))
    assert reprocess(store, cfg, [day]) == [day]  # first heals
    assert reprocess(store, cfg, [day]) == []  # second: already ingested → no rewrite


def test_reprocess_without_media_root_heals_but_no_cas(tmp_path: Path) -> None:
    """Without media_root the manifest heal still runs; only CAS bytes are skipped."""
    store, db, _ = _build(tmp_path)
    convert(store, _cfg(db))
    day = _day_file(store)
    reprocess(store, _cfg(db), [day])  # no media_root
    objects = store / "chat" / "whatsapp" / "by-id" / _thread_id(CHAT_JID) / "originals" / "_objects"
    cas = [p for p in objects.rglob("*") if p.is_file()] if objects.exists() else []
    assert cas == []  # no bytes stored without media_root
    # …but the media KIND is preserved in the manifest (renders [media: <mime>]).
    entry = next(m for m in _manifest(day)["messages"] if m["key_id"] == MEDIA_KEY_ID)
    assert entry["media"]["mime"] == MEDIA_MIME
    assert "sha256" not in entry["media"]


def test_reprocess_heals_missing_manifest_text(tmp_path: Path) -> None:
    """A pre-w6f (0.2.0) manifest without text: is healed from the DB by key_id."""
    store, db, media_root = _build(tmp_path)
    convert(store, _cfg(db))
    day = _day_file(store)

    # Simulate a 0.2.0 file: drop text: from every manifest entry (text lives only in body).
    raw = day.read_text()
    _, fm_text, body = raw.split("---\n", 2)
    fm = yaml.safe_load(fm_text)
    for m in fm["messages"]:
        m.pop("text", None)
    day.write_text("---\n" + yaml.dump(fm, allow_unicode=True, sort_keys=False) + "---\n" + body)
    assert all("text" not in m for m in _manifest(day)["messages"])

    changed = reprocess(store, _cfg(db, media_root=str(media_root)), [day])
    assert changed == [day]
    healed = {m["key_id"]: m for m in _manifest(day)["messages"]}
    assert healed["AABBCC001"]["text"] == "Hello there"  # restored from DB
    assert healed["AABBCC004"]["quoted_key_id"] == "AABBCC001"  # reply linkage intact


def test_convert_rejects_non_sqlite_source(tmp_path: Path) -> None:
    """A non-SQLite source_db (e.g. an encrypted backup) fails with a clear error."""
    import pytest

    from convert import convert

    bogus = tmp_path / "msgstore.db"
    bogus.write_bytes(b"\x61\xba\xe7\x77not a sqlite db" * 8)  # crypt-like garbage
    store = tmp_path / "knowledge"
    store.mkdir()
    with pytest.raises(ValueError, match="not a SQLite database"):
        convert(store, {"source_db": str(bogus), "owner_jid": "x@s.whatsapp.net"})
