"""Spec for roadmap:w-key — resolve the WhatsApp backup key from secret agents.

Hermetic: `bw` / `secret-tool` are FAKE executables written into a tmp dir that
is prepended to PATH. No real secrets, no network, no vault.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from keysource import KeySourceError, resolve_backup_key

VALID_KEY = "0123456789abcdef" * 4  # 64 hex chars
MIXED_CASE_KEY = "0123456789ABCDEF" * 4


@pytest.fixture()
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Return a factory that installs a fake executable on PATH.

    The fake logs its argv to <name>.argv and prints *stdout*; *exit_code*
    controls the return code, *stderr* goes to stderr.
    """
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    def install(name: str, stdout: str, *, exit_code: int = 0, stderr: str = "") -> Path:
        argv_log = bin_dir / f"{name}.argv"
        script = bin_dir / name
        script.write_text(
            "#!/bin/sh\n"
            f'echo "$@" > "{argv_log}"\n'
            + (f"printf '%s' '{stderr}' >&2\n" if stderr else "")
            + f"printf '%s' '{stdout}'\n"
            f"exit {exit_code}\n"
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return argv_log

    return install


# ── happy paths ─────────────────────────────────────────────────────────────────

def test_bitwarden_scheme_calls_bw(fake_bin):  # roadmap:w-key
    argv_log = fake_bin("bw", VALID_KEY)
    assert resolve_backup_key("bitwarden:item-123") == VALID_KEY
    assert argv_log.read_text().split() == ["get", "password", "item-123"]


def test_keyring_scheme_calls_secret_tool(fake_bin):  # roadmap:w-key
    argv_log = fake_bin("secret-tool", VALID_KEY)
    assert resolve_backup_key("keyring:whatsapp:backup") == VALID_KEY
    assert argv_log.read_text().split() == [
        "lookup", "service", "whatsapp", "account", "backup",
    ]


def test_strips_surrounding_whitespace(fake_bin):  # roadmap:w-key
    fake_bin("bw", f"  {VALID_KEY}\n\n")
    assert resolve_backup_key("bitwarden:item-123") == VALID_KEY


def test_preserves_hex_case(fake_bin):  # roadmap:w-key
    fake_bin("bw", MIXED_CASE_KEY)
    assert resolve_backup_key("bitwarden:item-123") == MIXED_CASE_KEY


# ── validation ──────────────────────────────────────────────────────────────────

def test_rejects_non_hex_output(fake_bin):  # roadmap:w-key
    fake_bin("bw", "not-a-key-at-all-not-a-key-at-all-not-a-key-at-all-not-a-key-too")
    with pytest.raises(KeySourceError) as exc:
        resolve_backup_key("bitwarden:item-123")
    assert "not-a-key" not in str(exc.value)  # never echo the material


def test_rejects_wrong_length(fake_bin):  # roadmap:w-key
    fake_bin("bw", VALID_KEY[:-1])  # 63 hex chars
    with pytest.raises(KeySourceError):
        resolve_backup_key("bitwarden:item-123")


def test_error_message_never_contains_key_material(fake_bin):  # roadmap:w-key
    fake_bin("bw", VALID_KEY[:-1])
    with pytest.raises(KeySourceError) as exc:
        resolve_backup_key("bitwarden:item-123")
    assert VALID_KEY[:-1] not in str(exc.value)


# ── source-string parsing ───────────────────────────────────────────────────────

def test_unknown_scheme_raises(fake_bin):  # roadmap:w-key
    with pytest.raises(KeySourceError):
        resolve_backup_key("vault:something")


def test_malformed_source_without_colon_raises(fake_bin):  # roadmap:w-key
    with pytest.raises(KeySourceError):
        resolve_backup_key("bitwarden")


def test_keyring_missing_account_raises(fake_bin):  # roadmap:w-key
    with pytest.raises(KeySourceError):
        resolve_backup_key("keyring:onlyservice")


# ── subprocess failure modes ────────────────────────────────────────────────────

def test_missing_binary_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # roadmap:w-key
    empty = tmp_path / "emptybin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    with pytest.raises(KeySourceError) as exc:
        resolve_backup_key("bitwarden:item-123")
    assert "bw" in str(exc.value)


def test_nonzero_exit_surfaces_stderr(fake_bin):  # roadmap:w-key
    fake_bin("bw", "", exit_code=1, stderr="Vault is locked.")
    with pytest.raises(KeySourceError) as exc:
        resolve_backup_key("bitwarden:item-123")
    assert "Vault is locked." in str(exc.value)
