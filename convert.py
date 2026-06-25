"""zkm-whatsapp — convert decrypted WhatsApp msgstore.db to per-chat-day transcripts.

Source: decrypted SQLite msgstore.db (stdlib sqlite3, zero extra deps for DB parsing).
Output: chat/whatsapp/by-id/<thread_id>/YYYY-MM-DD.md — one file per chat per day.

Stable IDs (W3):
  message_id  = whatsapp:<chat_jid>:<key_id>  (protocol-level key_id)
  thread_id   = sha256(chat_jid.encode())[:16]
  in_reply_to = whatsapp:<chat_jid>:<quoted_key_id>  (from message_quoted)

Source state (W4): .zkm-state/zkm-whatsapp.json — timestamp watermark per source_db.
Dedup key: key_id in the file's messages: manifest.
Deterministic emission: sort by (timestamp, key_id); fixed sentinels; no locale strings.
"""

from __future__ import annotations

# Ensure this plugin's directory is on sys.path so `state` can be imported
# whether the module is loaded directly (pytest) or via importlib (zkm core).
import sys as _sys
from pathlib import Path as _Path

_here = str(_Path(__file__).parent)
if _here not in _sys.path:
    _sys.path.insert(0, _here)

import hashlib
import logging
import mimetypes
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from datetime import tzinfo as TzInfo
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from zkm.atomic import write_atomic
from zkm.cas import write_object
from zkm.inbox import build_canonical_index, symlink_with_sidecar

from state import load_state, save_state

log = logging.getLogger(__name__)

PLUGIN_NAME = "whatsapp"
PLUGIN_VERSION = "0.7.0"

_DELETED_SENTINEL = "«deleted»"  # «deleted»
_REPLY_INDICATOR = "↩"  # ↩

ProgressCallback = Callable[[int, int | None, str], None]


# ── JID / ID helpers ────────────────────────────────────────────────────────────

def _thread_id(chat_jid: str) -> str:
    return hashlib.sha256(chat_jid.encode()).hexdigest()[:16]


def _thread_rel(tid: str) -> str:
    """Canonical relative chat path: chat/whatsapp/by-id/<tid>.

    Returns a POSIX-style string so callers can build sub-paths without a store root.
    Single derivation so id:8040 (by-name view) and id:da9f (migration) can reuse it.
    """
    return f"chat/whatsapp/by-id/{tid}"


def _thread_dir(store_path: Path, tid: str) -> Path:
    """Canonical absolute chat directory: <store>/chat/whatsapp/by-id/<tid>/."""
    return store_path / _thread_rel(tid)


# ── by-name view helpers (id:8040) ───────────────────────────────────────────────

def _slug_label(s: str) -> str:
    """Sanitise a chat label for use as a directory name.

    Strip ``/``, NUL, and leading dots; keep UTF-8/emoji.
    """
    s = s.replace("/", "").replace("\x00", "").lstrip(".")
    return s or "«unnamed»"


def _chat_label(chat_jid: str, chat_name: str | None) -> str:
    """Derive the human-readable label for the by-name/ first-level dir.

    Group: ``chat_name``/subject with fallback ``«group»``.
    DM:    contact ``name`` (not available here — caller passes None) → phone number.
    """
    is_group = chat_jid.endswith("@g.us")
    if is_group:
        raw = chat_name or "«group»"
    else:
        # DM: contact name is not stored in the chat row; fall back to phone number.
        raw = chat_name or chat_jid.split("@")[0]
    return _slug_label(raw)


def _chat_leaf(chat_jid: str) -> str:
    """Derive the unique leaf name for the by-name symlink.

    DM: phone number (local part of JID, e.g. ``41792222222``).
    Group: group short-id (local part of JID, e.g. ``41791111111-1620000000``).

    Using the JID local part keeps number-changed contacts as distinct symlinks with
    NO merge claim (Layer-2 identity resolution is out of scope).
    """
    return chat_jid.split("@")[0]


def _ensure_gitignore_by_name(store_path: Path) -> None:
    """Add ``chat/*/by-name/`` to the store .gitignore if not already present."""
    gitignore = store_path / ".gitignore"
    pattern = "chat/*/by-name/"
    if gitignore.exists():
        if pattern in gitignore.read_text():
            return
        current = gitignore.read_text()
        if not current.endswith("\n"):
            current += "\n"
        gitignore.write_text(current + pattern + "\n")
    else:
        gitignore.write_text(pattern + "\n")


