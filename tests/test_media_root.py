"""media_root — anchor relative message_media file_path to the on-disk media tree.

msgstore.db stores media as paths relative to the WhatsApp data dir
(e.g. "Media/WhatsApp Voice Notes/…/x.opus"). Without media_root those never
resolve and the media is emitted as a bare `[media: <mime>]` placeholder with no
CAS bytes — so downstream amenders (zkm-stt's stt-wa) have nothing to transcribe.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from conftest import MEDIA_BYTES, MEDIA_MIME, _create_test_db

from convert import _thread_id, convert

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
    return next((store / "chat" / "whatsapp" / _thread_id(CHAT_JID)).glob("*.md"))


def test_media_root_resolves_relative_path_to_cas(tmp_path: Path) -> None:
    store, db, media_root = _build(tmp_path)
    convert(store, _cfg(db, media_root=str(media_root)))

    objects = store / "chat" / "whatsapp" / _thread_id(CHAT_JID) / "originals" / "_objects"
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

    objects = store / "chat" / "whatsapp" / _thread_id(CHAT_JID) / "originals" / "_objects"
    cas_files = [p for p in objects.rglob("*") if p.is_file()] if objects.exists() else []
    assert cas_files == []
    # Bare placeholder in the manifest: no media dict, so amenders see nothing.
    assert all(not m.get("media") for m in _manifest(_day_file(store))["messages"])
