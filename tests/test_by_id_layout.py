"""Red spec for id:3b8a seam id:058c — canonical chat path moves under by-id/.

Decision: meeting 2026-06-25 (human-readable-chat-folder-names). The canonical,
stable store path becomes ``chat/whatsapp/by-id/<thread_id>/<YYYY-MM-DD>.md`` (was the
flat ``chat/whatsapp/<thread_id>/…``). The thread_id value, dedup, watermark and
determinism are unchanged — only the on-disk path prefix gains ``by-id/``.

These are RED until id:058c lands. See ROADMAP.md id:058c.
"""

from __future__ import annotations

from pathlib import Path

from convert import _thread_id, convert

CONTACT_A_JID = "41792222222@s.whatsapp.net"  # 1:1 chat in the conftest fixture


def test_day_files_emitted_under_by_id(store: Path, config: dict):  # roadmap:058c
    written = convert(store, config)
    assert written, "expected at least one day file"
    for p in written:
        # canonical layout: chat/whatsapp/by-id/<tid>/<day>.md
        assert p.parent.parent.name == "by-id", f"{p} not under by-id/"
        assert p.parent.parent.parent.name == "whatsapp", f"{p} not under chat/whatsapp/"


def test_thread_id_dir_lives_under_by_id(store: Path, config: dict):  # roadmap:058c
    convert(store, config)
    tid = _thread_id(CONTACT_A_JID)
    assert (store / "chat" / "whatsapp" / "by-id" / tid).is_dir()
    # the old flat location must no longer hold day files
    old = store / "chat" / "whatsapp" / tid
    assert not (old.exists() and any(old.glob("*.md"))), "day files still at the flat path"


def test_determinism_preserved_under_by_id(store: Path, config: dict):  # roadmap:058c
    # regression-guard (passes today): the by-id move must NOT break the determinism
    # contract — a second convert with no new messages returns [] (byte-identical no-op).
    convert(store, config)
    second = convert(store, config)
    assert second == []