def _regenerate_name_view(store_path: Path) -> None:
    """(Re)build the regenerable by-name symlink view for all by-id/ chat dirs.

    Scans store/chat/whatsapp/by-id/ and for each thread dir reads the frontmatter
    of the lexicographically last day file (cheapest way to get chat_jid + chat_name).
    Creates/updates relative symlinks under chat/whatsapp/by-name/<label>/<leaf>
    pointing to ../../by-id/<tid>/ and prunes stale ones.

    Idempotent: identical re-runs produce byte-identical links.
    """
    by_id_root = store_path / "chat" / "whatsapp" / "by-id"
    if not by_id_root.is_dir():
        return

    by_name_root = store_path / "chat" / "whatsapp" / "by-name"
    by_name_root.mkdir(parents=True, exist_ok=True)

    # Ensure the view is gitignored.
    _ensure_gitignore_by_name(store_path)

    # Build the desired {(label, leaf): tid} mapping.
    desired: dict[tuple[str, str], str] = {}
    for tid_dir in sorted(by_id_root.iterdir()):
        if not tid_dir.is_dir():
            continue
        tid = tid_dir.name
        day_files = sorted(tid_dir.glob("*.md"))
        if not day_files:
            continue
        # Read frontmatter of the latest day file for this chat.
        text = day_files[-1].read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        end = text.find("\n---\n", 4)
        if end == -1:
            continue
        fm = yaml.safe_load(text[4:end]) or {}
        chat_jid = fm.get("chat_jid", "")
        chat_name = fm.get("chat_name")
        if not chat_jid:
            continue
        label = _chat_label(chat_jid, chat_name)
        leaf = _chat_leaf(chat_jid)
        desired[(label, leaf)] = tid

    # Collect currently existing symlinks under by-name/.
    existing_links: dict[tuple[str, str], str] = {}
    for label_dir in by_name_root.iterdir():
        if not label_dir.is_dir():
            continue
        for link in label_dir.iterdir():
            if link.is_symlink():
                existing_links[(label_dir.name, link.name)] = str(link.readlink())

    # Create/update desired links.
    for (label, leaf), tid in desired.items():
        # Relative target: ../../by-id/<tid>  (link lives at by-name/<label>/<leaf>)
        target = f"../../by-id/{tid}"
        link_dir = by_name_root / label
        link_dir.mkdir(exist_ok=True)
        link_path = link_dir / leaf
        if link_path.is_symlink():
            if str(link_path.readlink()) == target:
                continue  # already correct
            link_path.unlink()
        elif link_path.exists():
            link_path.unlink()
        link_path.symlink_to(target)

    # Prune stale links (exist in the tree but not in desired).
    for (label, leaf) in set(existing_links) - set(desired):
        stale = by_name_root / label / leaf
        if stale.is_symlink():
            stale.unlink()
        # Remove empty label dirs.
        parent = stale.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


# ── Database schema probing ──────────────────────────────────────────────────────

def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# ── DB queries ───────────────────────────────────────────────────────────────────

def _build_jid_map(con: sqlite3.Connection) -> dict[int, str]:
    """Return {jid._id: "user@server"} for all jids."""
    return {
        row[0]: f"{row[1]}@{row[2]}"
        for row in con.execute("SELECT _id, user, server FROM jid")
    }


def _detect_owner_jid(con: sqlite3.Connection) -> str | None:
    """Derive owner JID from the most frequent attributed from_me sender.

    SELECT user || '@' || server FROM jid WHERE _id = (
        SELECT sender_jid_row_id FROM message
        WHERE from_me = 1 AND sender_jid_row_id IS NOT NULL
        GROUP BY sender_jid_row_id ORDER BY COUNT(*) DESC LIMIT 1)

    Returns None if no qualifying rows exist.
    """
    row = con.execute("""
        SELECT j.user || '@' || j.server
        FROM jid j
        WHERE j._id = (
            SELECT sender_jid_row_id FROM message
            WHERE from_me = 1 AND sender_jid_row_id IS NOT NULL
            GROUP BY sender_jid_row_id
            ORDER BY COUNT(*) DESC
            LIMIT 1
        )
    """).fetchone()
    return row[0] if row else None


def _query_messages(
    con: sqlite3.Connection,
    watermark_ms: int,
    *,
    has_revoked_col: bool,
    has_quoted_table: bool,
    has_media_table: bool,
    has_number_change_table: bool,
) -> list[sqlite3.Row]:
    """Query all messages newer than watermark_ms."""
    revoked_expr = "m.revoked" if has_revoked_col else "0"
    quoted_join = (
        "LEFT JOIN message_quoted mq ON mq.message_row_id = m._id"
        if has_quoted_table else ""
    )
    quoted_key = "mq.key_id AS quoted_key_id" if has_quoted_table else "NULL AS quoted_key_id"
    media_join = (
        "LEFT JOIN message_media mm ON mm.message_row_id = m._id"
        if has_media_table else ""
    )
    media_cols = (
        "mm.mime_type, mm.file_path AS media_path"
        if has_media_table else "NULL AS mime_type, NULL AS media_path"
    )
    nc_join = (
        "LEFT JOIN message_system_number_change nc ON nc.message_row_id = m._id"
        if has_number_change_table else ""
    )
    nc_cols = (
        "nc.old_jid_row_id AS nc_old_jid_row_id, nc.new_jid_row_id AS nc_new_jid_row_id"
        if has_number_change_table else "NULL AS nc_old_jid_row_id, NULL AS nc_new_jid_row_id"
    )
    sql = f"""
        SELECT
            m._id AS row_id,
            m.key_id,
            m.timestamp,
            m.from_me,
            m.text_data,
            m.chat_row_id,
            m.sender_jid_row_id,
            {revoked_expr} AS revoked,
            c.jid_row_id AS chat_jid_row_id,
            c.subject AS chat_name,
            {quoted_key},
            {media_cols},
            {nc_cols}
        FROM message m
        JOIN chat c ON c._id = m.chat_row_id
        {quoted_join}
        {media_join}
        {nc_join}
        WHERE m.timestamp > ?
        ORDER BY m.timestamp, m.key_id
    """
    return con.execute(sql, (watermark_ms,)).fetchall()


