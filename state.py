"""Source-state management for zkm-whatsapp.

State file: <store>/.zkm-state/zkm-whatsapp.json
Schema: { "<abs_source_db_path>": { "watermark_ms": <int> } }

Watermark = max(timestamp) of messages imported so far (milliseconds since epoch).
Correctness comes from dedup-on-key_id; the watermark is a speed optimisation only.
Rowid renumber across backup-restore does NOT affect correctness.
"""

from __future__ import annotations

import json
from pathlib import Path

from zkm.atomic import write_atomic

_STATE_FILE = ".zkm-state/zkm-whatsapp.json"


def _state_path(store_path: Path) -> Path:
    return store_path / _STATE_FILE


def load_state(store_path: Path, source_db: Path) -> dict:
    """Return the state dict for *source_db*, or {} if not yet recorded."""
    path = _state_path(store_path)
    if not path.exists():
        return {}
    all_state: dict = json.loads(path.read_text())
    return all_state.get(str(source_db.resolve()), {})


def save_state(store_path: Path, source_db: Path, state: dict) -> None:
    """Persist *state* for *source_db* (merges with other source_db entries)."""
    path = _state_path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    all_state: dict = {}
    if path.exists():
        all_state = json.loads(path.read_text())
    all_state[str(source_db.resolve())] = state
    write_atomic(path, json.dumps(all_state, indent=2, ensure_ascii=False))
