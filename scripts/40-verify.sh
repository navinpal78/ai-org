#!/usr/bin/env bash
# 40-verify.sh - prove the whole thing actually works, and prove it on the GPU.
#
# "Ollama is installed" is not verification. The failure that costs people the
# most time is a silent CPU fallback: everything appears to work, it is just
# 50x slower, and you spend an evening blaming your prompt. So this script
# runs a real generation and reports the speed and the offload percentage.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"
require_profile

# models.env defines AI_DEFAULT_MODEL and the per-role model names, and this
# script used AI_DEFAULT_MODEL without ever loading it - so under `set -u` it
# died at step 4 with "AI_DEFAULT_MODEL: unbound variable" on every machine.
# That means verify has never actually run to completion.
MODELS_ENV="$AIORG_CONFIG/models.env"
if [ -f "$MODELS_ENV" ]; then
  # shellcheck disable=SC1090
  . "$MODELS_ENV"
else
  log_warn "config/models.env is missing - the live test will be skipped."
  log_dim "Run:  ./bootstrap.sh detect"
fi

PASS=0
FAIL=0
WARN=0

# One convention for "which server", from lib/common.sh. Every `ollama list` and
# `ollama ps` below goes through this. Called bare, the CLI always means
# localhost, so with the GPU on another machine verify inspected the wrong box
# and reported every model as missing.
OLLAMA_TARGET="$(aiorg_ollama_target)"
OLLAMA_URL="$(aiorg_ollama_url)"

check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    log_ok "$label"
    PASS=$((PASS + 1))
  else
    log_err "$label"
    FAIL=$((FAIL + 1))
  fi
}

soft_check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    log_ok "$label"
    PASS=$((PASS + 1))
  else
    log_warn "$label"
    WARN=$((WARN + 1))
  fi
}

echo
log_step "1/6  Configuration"
check "config/profile.env exists" test -f "$AIORG_PROFILE"
check "config/hardware.json exists" test -f "$AIORG_HARDWARE_JSON"
check "config/models.env exists" test -f "$AIORG_CONFIG/models.env"
log_dim "  tier: $AI_TIER ($AI_TIER_LABEL), context $AI_CONTEXT, parallel $AI_PARALLEL"

echo
log_step "2/6  Ollama service"
if curl -sf "$OLLAMA_URL/api/version" >/dev/null 2>&1; then
  version="$(curl -s "$OLLAMA_URL/api/version" | jq -r '.version // "unknown"')"
  log_ok "responding on port $AI_OLLAMA_PORT (version $version)"
  PASS=$((PASS + 1))
else
  log_err "not responding on port $AI_OLLAMA_PORT"
  log_dim "  sudo systemctl status ollama"
  FAIL=$((FAIL + 1))
fi

echo
log_step "3/6  Models on disk"
if [ -f "$AIORG_STATE/models-installed.txt" ]; then
  while IFS='=' read -r role model; do
    case "$role" in ''|'#'*|tier|usable_vram_gb) continue ;; esac
    if OLLAMA_HOST="$OLLAMA_TARGET" ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$model"; then
      log_ok "$role -> $model"
      PASS=$((PASS + 1))
    else
      log_err "$role -> $model  (not downloaded)"
      log_dim "  ./bootstrap.sh models"
      FAIL=$((FAIL + 1))
    fi
  done < "$AIORG_STATE/models-installed.txt"
else
  log_warn "no record of installed models yet - run ./bootstrap.sh models"
  WARN=$((WARN + 1))
fi

echo
log_step "4/6  Live generation and GPU offload"
TEST_MODEL="${AI_TEST_MODEL:-${AI_DEFAULT_MODEL:-}}"

if [ -z "$TEST_MODEL" ]; then
  log_warn "no default model resolved. Skipping the live test."
  WARN=$((WARN + 1))
elif ! OLLAMA_HOST="$OLLAMA_TARGET" ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$TEST_MODEL"; then
  log_warn "$TEST_MODEL not downloaded. Skipping the live test."
  WARN=$((WARN + 1))
