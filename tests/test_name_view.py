"""Red spec for id:3b8a seam id:8040 — regenerable human-readable by-name view.

Decision: meeting 2026-06-25 (human-readable-chat-folder-names). Each convert run
(re)generates ``chat/whatsapp/by-name/<label>/<leaf>`` relative symlinks pointing at the
canonical ``by-id/<tid>/`` dir. Labels are derived mechanically from frontmatter (group
subject / DM contact name, with fallbacks); the leaf is the phone number (DM) /
group-short-id, so collisions and number-changes coexist as distinct links with NO merge
claim. The view is gitignored (derived, never committed) and idempotent.

Depends on id:058c (the view targets ``by-id/``). RED until id:8040 lands.
See ROADMAP.md id:8040.
"""

from __future__ import annotations

from pathlib import Path

from convert import convert

CONTACT_A_PHONE = "41792222222"  # 1:1 chat contact in the conftest fixture (no name → phone)


def _symlinks(by_name: Path) -> list[Path]:
    return [p for p in by_name.rglob("*") if p.is_symlink()]


def test_by_name_symlink_resolves_to_by_id(store: Path, config: dict):  # roadmap:8040
    convert(store, config)
    by_name = store / "chat" / "whatsapp" / "by-name"
    assert by_name.is_dir(), "by-name/ view not generated"
    links = _symlinks(by_name)
    assert links, "no leaf symlinks in by-name/"
    by_id = store / "chat" / "whatsapp" / "by-id"
    for link in links:
        target = link.resolve()
        assert by_id in target.parents or target.parent.parent.name == "by-id", (
            f"{link} does not resolve into by-id/"
        )


def test_group_label_from_subject(store: Path, config: dict):  # roadmap:8040
    convert(store, config)
    by_name = store / "chat" / "whatsapp" / "by-name"
    labels = [p.name.lower() for p in by_name.iterdir() if p.is_dir()]
    # the fixture group chat carries subject "Test Group"
    assert any("test" in lbl and "group" in lbl for lbl in labels), labels


def test_dm_leaf_is_phone_number(store: Path, config: dict):  # roadmap:8040
    convert(store, config)
    by_name = store / "chat" / "whatsapp" / "by-name"
    # contact A DM has no name in the fixture → label falls back to phone; leaf = phone number
    leaves = [p.name for p in _symlinks(by_name)]
    assert any(CONTACT_A_PHONE in leaf for leaf in leaves), leaves


def test_by_name_is_gitignored(store: Path, config: dict):  # roadmap:8040
    convert(store, config)
    gitignore = store / ".gitignore"
    assert gitignore.exists(), "store .gitignore not created"
    assert "by-name" in gitignore.read_text(), "chat/*/by-name/ not gitignored"


def test_view_regeneration_idempotent(store: Path, config: dict):  # roadmap:8040
    import os

    convert(store, config)
    by_name = store / "chat" / "whatsapp" / "by-name"
    before = {p.relative_to(by_name).as_posix(): os.readlink(p) for p in _symlinks(by_name)}
    assert before, "no view generated — nothing to check idempotency against"
    convert(store, config)  # regenerate
    after = {p.relative_to(by_name).as_posix(): os.readlink(p) for p in _symlinks(by_name)}
    assert before == after, "view not idempotent across runs"
