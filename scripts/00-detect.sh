#!/usr/bin/env bash
# 00-detect.sh - profile the hardware, then resolve which models fit.
#
# This script is safe to run at any time and on any machine. Re-run it after
# changing hardware. Everything downstream reads what it writes, so this is
# the only script you ever need to re-run when you upgrade.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"

log_step "Profiling this machine"

need_cmd python3
need_cmd date

# Timestamp the hardware file so the resolver report is honest about when the
# reading was taken.
python3 "$AIORG_ROOT/lib/hwdetect.py"

log_step "Resolving models for the detected hardware"
python3 "$AIORG_ROOT/tools/resolve_models.py"

# Record what happened, so a later run can tell you the profile changed.
# Source the profile first: the tier is needed on both branches below.
# shellcheck disable=SC1091
. "$AIORG_PROFILE"

mkdir -p "$AIORG_STATE"
if [ -f "$AIORG_STATE/previous-tier" ]; then
  prev="$(cat "$AIORG_STATE/previous-tier")"
  if [ "$prev" != "$AI_TIER" ]; then
    log_warn "Hardware tier changed: $prev -> $AI_TIER"
    log_dim "Models and context length have been re-resolved automatically."
    log_dim "Re-run './bootstrap.sh models' to download anything newly needed."
    log_dim ""
    printf 'detected: %s\n  tier: %s -> %s (change)\n' \
      "$(date -Iseconds)" "$prev" "$AI_TIER" >> "$AIORG_STATE/detect-history.log"
  else
    printf 'detected: %s\n  tier: %s (unchanged)\n' \
      "$(date -Iseconds)" "$AI_TIER" >> "$AIORG_STATE/detect-history.log"
  fi
else
  printf 'detected: %s\n  tier: %s (first run)\n' \
    "$(date -Iseconds)" "$AI_TIER" >> "$AIORG_STATE/detect-history.log"
fi
printf '%s' "$AI_TIER" > "$AIORG_STATE/previous-tier"

log_ok "Done."
