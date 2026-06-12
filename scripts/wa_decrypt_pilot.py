#!/usr/bin/env python3
"""Decrypt msgstore.db.crypt15 (fetch-role pilot; out of convert() scope).

Key sources (mutually exclusive):
  positional KEYFILE              hex key read from a file (no cmdline exposure)
  --key-source bitwarden:<id>     bw get password <id>
  --key-source keyring:<svc>:<acct>  secret-tool lookup service <svc> account <acct>

Usage:
  wa_decrypt_pilot.py KEYFILE CRYPT15 OUT
  wa_decrypt_pilot.py --key-source bitwarden:item-id CRYPT15 OUT
"""
from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("keyfile", nargs="?", type=Path,
                    help="file containing the 64-char hex backup key")
    ap.add_argument("crypt15", type=Path, help="encrypted msgstore.db.crypt15")
    ap.add_argument("out", type=Path, help="output path for the decrypted SQLite db")
    ap.add_argument("--key-source", metavar="SOURCE",
                    help="bitwarden:<item-id> or keyring:<service>:<account> (see keysource.py)")
    args = ap.parse_args()

    if bool(args.keyfile) == bool(args.key_source):
        ap.error("provide exactly one of KEYFILE or --key-source")

    if args.key_source:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from keysource import KeySourceError, resolve_backup_key
        try:
            hex_key = resolve_backup_key(args.key_source)
        except KeySourceError as e:
            ap.exit(1, f"key source error: {e}\n")
    else:
        hex_key = args.keyfile.read_text().strip()

    # Heavy imports deferred so --help stays fast (core zkm convention).
    from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
    from wa_crypt_tools.lib.key.keyfactory import KeyFactory

    key = KeyFactory.from_hex(hex_key)
    with open(args.crypt15, "rb") as encrypted:
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