def _query_calls(
    con: sqlite3.Connection,
    watermark_ms: int,
    jid_map: dict[int, str],
    owner_jid: str,
    tz: TzInfo,
) -> list[dict]:
    """Query call_log rows newer than watermark_ms and return normalised dicts.

    Each dict matches the message-dict shape used by _render_file / _reconstitute
    (with call_id as key_id for dedup, plus an extra call_id field for the manifest).
    Absent call_log table → returns [].

    Confirmed real call_log columns (msgstore.db v5+):
      _id, jid_row_id, from_me, call_id, timestamp, video_call, duration
    where duration == 0 means not connected (missed / declined).
    """
    if not _table_exists(con, "call_log"):
        return []
    rows = con.execute(
        """
        SELECT cl.call_id, cl.jid_row_id, cl.from_me,
               cl.timestamp, cl.video_call, cl.duration
        FROM call_log cl
        WHERE cl.timestamp > ?
        ORDER BY cl.timestamp, cl.call_id
        """,
        (watermark_ms,),
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        call_id: str = row["call_id"]
        jid_row_id: int = row["jid_row_id"]
        from_me_flag: int = row["from_me"]
        ts_ms: int = row["timestamp"]
        video_call: int = row["video_call"]
        duration: int = row["duration"]

        chat_jid = jid_map.get(jid_row_id, f"unknown@{jid_row_id}")
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=tz)
        sender_jid = owner_jid if from_me_flag else chat_jid
        direction = "outgoing" if from_me_flag else "incoming"
        kind = "video" if video_call else "voice"
        result.append({
            "key_id": call_id,            # used as dedup key throughout
            "call_id": call_id,           # also stored in manifest as call_id
            "ts": ts,
            "timestamp_ms": ts_ms,
            "from_me": bool(from_me_flag),
            "sender_jid": sender_jid,
            "chat_jid": chat_jid,         # consumed by convert() loop; not in message shape
            "chat_jid_row_id": None,      # no row_id for calls; _build_participants handles None
            "chat_name": None,
            "text_data": None,
            "quoted_key_id": None,
            "mime_type": None,
            "media_path": None,
            "revoked": False,
            "call": {
                "direction": direction,
                "kind": kind,
                "duration": int(duration),
            },
        })
    return result


def _group_participants(
    con: sqlite3.Connection,
    chat_jid_row_id: int,
    jid_map: dict[int, str],
) -> list[str]:
    """Return participant JIDs for a group chat (empty list for 1:1)."""
    if not _table_exists(con, "group_participant_user"):
        return []
    rows = con.execute(
        "SELECT user_jid_row_id FROM group_participant_user WHERE group_jid_row_id = ?",
        (chat_jid_row_id,),
    ).fetchall()
    return [jid_map[r[0]] for r in rows if r[0] in jid_map]


# ── Frontmatter parsing (existing files) ─────────────────────────────────────────

def _manifest_dedup_key(entry: dict) -> str | None:
    """Return the dedup key for a manifest entry.

    Regular messages use ``key_id``; call entries (id:5e19) use ``call_id`` as
    the manifest-level stable identifier.  Both are stored under ``key_id`` in
    the dict so existing dedup logic works uniformly, but calls also carry
    ``call_id`` for explicit identification in the manifest YAML.
    """
    return entry.get("key_id") or entry.get("call_id")


