#!/usr/bin/env python3
"""Pilot: decrypt msgstore.db.crypt15 reading hex key from file (no cmdline exposure)."""
import sys, zlib
from pathlib import Path
from wa_crypt_tools.lib.key.keyfactory import KeyFactory
from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory

key = KeyFactory.from_hex(Path(sys.argv[1]).read_text().strip())
encrypted = open(sys.argv[2], 'rb')
db = DatabaseFactory.from_file(encrypted)
raw = db.decrypt(key, encrypted.read())
try:
    raw = zlib.decompress(raw)
except zlib.error:
    pass
Path(sys.argv[3]).write_bytes(raw)
print("Done")
