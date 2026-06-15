#!/usr/bin/env bash
# Auto-decrypt a syncthing'd (or otherwise synced) WhatsApp backup into the zkm inbox
# `source_db`, then run `zkm convert whatsapp` so transcripts stay current.
#
# Meant to be triggered by zkm-whatsapp-decrypt.path (systemd --user) whenever the
# backup folder changes; idempotent via the newer-than guard, so repeated triggers
# (or a backstop timer) are cheap no-ops.
#
# Configure via environment variables (defaults below are examples — edit to taste).
# The backup key is read from the OS keyring (libsecret) — never stored on disk —
# the same way tools like mbsync's PassCmd do. Store it once:
#   secret-tool store --label="whatsapp backup key" service zkm/whatsapp account backup
#
# wa_decrypt_pilot.py needs `wa-crypt-tools`, which is deliberately NOT a zkm-whatsapp
# dependency (decryption is out of convert() scope); it is provided ephemerally via
# `uv run --with`.
set -euo pipefail

CRYPT15="${WA_CRYPT15:-$HOME/Sync/WhatsApp/Databases/msgstore.db.crypt15}"  # synced backup
OUT="${WA_OUT:-$HOME/knowledge/inbox/whatsapp/msgstore.db}"                 # = zkm whatsapp.source_db
KEYREF="${WA_KEYREF:-keyring:zkm/whatsapp:backup}"                          # keyring:<service>:<account>
REPO="${WA_REPO:-$HOME/src/zkm-whatsapp}"                                   # this plugin's checkout
STORE="${WA_STORE:-$HOME/knowledge}"                                       # zkm store root
ZKM="${ZKM_BIN:-zkm}"  # systemd --user has a minimal PATH; set an absolute path if needed
LOCK="${WA_LOCK:-${OUT%/*}/.wa-decrypt.lock}"

mkdir -p "$(dirname "$OUT")"
exec 9>"$LOCK"
flock -n 9 || { echo "zkm-whatsapp-decrypt: already running, skipping"; exit 0; }

[[ -f "$CRYPT15" ]] || { echo "zkm-whatsapp-decrypt: no backup at $CRYPT15"; exit 0; }

# Idempotent: skip the pipeline when the decrypted db is already at least as new as the
# backup (so triggers for unrelated files in the folder are cheap no-ops).
if [[ -f "$OUT" && "$OUT" -nt "$CRYPT15" ]]; then
  echo "zkm-whatsapp-decrypt: $OUT already current; skipping"
  exit 0
fi

# Decrypt to a temp file, then atomic rename so `zkm convert` never sees a half-written db.
TMP="$(mktemp "${OUT}.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
cd "$REPO"
uv run --with wa-crypt-tools python scripts/wa_decrypt_pilot.py \
    --key-source "$KEYREF" "$CRYPT15" "$TMP"
mv -f "$TMP" "$OUT"
trap - EXIT
echo "zkm-whatsapp-decrypt: wrote $OUT from $(basename "$CRYPT15")"

# Keep the knowledge base current. --no-amenders so an unattended run never blocks on a
# local amender/expand model; run a full `zkm convert whatsapp` by hand for amendments.
cd "$STORE"
"$ZKM" convert whatsapp --no-amenders
echo "zkm-whatsapp-decrypt: zkm convert whatsapp done"
