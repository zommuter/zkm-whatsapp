#!/usr/bin/env python3
"""Decrypt an encrypted WhatsApp msgstore backup (fetch-role pilot; out of convert() scope).

Handles crypt12/14/15 — the crypt version is auto-detected from the file header.

Key sources (mutually exclusive):
  positional KEYFILE              either a 64-char hex backup key, OR the raw
                                  Java-serialized `key` file (e.g. from a rooted
                                  phone's /data/data/com.whatsapp/files/key)
  --key-source bitwarden:<id>     bw get password <id>  (hex key)
  --key-source keyring:<svc>:<acct>  secret-tool lookup service <svc> account <acct> (hex key)

Usage:
  wa_decrypt_pilot.py KEYFILE msgstore.db.crypt14 OUT
  wa_decrypt_pilot.py --key-source bitwarden:item-id msgstore.db.crypt15 OUT
"""
from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path

_HEX = set("0123456789abcdefABCDEF")


def _is_hex_key(data: bytes) -> str | None:
    """Return the 64-char hex key if ``data`` is one, else None (→ serialized key file)."""
    try:
        s = data.decode("ascii").strip()
    except UnicodeDecodeError:
        return None
    return s if len(s) == 64 and all(c in _HEX for c in s) else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keyfile", nargs="?", type=Path,
                    help="64-char hex backup key OR the raw Java-serialized `key` file")
    ap.add_argument("encrypted", type=Path, help="encrypted msgstore.db.crypt12/14/15")
    ap.add_argument("out", type=Path, help="output path for the decrypted SQLite db")
    ap.add_argument("--key-source", metavar="SOURCE",
                    help="bitwarden:<item-id> or keyring:<service>:<account> (see keysource.py)")
    args = ap.parse_args()

    if bool(args.keyfile) == bool(args.key_source):
        ap.error("provide exactly one of KEYFILE or --key-source")

    # Heavy imports deferred so --help stays fast (core zkm convention).
    from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
    from wa_crypt_tools.lib.key.keyfactory import KeyFactory

    if args.key_source:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from keysource import KeySourceError, resolve_backup_key
        try:
            key = KeyFactory.from_hex(resolve_backup_key(args.key_source))
        except KeySourceError as e:
            ap.exit(1, f"key source error: {e}\n")
    else:
        hex_key = _is_hex_key(args.keyfile.read_bytes())
        # 64-hex string → from_hex; otherwise treat as the serialized `key` file.
        key = KeyFactory.from_hex(hex_key) if hex_key else KeyFactory.from_file(args.keyfile)

    with open(args.encrypted, "rb") as encrypted:
        db = DatabaseFactory.from_file(encrypted)
        raw = db.decrypt(key, encrypted.read())
    try:
        raw = zlib.decompress(raw)
    except zlib.error:
        pass
    args.out.write_bytes(raw)
    print("Done")


if __name__ == "__main__":
    main()
