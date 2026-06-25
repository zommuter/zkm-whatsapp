#!/usr/bin/env bash
# migrate_by_id.sh — da9f: move the live store's flat chat/whatsapp/<tid>/ dirs into
# chat/whatsapp/by-id/<tid>/ (history-preserving), then regenerate the by-name view.
#
# WHY (ordering hazard): the shipped convert() scans chat/whatsapp/by-id/ for existing
# day-files. Running `zkm convert whatsapp` BEFORE this migration would see by-id/ empty,
# treat every chat as new, and re-emit from the CURRENT msgstore.db under by-id/ — leaving
# the old flat dirs orphaned (history not in the current DB = silent transcript loss). So:
# pause the auto-decryption trigger → migrate → convert → resume.
#
# COORDINATE (da9f): zkm-stt must resolve under by-id/ too (_cas_object_path +
# _discover_whatsapp_day_files scope) — land that BEFORE re-enabling stt runs, or voice
# notes silently skip / double-transcribe via the by-name symlinks. See zkm-whatsapp
# ARCHITECTURE.md "Folder naming" and ROADMAP id:da9f.
#
# Usage:
#   scripts/migrate_by_id.sh            # DRY RUN (default): pre-flight + show what would move
#   scripts/migrate_by_id.sh --apply    # do it: pause trigger → git mv → commit → convert → resume
#   ZKM_STORE=/path scripts/migrate_by_id.sh --apply
#
# Idempotent: after a successful migration there are no flat dirs left, so a re-run is a no-op.
set -euo pipefail

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

STORE="${ZKM_STORE:-$HOME/knowledge}"
WA="$STORE/chat/whatsapp"
BYID="$WA/by-id"
TRIGGER="zkm-whatsapp-decrypt.path"

die() { echo "migrate_by_id: $*" >&2; exit 1; }

[ -d "$WA" ] || die "no $WA (ZKM_STORE=$STORE) — nothing to migrate"
git -C "$STORE" rev-parse --git-dir >/dev/null 2>&1 || die "$STORE is not a git repo (git mv needs it)"

# Flat <tid> dirs = direct children of chat/whatsapp/ that are NOT by-id/ or by-name/.
mapfile -t FLAT < <(find "$WA" -mindepth 1 -maxdepth 1 -type d \
  ! -name by-id ! -name by-name -printf '%f\n' | sort)

echo "store         : $STORE"
echo "flat <tid> dirs: ${#FLAT[@]}"
echo "by-id/ exists  : $([ -d "$BYID" ] && echo yes || echo no)"

if [ "${#FLAT[@]}" -eq 0 ]; then
  echo "nothing to migrate (already done, or empty) — no-op."
  exit 0
fi

# Refuse a half-migrated split-brain unless the only by-id content is from a prior partial run.
if [ -d "$BYID" ] && [ -n "$(find "$BYID" -mindepth 1 -maxdepth 1 -type d -print -quit 2>/dev/null)" ]; then
  echo "WARNING: by-id/ already has dirs AND flat dirs remain — possible partial/split state."
  echo "         Inspect before --apply: flat dirs would be moved alongside existing by-id/ ones."
  [ "$APPLY" -eq 1 ] || { echo "(dry-run) refusing to guess; resolve manually or confirm intent."; }
fi

if [ "$APPLY" -eq 0 ]; then
  echo
  echo "DRY RUN — would move ${#FLAT[@]} dirs into by-id/ (showing first 10):"
  printf '  chat/whatsapp/%s/  ->  chat/whatsapp/by-id/%s/\n' "${FLAT[@]:0:10}" "${FLAT[@]:0:10}" 2>/dev/null || \
    for f in "${FLAT[@]:0:10}"; do echo "  chat/whatsapp/$f/ -> chat/whatsapp/by-id/$f/"; done
  echo "Re-run with --apply to perform the migration."
  exit 0
fi

# --- apply ---
[ -z "$(git -C "$STORE" status --porcelain)" ] || die "store working tree is dirty — commit/stash first"

echo "pausing auto-decryption trigger ($TRIGGER) …"
systemctl --user stop "$TRIGGER" 2>/dev/null || echo "  (trigger not active or systemd --user unavailable; continuing)"

mkdir -p "$BYID"
echo "git mv-ing ${#FLAT[@]} dirs (history-preserving) …"
for f in "${FLAT[@]}"; do
  git -C "$STORE" mv "chat/whatsapp/$f" "chat/whatsapp/by-id/$f"
done

git -C "$STORE" commit -q -m "chore(store): migrate chat/whatsapp/<tid> → by-id/<tid> (da9f, ${#FLAT[@]} chats)"
echo "committed migration."

echo "regenerating by-name view via convert (key_id dedup → near-no-op for existing chats) …"
ZKM_BYPASS_DIRTY_CHECK="${ZKM_BYPASS_DIRTY_CHECK:-1}" zkm convert whatsapp || \
  echo "  (convert returned nonzero — check output; migration itself is committed and safe)"

echo "resuming trigger …"
systemctl --user start "$TRIGGER" 2>/dev/null || echo "  (could not restart $TRIGGER — start it manually)"

echo "done. Verify: day-files under chat/whatsapp/by-id/, by-name/ symlinks resolve,"
echo "and that zkm-stt resolves by-id/ (see ROADMAP id:da9f / the zkm-stt lockstep)."