def _load_existing_manifest(path: Path) -> dict[str, dict]:
    """Return {dedup_key: manifest_entry} from an existing day file, or {} if missing.

    Dedup key = ``key_id`` for messages, ``call_id`` for call entries (id:5e19).
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fm = yaml.safe_load(text[4:end]) or {}
    result = {}
    for entry in fm.get("messages", []):
        k = _manifest_dedup_key(entry)
        if k:
            result[k] = entry
    return result


# ── File rendering ────────────────────────────────────────────────────────────────

def _sha256_from_cas_rel(cas_rel: str) -> str:
    """Extract the sha256 hex digest from a CAS-relative path (``…/_objects/aa/rest``)."""
    parts = Path(cas_rel).parts
    # last two parts: <sha[:2]> / <sha[2:]>
    return parts[-2] + parts[-1]


def _render_file(
    *,
    chat_jid: str,
    chat_name: str | None,
    day_str: str,
    thread_id: str,
    participants: list[dict],
    messages: list[dict],
) -> str:
    """Render a complete per-chat-day .md file (frontmatter + body)."""
    manifest = []
    for m in messages:
        nc = m.get("number_change")
        call_info = m.get("call")
        if call_info:
            # Call entry (id:5e19): messaging-namespaced message_type, keyed by call_id.
            entry = {
                "call_id": m["call_id"],
                "timestamp": m["ts"].isoformat(),
                "sender_jid": m["sender_jid"],
                "message_type": "call",
                "call": call_info,
            }
        elif m["revoked"]:
            status = "revoked"
            entry = {
                "key_id": m["key_id"],
                "timestamp": m["ts"].isoformat(),
                "sender_jid": m["sender_jid"],
                "status": status,
            }
        else:
            status = "sent"
            entry = {
                "key_id": m["key_id"],
                "timestamp": m["ts"].isoformat(),
                "sender_jid": m["sender_jid"],
                "status": status,
            }
            if nc:
                # Persist message_type + number_change so reconstitution rebuilds the system line.
                # message_type: system is messaging-namespaced; status: stays core-owned (roadmap:cfd1).
                entry["message_type"] = "system"
                entry["number_change"] = {"old": nc["old"], "new": nc["new"]}
            else:
                # Persist text so reconstitution is lossless (roadmap:w6f).
                if m.get("mime_type") or m.get("media_path"):
                    # Media: persist mime + sha256 so cas_rel can be re-derived.
                    cas_rel = m.get("cas_rel")
                    if cas_rel:
                        entry["media"] = {
                            "mime": m["mime_type"] or "application/octet-stream",
                            "sha256": _sha256_from_cas_rel(cas_rel),
                        }
                else:
                    if m.get("text_data") is not None:
                        entry["text"] = m["text_data"]
                if m.get("quoted_key_id"):
                    entry["quoted_key_id"] = m["quoted_key_id"]
        manifest.append(entry)

    fm: dict = {
        "source": PLUGIN_NAME,
        "date": day_str,
        "tags": [],
        "thread_id": thread_id,
        "chat_jid": chat_jid,
        "participants": participants,
        "messages": manifest,
        "processor": PLUGIN_NAME,
        "processor_version": PLUGIN_VERSION,
    }
    if chat_name:
        fm["chat_name"] = chat_name

    # Name lookup: address → display name
    name_map = {p["address"]: p.get("name") for p in participants}

    lines = []
    for m in messages:
        sender = name_map.get(m["sender_jid"]) or m["sender_jid"]
        time_str = m["ts"].strftime("%H:%M")

        nc = m.get("number_change")
        call_info = m.get("call")
        if call_info:
            # Call line (id:5e19). Wording is a REVIEW_ME judgment call.
            direction = call_info["direction"]   # incoming / outgoing
            kind = call_info["kind"]             # voice / video
            duration = call_info["duration"]
            if duration:
                body = f"«call: {direction} {kind}, {duration}s»"
            else:
                body = f"«call: {direction} {kind}, missed»"
            lines.append(f"[{time_str}] {sender}: {body} <!-- call_id: {m['call_id']} -->")
        elif nc:
            body = f"«number change: {nc['old']} → {nc['new']}»"
            prefix = ""
            lines.append(f"[{time_str}] {sender}: {prefix}{body} <!-- key_id: {m['key_id']} -->")
        elif m["revoked"]:
            lines.append(f"[{time_str}] {sender}: {_DELETED_SENTINEL} <!-- key_id: {m['key_id']} -->")
        elif m["media_path"] or m["mime_type"]:
            cas_rel = m.get("cas_rel")
            if cas_rel:
                body = f"[media: {m['mime_type']} → {cas_rel}]"
            else:
                body = f"[media: {m['mime_type'] or 'application/octet-stream'}]"
            prefix = ""
            if m["quoted_key_id"]:
                prefix = f"{_REPLY_INDICATOR} (re: {m['quoted_key_id']}) "
            lines.append(f"[{time_str}] {sender}: {prefix}{body} <!-- key_id: {m['key_id']} -->")
        else:
            body = m["text_data"] or ""
            prefix = ""
            if m["quoted_key_id"]:
                prefix = f"{_REPLY_INDICATOR} (re: {m['quoted_key_id']}) "
            lines.append(f"[{time_str}] {sender}: {prefix}{body} <!-- key_id: {m['key_id']} -->")

    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    body_str = "\n".join(lines)
    return f"---\n{yaml_str}---\n\n{body_str}\n"


# ── WAL-safe source resolution ────────────────────────────────────────────────────

def _wal_safe_source(source_db: Path) -> tuple[Path, Path | None]:
    """Return a db path safe to open without mutating the source.

    If a non-empty sibling <db>-wal exists, copy the db + -wal + -shm trio to a
    tempdir and checkpoint the copy (TRUNCATE) so reads include all committed frames.
    The caller owns the tempdir and must shutil.rmtree it when done.

    If no -wal is present (or it is already empty), the original path is returned
    unchanged and tempdir is None.
    """
    wal = source_db.with_name(source_db.name + "-wal")
    if not wal.exists() or wal.stat().st_size == 0:
        return source_db, None
    tmp = Path(tempfile.mkdtemp(prefix="zkm-wa-"))
    db_copy = tmp / source_db.name
    shutil.copy2(source_db, db_copy)
    for suffix in ("-wal", "-shm"):
        sib = source_db.with_name(source_db.name + suffix)
        if sib.exists():
            shutil.copy2(sib, tmp / sib.name)
    _con = sqlite3.connect(db_copy)
    _con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    _con.commit()
    _con.close()
    return db_copy, tmp


# ── Main entry point ─────────────────────────────────────────────────────────────

def _assert_sqlite_source(source_db: Path) -> None:
    """Fail early + clearly if source_db isn't a decrypted SQLite DB.

    Avoids the opaque ``sqlite3.DatabaseError: file is not a database`` deep in a
    query when the user points source_db at an encrypted .crypt14/15 backup or a
    failed decryption.
    """
    if not source_db.exists():
        raise FileNotFoundError(f"whatsapp source_db not found: {source_db}")
    with open(source_db, "rb") as f:
        if f.read(16) != b"SQLite format 3\x00":
            raise ValueError(
                f"whatsapp source_db is not a SQLite database: {source_db}\n"
                "It looks like an encrypted .crypt12/14/15 backup or a failed decryption. "
                "Decrypt it first (fetch-role) — see docs/merge-old-backup.md."
            )


def convert(
    store_path: Path,
    config: dict,
    *,
    progress: ProgressCallback | None = None,
) -> list[Path]:
    source_db = Path(config["source_db"]).expanduser().resolve()
    _assert_sqlite_source(source_db)
    tz: TzInfo = ZoneInfo(config["timezone"]) if "timezone" in config else (datetime.now().astimezone().tzinfo or ZoneInfo("UTC"))
    # media_root anchors the *relative* file_path values stored in message_media
    # (e.g. "Media/WhatsApp Voice Notes/…/x.opus") to the on-disk WhatsApp media
    # tree. Without it those relative paths never resolve and media is skipped.
    media_root = (
        Path(config["media_root"]).expanduser().resolve() if config.get("media_root") else None
    )
    media_stats = {"stored": 0, "missing": 0}

    db_state = load_state(store_path, source_db)
    watermark_ms: int = db_state.get("watermark_ms", 0)

    db_to_open, tmpdir = _wal_safe_source(source_db)
    con = sqlite3.connect(db_to_open)
    con.row_factory = sqlite3.Row

    try:
        jid_map = _build_jid_map(con)

        # Resolve owner_jid: explicit config overrides; otherwise auto-detect; fallback to default.
        if "owner_jid" in config:
            owner_jid: str = config["owner_jid"]
        else:
            owner_jid = _detect_owner_jid(con) or "owner@s.whatsapp.net"
        msg_cols = _table_columns(con, "message")
        has_revoked_col = "revoked" in msg_cols
        has_quoted = _table_exists(con, "message_quoted")
        has_media = _table_exists(con, "message_media")
        has_number_change = _table_exists(con, "message_system_number_change")

        rows = _query_messages(
            con, watermark_ms,
            has_revoked_col=has_revoked_col,
            has_quoted_table=has_quoted,
            has_media_table=has_media,
            has_number_change_table=has_number_change,
        )

        # Group new rows by (chat_jid, day_str)
        by_chat_day: dict[tuple[str, str], list[dict]] = defaultdict(list)
        max_ts_ms = watermark_ms
        for row in rows:
            chat_jid = jid_map.get(row["chat_jid_row_id"], f"unknown@{row['chat_jid_row_id']}")
            ts_ms: int = row["timestamp"]
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=tz)
            day_str = ts.strftime("%Y-%m-%d")

            if row["from_me"]:
                sender_jid = owner_jid
            elif row["sender_jid_row_id"] and row["sender_jid_row_id"] in jid_map:
                sender_jid = jid_map[row["sender_jid_row_id"]]
            else:
                sender_jid = chat_jid

            # Resolve number_change JIDs if present (roadmap:w11).
            nc_old = row["nc_old_jid_row_id"]
            nc_new = row["nc_new_jid_row_id"]
            number_change = None
            if nc_old is not None and nc_new is not None:
                old_jid = jid_map.get(nc_old)
                new_jid = jid_map.get(nc_new)
                if old_jid and new_jid:
                    number_change = {"old": old_jid, "new": new_jid}

            msg_dict: dict = {
                "key_id": row["key_id"],
                "ts": ts,
                "timestamp_ms": ts_ms,
                "from_me": bool(row["from_me"]),
                "sender_jid": sender_jid,
                "text_data": row["text_data"],
                "chat_jid_row_id": row["chat_jid_row_id"],
                "chat_name": row["chat_name"],
                "quoted_key_id": row["quoted_key_id"],
                "mime_type": row["mime_type"],
                "media_path": row["media_path"],
                "revoked": bool(row["revoked"]),
            }
            if number_change:
                msg_dict["number_change"] = number_change
            by_chat_day[(chat_jid, day_str)].append(msg_dict)
            if ts_ms > max_ts_ms:
                max_ts_ms = ts_ms

        # Merge call_log rows into the per-day stream (id:5e19).
        call_rows = _query_calls(con, watermark_ms, jid_map, owner_jid, tz)
        for call_dict in call_rows:
            chat_jid = call_dict.pop("chat_jid")  # consumed here; not in message shape
            day_str = call_dict["ts"].strftime("%Y-%m-%d")
            by_chat_day[(chat_jid, day_str)].append(call_dict)
            if call_dict["timestamp_ms"] > max_ts_ms:
                max_ts_ms = call_dict["timestamp_ms"]

        inbox_index: dict[str, Path] = build_canonical_index(store_path, "inbox/whatsapp")
        written: list[Path] = []
        total = len(by_chat_day)

        for i, ((chat_jid, day_str), new_msgs) in enumerate(sorted(by_chat_day.items())):
            if progress:
                progress(i, total, f"{chat_jid} {day_str}")

            tid = _thread_id(chat_jid)
            out_dir = _thread_dir(store_path, tid)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{day_str}.md"

            # Merge with existing manifest (dedup on key_id)
            existing = _load_existing_manifest(out_path)
            new_by_key = {m["key_id"]: m for m in new_msgs}
            if not (set(new_by_key) - set(existing)):
                continue  # all new key_ids already in file → skip (no change)

            all_msgs_by_key = {**{k: _reconstitute(v, tz, thread_id=tid) for k, v in existing.items()}, **new_by_key}
            all_msgs = sorted(all_msgs_by_key.values(), key=lambda m: (m["timestamp_ms"], m["key_id"]))

            # Determine participants; use the first regular message for chat metadata
            # (call dicts have chat_jid_row_id=None / chat_name=None by design).
            sample = next((m for m in new_msgs if m.get("chat_jid_row_id") is not None), new_msgs[0])
            participants = _build_participants(
                con, chat_jid, sample.get("chat_jid_row_id"), jid_map, owner_jid, all_msgs
            )

            # Handle media → CAS + inbox symlink (W6)
            for m in all_msgs:
                if m.get("media_path"):
                    stored = _handle_media(
                        m, store_path, tid, out_path, chat_jid, inbox_index, media_root
                    )
                    media_stats["stored" if stored else "missing"] += 1

            # Pick chat_name from the first regular message (calls carry None).
            chat_name = next(
                (m.get("chat_name") for m in new_msgs if m.get("chat_name") is not None), None
            )
            rendered = _render_file(
                chat_jid=chat_jid,
                chat_name=chat_name,
                day_str=day_str,
                thread_id=tid,
                participants=participants,
                messages=all_msgs,
            )
            write_atomic(out_path, rendered)
            written.append(out_path)

    finally:
        con.close()
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)

    if max_ts_ms > watermark_ms:
        save_state(store_path, source_db, {"watermark_ms": max_ts_ms})

    if media_stats["missing"]:
        hint = (
            "set `media_root` to the WhatsApp data dir (the parent of `Media/`)"
            if media_root is None
            else f"check that the files exist under media_root={media_root}"
        )
        log.warning(
            "whatsapp: %d media file(s) stored, %d not found — %s",
            media_stats["stored"],
            media_stats["missing"],
            hint,
        )

    # Regenerate the human-readable by-name/ symlink view (id:8040).
    _regenerate_name_view(store_path)

    return written


# ── Manifest heal + media backfill (reprocess) ─────────────────────────────────────

def _heal_meta_by_key_id(con: sqlite3.Connection) -> dict[str, dict]:
    """Return {key_id: {text_data, quoted_key_id, mime_type, file_path, number_change}}.

    Re-derives — straight from the DB — every field ``_reconstitute`` needs to rebuild
    a message losslessly. Used to heal pre-w6f (0.2.0) day-files whose manifests stored
    only key_id/sender/status/timestamp, so a merge-triggered rewrite no longer blanks
    text/replies/media/system lines.
    """
    has_quoted = _table_exists(con, "message_quoted")
    has_media = _table_exists(con, "message_media")
    has_nc = _table_exists(con, "message_system_number_change")
    jid_map = _build_jid_map(con) if has_nc else {}

    quoted_col = "mq.key_id AS quoted_key_id" if has_quoted else "NULL AS quoted_key_id"
    quoted_join = "LEFT JOIN message_quoted mq ON mq.message_row_id = m._id" if has_quoted else ""
    media_cols = (
        "mm.mime_type, mm.file_path AS media_path" if has_media
        else "NULL AS mime_type, NULL AS media_path"
    )
    media_join = "LEFT JOIN message_media mm ON mm.message_row_id = m._id" if has_media else ""
    nc_cols = (
        "nc.old_jid_row_id AS nc_old, nc.new_jid_row_id AS nc_new" if has_nc
        else "NULL AS nc_old, NULL AS nc_new"
    )
    nc_join = (
        "LEFT JOIN message_system_number_change nc ON nc.message_row_id = m._id" if has_nc else ""
    )
    rows = con.execute(f"""
        SELECT m.key_id, m.text_data, {quoted_col}, {media_cols}, {nc_cols}
        FROM message m
        {quoted_join}
        {media_join}
        {nc_join}
    """).fetchall()

    meta: dict[str, dict] = {}
    for r in rows:
        if not r["key_id"]:
            continue
        number_change = None
        if r["nc_old"] is not None and r["nc_new"] is not None:
            old_jid, new_jid = jid_map.get(r["nc_old"]), jid_map.get(r["nc_new"])
            if old_jid and new_jid:
                number_change = {"old": old_jid, "new": new_jid}
        meta[r["key_id"]] = {
            "text_data": r["text_data"],
            "quoted_key_id": r["quoted_key_id"],
            "mime_type": r["mime_type"],
            "file_path": r["media_path"],
            "number_change": number_change,
        }
    return meta


def _patch_media_body_line(body: str, key_id: str, mime: str | None, cas_rel: str) -> str:
    """Rewrite the single body line for ``key_id`` from a bare media placeholder
    to the CAS-linked form, leaving every other line (incl. message text) untouched."""
    marker = f"<!-- key_id: {key_id} -->"
    mime_txt = mime or "application/octet-stream"
    bare = f"[media: {mime_txt}]"
    full = f"[media: {mime_txt} → {cas_rel}]"
    out = []
    for line in body.split("\n"):
        if marker in line and bare in line:
            line = line.replace(bare, full)
        out.append(line)
    return "\n".join(out)


def _heal_day_file(
    md: Path,
    store_path: Path,
    meta_map: dict[str, dict],
    media_root: Path | None,
    inbox_index: dict[str, Path],
) -> bool:
    """Make one day-file's manifest lossless + CAS its media. Returns True if changed.

    Surgical and non-destructive: it only ADDS missing manifest fields (text,
    quoted_key_id, media, message_type/number_change — sourced from the DB) and rewrites
    media body lines to the CAS form. Message text in the body and every other line stay
    byte-for-byte. Idempotent: nothing to add → no rewrite. After healing, a
    merge-triggered rewrite reconstitutes losslessly.
    """
    text = md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    end = text.find("\n---\n", 4)
    if end == -1:
        return False
    fm = yaml.safe_load(text[4:end]) or {}
    body_after = text[end + 5:]  # "\n" + body + "\n" — preserved except media lines

    chat_jid = fm.get("chat_jid")
    tid = fm.get("thread_id")
    if not chat_jid or not tid:
        return False

    changed = False
    for entry in fm.get("messages", []):
        kid = entry.get("key_id")
        meta = meta_map.get(kid) if kid else None
        if meta is None:
            continue

        # System / number-change event — persist so reconstitution rebuilds the line.
        if meta["number_change"] and entry.get("message_type") != "system":
            entry["message_type"] = "system"
            entry["number_change"] = meta["number_change"]
            changed = True
            continue
        if entry.get("status") == "revoked" or entry.get("message_type") == "system":
            continue  # revoked/system carry no text or media

        # Reply linkage.
        if meta["quoted_key_id"] and not entry.get("quoted_key_id"):
            entry["quoted_key_id"] = meta["quoted_key_id"]
            changed = True

        if meta["mime_type"] or meta["file_path"]:
            # Media message: CAS the bytes (if resolvable) and/or persist the kind.
            if (entry.get("media") or {}).get("sha256"):
                continue  # already fully ingested
            mime = meta["mime_type"]
            stored = False
            if meta["file_path"]:
                msg = {"key_id": kid, "media_path": meta["file_path"], "mime_type": mime}
                if _handle_media(msg, store_path, tid, md, chat_jid, inbox_index, media_root):
                    entry["media"] = {
                        "mime": mime or "application/octet-stream",
                        "sha256": _sha256_from_cas_rel(msg["cas_rel"]),
                    }
                    body_after = _patch_media_body_line(body_after, kid, mime, msg["cas_rel"])
                    stored = changed = True
            if not stored and "media" not in entry:
                # Preserve the media kind even without bytes (renders [media: <mime>]).
                entry["media"] = {"mime": mime or "application/octet-stream"}
                changed = True
        elif "text" not in entry and meta["text_data"] is not None:
            # Plain text message — persist text so a future rewrite keeps it.
            entry["text"] = meta["text_data"]
            changed = True

    if not changed:
        return False
    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    write_atomic(md, f"---\n{yaml_str}---\n{body_after}")
    return True


def reprocess(
    store_path: Path,
    config: dict,
    candidates: list[Path],
    *,
    progress: ProgressCallback | None = None,
) -> list[Path]:
    """Heal existing day-files' manifests + backfill media. Returns changed paths.

    Two jobs, both watermark-independent, non-destructive and idempotent:

    1. **Manifest heal** — pre-w6f (0.2.0) day-files stored only key_id/sender/status/
       timestamp, so a merge that rewrites a day would blank its text/replies/media.
       This re-derives text/quoted/media/number_change from the DB by key_id and writes
       the missing fields into the manifest (body left intact), making rewrites lossless.
       Required before merging an additional source DB (e.g. an older phone backup).
    2. **Media backfill** — for media messages, CAS the actual bytes (via ``media_root``)
       and rewrite the ``[media: …]`` body line to the CAS-linked form, so amenders
       (zkm-stt) can transcribe them. Needs ``media_root``; without it, the heal still
       runs (text/replies) and media kind is preserved as a bare placeholder.

    Triggered by ``zkm convert whatsapp --reprocess-all`` (core passes managed
    day-files as ``candidates``).
    """
    source_db = Path(config["source_db"]).expanduser().resolve()
    media_root = (
        Path(config["media_root"]).expanduser().resolve() if config.get("media_root") else None
    )
    if not candidates:
        return []
    if media_root is None:
        log.warning(
            "whatsapp: --reprocess-all running manifest heal only; set `media_root` "
            "(the WhatsApp data dir, parent of `Media/`) to also CAS media bytes."
        )

    db_to_open, tmpdir = _wal_safe_source(source_db)
    con = sqlite3.connect(db_to_open)
    con.row_factory = sqlite3.Row
    written: list[Path] = []
    try:
        meta_map = _heal_meta_by_key_id(con)
        inbox_index = build_canonical_index(store_path, "inbox/whatsapp")
        total = len(candidates)
        for i, md in enumerate(candidates):
            if progress is not None:
                progress(i, total, str(md))
            if _heal_day_file(md, store_path, meta_map, media_root, inbox_index):
                written.append(md)
    finally:
        con.close()
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)

    log.info("whatsapp: reprocess healed/backfilled %d day-file(s)", len(written))
    return written


# ── Helpers ───────────────────────────────────────────────────────────────────────

def _reconstitute(entry: dict, tz: TzInfo, *, thread_id: str | None = None) -> dict:
    """Re-create a message dict from a manifest entry (for merging with existing files).

    Handles three entry shapes:
    - Regular messages: ``key_id``, ``status``, optional ``text``/``quoted_key_id``/``media``
    - System events (id:w11): ``message_type: system``, ``number_change``
    - Call entries (id:5e19): ``call_id``, ``message_type: call``, ``call: {direction, kind, duration}``

    Old entries without new keys load without error (bodies stay blank).
    Pass ``thread_id`` to enable re-derivation of ``cas_rel`` for media entries.
    """
    ts = datetime.fromisoformat(entry["timestamp"]).astimezone(tz)
    message_type = entry.get("message_type")

    # Call entry (id:5e19): keyed by call_id, carries message_type: call.
    if message_type == "call":
        call_id = entry["call_id"]
        call_info = entry.get("call", {})
        return {
            "key_id": call_id,        # dedup key
            "call_id": call_id,
            "ts": ts,
            "timestamp_ms": int(ts.timestamp() * 1000),
            "from_me": False,
            "sender_jid": entry["sender_jid"],
            "text_data": None,
            "chat_jid_row_id": None,
            "chat_name": None,
            "quoted_key_id": None,
            "mime_type": None,
            "media_path": None,
            "revoked": False,
            "call": call_info,
        }

    status = entry.get("status", "sent")
    revoked = status == "revoked"
    # Detect system events via message_type (roadmap:cfd1; avoids colliding with core status: enum).
    is_system = message_type == "system"

    # Recover number_change data for system events (roadmap:w11).
    number_change: dict | None = entry.get("number_change") if is_system else None

    # Recover media info and re-derive cas_rel from stored sha256 (roadmap:w6f).
    mime_type: str | None = None
    cas_rel: str | None = None
    media = entry.get("media")
    if media and thread_id:
        mime_type = media.get("mime")
        sha = media.get("sha256", "")
        if sha:
            cas_rel = f"{_thread_rel(thread_id)}/originals/_objects/{sha[:2]}/{sha[2:]}"
    elif media:
        mime_type = media.get("mime")

    msg: dict = {
        "key_id": entry["key_id"],
        "ts": ts,
        "timestamp_ms": int(ts.timestamp() * 1000),
        "from_me": False,
        "sender_jid": entry["sender_jid"],
        "text_data": entry.get("text"),
        "chat_jid_row_id": None,
        "chat_name": None,
        "quoted_key_id": entry.get("quoted_key_id"),
        "mime_type": mime_type,
        # media_path=None: do not re-run _handle_media on stale paths (roadmap:w6f).
        "media_path": None,
        "revoked": revoked,
    }
    if cas_rel:
        msg["cas_rel"] = cas_rel
    if number_change:
        msg["number_change"] = number_change
    return msg


def _build_participants(
    con: sqlite3.Connection,
    chat_jid: str,
    chat_jid_row_id: int | None,
    jid_map: dict[int, str],
    owner_jid: str,
    messages: list[dict],
) -> list[dict]:
    is_group = chat_jid.endswith("@g.us")

    if is_group and chat_jid_row_id is not None:
        member_jids = _group_participants(con, chat_jid_row_id, jid_map)
    else:
        member_jids = list({m["sender_jid"] for m in messages} | {owner_jid})

    seen: set[str] = set()
    result: list[dict] = []
    for jid in member_jids:
        if jid in seen:
            continue
        seen.add(jid)
        result.append({"address": jid, "role": "member"})

    if owner_jid not in seen:
        result.append({"address": owner_jid, "role": "member"})
    return result


def _ext_for_mime(mime: str | None) -> str:
    """Return a file extension (with leading dot) for *mime*, or empty string."""
    if not mime:
        return ""
    ext = mimetypes.guess_extension(mime, strict=False)
    return ext or ""


def _resolve_media_path(raw: str, media_root: Path | None) -> Path | None:
    """Resolve a message_media file_path to an existing file, or None.

    msgstore.db stores media as paths relative to the WhatsApp data dir
    (e.g. "Media/WhatsApp Voice Notes/…/x.opus"). An absolute path is used
    as-is; a relative one is anchored under ``media_root`` when configured.
    """
    p = Path(raw)
    if p.is_absolute():
        return p if p.exists() else None
    if media_root is not None:
        cand = media_root / p
        if cand.exists():
            return cand
    # Last resort: relative to cwd (preserves legacy behaviour for abs-ish paths).
    return p if p.exists() else None


def _handle_media(
    m: dict,
    store_path: Path,
    tid: str,
    out_path: Path,
    chat_jid: str,
    inbox_index: dict[str, Path],
    media_root: Path | None = None,
) -> bool:
    """Store media file in CAS, create inbox symlink + .origin.json sidecar (W6).

    Returns True if the media file was found and stored, False if it could not
    be located (so the caller can count and surface missing-media totals).
    """
    resolved = _resolve_media_path(m["media_path"], media_root)
    if resolved is None:
        return False
    media_path = resolved
    subdir = f"{_thread_rel(tid)}/originals"
    try:
        cas_path = write_object(store_path, subdir, media_path)
        m["cas_rel"] = str(cas_path.relative_to(store_path))

        message_id = f"whatsapp:{chat_jid}:{m['key_id']}"
        link_name = media_path.name or f"{m['key_id']}{_ext_for_mime(m.get('mime_type'))}"
        symlink_with_sidecar(
            cas_object=cas_path,
            link_dir=store_path / "inbox" / "whatsapp" / tid,
            link_name=link_name,
            producer={
                "plugin": PLUGIN_NAME,
                "message": str(out_path.relative_to(store_path)),
                "sha256": hashlib.sha256(message_id.encode()).hexdigest(),
            },
            canonical_index=inbox_index,
        )
        return True
    except Exception:
        # The file exists (resolved above) but storing it failed — a real error
        # (permissions, disk, CAS bug), NOT "media absent". Surface it per-item
        # rather than aborting the whole convert; don't swallow it silently.
        log.warning(
            "whatsapp: failed to store media %s (key_id=%s)", media_path, m.get("key_id"),
            exc_info=True,
        )
        return False
