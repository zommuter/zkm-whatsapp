"""Resolve the WhatsApp backup key from an external secret agent (W-key).

Supported source schemes:

    bitwarden:<item-id>            -> bw get password <item-id>
    keyring:<service>:<account>    -> secret-tool lookup service <service> account <account>

Both shell out to an already-authenticated agent so the 64-char hex backup key
never lands on disk. Used by the fetch-role decryption step
(``scripts/wa_decrypt_pilot.py --key-source ...``), NOT by ``convert()``.

NOTE: this module is deliberately named ``keysource`` (not ``secrets``) — the
plugin directory is inserted into ``sys.path`` by convert.py, so a ``secrets``
module here would shadow the stdlib.
"""

from __future__ import annotations

import re
import shutil
import subprocess

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class KeySourceError(Exception):
    """A backup-key source could not be resolved.

    Messages never contain key material (only lengths / agent stderr).
    """


def resolve_backup_key(source: str) -> str:
    """Resolve *source* to a 64-char hex WhatsApp backup key.

    Raises KeySourceError on unknown scheme, malformed source, missing agent
    binary, non-zero agent exit, or invalid key material.
    """
    scheme, sep, rest = source.partition(":")
    if not sep or not rest:
        raise KeySourceError(
            f"malformed key source {source!r} (expected '<scheme>:<...>')"
        )

    if scheme == "bitwarden":
        argv = ["bw", "get", "password", rest]
    elif scheme == "keyring":
        service, sep2, account = rest.partition(":")
        if not sep2 or not service or not account:
            raise KeySourceError(
                "malformed keyring source (expected 'keyring:<service>:<account>')"
            )
        argv = ["secret-tool", "lookup", "service", service, "account", account]
    else:
        raise KeySourceError(f"unknown key source scheme {scheme!r}")

    if shutil.which(argv[0]) is None:
        raise KeySourceError(
            f"{argv[0]!r} not found on PATH (required for {scheme!r} key sources)"
        )

    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise KeySourceError(
            f"{argv[0]} exited {proc.returncode}" + (f": {stderr}" if stderr else "")
        )

    key = proc.stdout.strip()
    if not _HEX64.match(key):
        raise KeySourceError(
            f"{scheme} source returned invalid key material "
            f"(expected 64 hex chars, got {len(key)} chars)"
        )
    return key
