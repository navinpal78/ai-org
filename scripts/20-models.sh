#!/usr/bin/env bash
# 20-models.sh - download the models that fit this machine.
#
# Reads config/models.env (written by the resolver) and pulls one model per
# role. If a pull fails - usually because the tag in config/models.json does
# not exist upstream - it reports and continues rather than aborting the whole
# setup, so you end up with a working system and a short list of things to fix.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"
require_profile

MODELS_ENV="$AIORG_CONFIG/models.env"
[ -f "$MODELS_ENV" ] || die "No resolved models. Run:  ./bootstrap.sh detect"
# shellcheck disable=SC1090
. "$MODELS_ENV"

# One convention for "which server", from lib/common.sh. The "already
# downloaded?" check below used to call a bare `ollama list`, which always means
# localhost - so with the GPU on another machine it asked the wrong box, decided
# every model was absent, and re-downloaded gigabytes on every run.
OLLAMA_TARGET="$(aiorg_ollama_target)"

log_step "Downloading models (this takes a while and a lot of disk)"

# Roles to skip by default. Vision and embedding models are small, but the
# creative pipeline is not needed until step 8 of the build order.
SKIP_ROLES="${AI_SKIP_ROLES:-}"

pulled=0
present=0
skipped=0
failed=0
failed_list=()

for role in $AI_ROLES; do
  model_var="$(aiorg_role_var "$role")_MODEL"
  model="${!model_var:-}"

  if [ -z "$model" ]; then
    log_warn "role '$role': no model fits this machine. Skipping."
    log_dim "  Add a smaller candidate in config/models.json, or see"
    log_dim "  docs/00-START-HERE.md for running this role elsewhere."
    skipped=$((skipped + 1))
    continue
  fi

  if printf '%s' " $SKIP_ROLES " | grep -q " $role "; then
    log_info "role '$role': skipped by AI_SKIP_ROLES. ($model)"
    skipped=$((skipped + 1))
    continue
  fi

  # Already downloaded?
  if OLLAMA_HOST="$OLLAMA_TARGET" ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$model"; then
    log_ok "role '$role': $model already present"
    present=$((present + 1))
    continue
  fi

  margin_var="${key}_MARGIN"
  notes_var="${key}_NOTES"
  log_info "role '$role': pulling $model  (${!margin_var:-?}, ${!notes_var:-})"
  if OLLAMA_HOST="$OLLAMA_TARGET" ollama pull "$model" 2>&1 | sed 's/^/       /'; then
    pulled=$((pulled + 1))
  else
    log_err "role '$role': failed to pull '$model'"
    log_dim "  The tag may not exist upstream. Check with:  ollama run $model"
    log_dim "  or browse https://ollama.com/library to find the current name,"
    log_dim "  then edit config/models.json and re-run this script."
    failed=$((failed + 1))
    failed_list+=("$role=$model")
  fi
done

echo
log_step "Download summary"
log_dim "  newly pulled:  $pulled"
log_dim "  already had:   $present"
log_dim "  skipped:       $skipped"
if [ "$failed" -gt 0 ]; then
  log_warn "  failed:        $failed"
  for entry in "${failed_list[@]}"; do
    log_dim "                $entry"
  done
  log_dim ""
  log_dim "This is not fatal. Everything else is installed."
  log_dim "Fix the tags in config/models.json and re-run this script."
fi
echo

# Record what is actually on disk, for the verify step and for agents to read.
{
  echo "# written by 20-models.sh on $(date -Iseconds)"
  echo "tier=$AI_TIER"
  echo "usable_vram_gb=$AI_USABLE_GB"
  for role in $AI_ROLES; do
    model_var="$(aiorg_role_var "$role")_MODEL"
    [ -n "${!model_var:-}" ] && echo "$role=${!model_var}"
  done
} > "$AIORG_STATE/models-installed.txt"

log_ok "Recorded installed models in state/models-installed.txt"
