"""W6 — Media → inbox+CAS+sidecar tests."""

from __future__ import annotations

import json
from pathlib import Path

from convert import convert, PLUGIN_NAME, _thread_id

from conftest import MEDIA_BYTES, MEDIA_FILENAME, MEDIA_MIME


OWNER_JID = "41791111111@s.whatsapp.net"
CONTACT_A_JID = "41792222222@s.whatsapp.net"
CHAT_JID = CONTACT_A_JID  # 1:1 chat used for media message


def _run(store: Path, config: dict) -> list[Path]:
    return convert(store, config)


def test_cas_object_created(store: Path, config: dict) -> None:
    _run(store, config)
    tid = _thread_id(CHAT_JID)
    objects_dir = store / "chat" / "whatsapp" / "by-id" / tid / "originals" / "_objects"
    all_objects = list(objects_dir.rglob("*"))
    cas_files = [p for p in all_objects if p.is_file()]
    assert len(cas_files) == 1
    assert cas_files[0].read_bytes() == MEDIA_BYTES


def test_inbox_symlink_created(store: Path, config: dict) -> None:
    _run(store, config)
    tid = _thread_id(CHAT_JID)
    inbox_dir = store / "inbox" / "whatsapp" / tid
    symlinks = [p for p in inbox_dir.iterdir() if p.is_symlink()]
    assert len(symlinks) == 1
    assert symlinks[0].name == MEDIA_FILENAME
    # Symlink must resolve to the CAS object and have the right bytes.
    assert symlinks[0].resolve().read_bytes() == MEDIA_BYTES


def test_origin_json_sidecar(store: Path, config: dict) -> None:
    _run(store, config)
    tid = _thread_id(CHAT_JID)
    inbox_dir = store / "inbox" / "whatsapp" / tid
    sidecars = [p for p in inbox_dir.iterdir() if p.name.endswith(".origin.json")]
    assert len(sidecars) == 1
    data = json.loads(sidecars[0].read_text())
    assert data["schema"] == 1
    assert len(data["sha256"]) == 64  # sha256 hex of the CAS object
    producers = data["producers"]
    assert len(producers) == 1
    p = producers[0]
    assert p["plugin"] == PLUGIN_NAME
    # message field is a relative path to the day .md file
    assert p["message"].startswith("chat/whatsapp/")
    assert p["message"].endswith(".md")


def test_body_line_references_cas(store: Path, config: dict) -> None:
    _run(store, config)
    tid = _thread_id(CHAT_JID)
    day_files = list((store / "chat" / "whatsapp" / "by-id" / tid).glob("*.md"))
    assert len(day_files) == 1
    body = day_files[0].read_text()
    # The media message line must reference the CAS path.
    assert f"[media: {MEDIA_MIME} →" in body
    assert "chat/whatsapp/" in body


def test_idempotency_single_symlink_and_producer(store: Path, config: dict) -> None:
    _run(store, config)
    _run(store, config)  # second run with same data
    tid = _thread_id(CHAT_JID)
    inbox_dir = store / "inbox" / "whatsapp" / tid
    symlinks = [p for p in inbox_dir.iterdir() if p.is_symlink()]
    assert len(symlinks) == 1
    sidecars = [p for p in inbox_dir.iterdir() if p.name.endswith(".origin.json")]
    data = json.loads(sidecars[0].read_text())
    assert len(data["producers"]) == 1  # no duplicate producers