else
  log_dim "  asking $TEST_MODEL to count to three (first call loads the model)..."
  start_ts="$(date +%s)"
  # think:false is not optional here. qwen3 and deepseek-r1 reason in the reply
  # budget, and a 16-token cap on a thinking model is spent before any answer
  # token exists: the API returns done_reason "length" with response:"" and
  # verify reports a bare "empty response". That is not a flaky model, it is this
  # call asking a thinking model to answer without leaving room to think. Both
  # the budget and the flag are fixed together - raising num_predict alone just
  # makes it slower before failing the same way.
  if response="$(curl -s --max-time 600 "$OLLAMA_URL/api/generate" \
        -d "{\"model\":\"$TEST_MODEL\",\"prompt\":\"Reply with exactly: 1 2 3\",\"stream\":false,\"think\":false,\"options\":{\"num_predict\":64}}")"; then

    elapsed=$(( $(date +%s) - start_ts ))
    log_ok "responded in ${elapsed}s (includes model load)"

    # Confirm it produced something sane rather than an error blob.
    got="$(printf '%s' "$response" | jq -r '.response // ""' | tr -d '\n' | head -c 40)"
    if [ -n "$got" ]; then
      log_ok "output: \"$got\""
      PASS=$((PASS + 1))
    else
      log_err "empty response"
      # Say WHY it was empty. "empty response" sent me looking at the model; the
      # actual cause was in the JSON the whole time.
      done_reason="$(printf '%s' "$response" | jq -r '.done_reason // "unknown"')"
      if [ "$done_reason" = "length" ]; then
        log_dim "  The model hit the token limit before answering (done_reason:"
        log_dim "  \"length\"). On a thinking model that means it spent the whole"
        log_dim "  budget reasoning. This is a budget problem, not a broken model."
      else
        log_dim "  done_reason: $done_reason"
      fi
      log_dim "  raw: $(printf '%s' "$response" | head -c 200)"
      FAIL=$((FAIL + 1))
    fi

    # The real check: is the model on the GPU?
    ps_out="$(OLLAMA_HOST="$OLLAMA_TARGET" ollama ps 2>/dev/null || true)"
    if printf '%s' "$ps_out" | grep -qi "100% GPU"; then
      log_ok "running at 100% GPU"
      PASS=$((PASS + 1))
    elif printf '%s' "$ps_out" | grep -qiE "[0-9]+% GPU"; then
      pct="$(printf '%s' "$ps_out" | grep -oiE "[0-9]+% GPU" | head -1)"
      log_warn "partial GPU offload ($pct) - some layers are on CPU"
      log_dim "  Normal when the model nearly fills VRAM: the leftovers spill"
      log_dim "  to RAM, which is much slower but works. To improve it, either"
      log_dim "  lower AI_CONTEXT_OVERRIDE or pick a smaller model in"
      log_dim "  config/models.json."
      WARN=$((WARN + 1))
    else
      log_err "no GPU offload detected - Ollama is running on CPU"
      log_dim "  This will be extremely slow. To fix:"
      log_dim "    journalctl -u ollama --since '5 min ago' | grep -iE 'cuda|nvidia|gpu'"
      log_dim "  Common causes:"
      log_dim "    - the 'ollama' user cannot see the GPU:"
      log_dim "        sudo usermod -aG video,render ollama && sudo systemctl restart ollama"
      log_dim "    - driver mismatch, or the card is too new for the installed driver"
      log_dim "    - on AMD: ROCm is not installed"
      FAIL=$((FAIL + 1))
    fi
  else
    log_err "generation request failed or timed out (600s)"
    FAIL=$((FAIL + 1))
  fi
fi

echo
log_step "5/6  Open WebUI"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  status="$(docker inspect -f '{{.State.Health.Status}}' ai-org-openwebui 2>/dev/null || echo "absent")"
  case "$status" in
    healthy) log_ok "container healthy"; PASS=$((PASS + 1)) ;;
    # Optional, so this is a warning and not a pass. It used to call
    # soft_check with `true`, which incremented PASS, then decremented WARN
    # (never incremented) and re-incremented it - so a missing container was
    # counted as a success and verify reported a clean run without a UI.
    absent)  log_warn "container not running (optional - agents do not need it)"
             WARN=$((WARN + 1)) ;;
    *)       log_err "container state: $status"
             log_dim "  docker logs --tail 50 ai-org-openwebui"
             FAIL=$((FAIL + 1)) ;;
  esac
else
  log_warn "Docker not available - skipping (Open WebUI is optional)"
  WARN=$((WARN + 1))
fi

echo
log_step "6/6  Reachability from other PCs"
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo '')"
if [ -n "$LAN_IP" ]; then
  if curl -sf --max-time 5 "http://${LAN_IP}:${AI_OLLAMA_PORT}/api/version" >/dev/null 2>&1; then
    log_ok "Ollama reachable at http://${LAN_IP}:${AI_OLLAMA_PORT}"
    PASS=$((PASS + 1))
  else
    log_warn "Ollama is not reachable at http://${LAN_IP}:${AI_OLLAMA_PORT}"
    log_dim "  It is bound to 0.0.0.0, so this is usually a firewall:"
    log_dim "    sudo ufw allow ${AI_OLLAMA_PORT}/tcp"
    log_dim "  To lock it down to your LAN only, see docs/00-START-HERE.md."
    WARN=$((WARN + 1))
  fi
else
  log_warn "could not determine this machine's LAN address"
  WARN=$((WARN + 1))
fi

echo
log_step "Result"
echo
log_dim "  passed:  $PASS"
[ "$WARN" -gt 0 ] && log_dim "  warnings: $WARN"
if [ "$FAIL" -gt 0 ]; then
  log_dim "  failed:  $FAIL"
else
  log_dim "  failed:  0"
fi
echo

if [ "$FAIL" -eq 0 ]; then
  log_ok "Foundation is working."
  echo
  log_dim "Next:  ./tools/new-agent.sh coder      # build your first agent"
  log_dim "       ./docs/00-START-HERE.md          # read this before continuing"
  echo
  exit 0
else
  log_err "$FAIL check(s) failed. Fix the above, then re-run:  ./bootstrap.sh verify"
  echo
  exit 1
fi
