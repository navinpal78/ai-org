#!/usr/bin/env bash
# 10-ollama.sh - install and tune Ollama for the detected hardware.
#
# The tuning is the point of this script. Ollama's defaults are conservative,
# and the defaults that matter (context length, parallel sessions, how long a
# model stays in VRAM) are all things we want to set from the detected tier
# rather than by hand. Upgrade the GPU, re-run detect and this, and the
# service reconfigures itself.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"
require_profile

SERVICE_NAME="ollama"
SERVICE_FILE="/etc/systemd/system/ollama.service"
# Reachable from your other PCs on the LAN. The port comes from the profile:
# hardcoding 11434 here meant that overriding AI_OLLAMA_PORT produced a service
# listening on one port while every other script probed another.
BIND_ADDR="0.0.0.0:${AI_OLLAMA_PORT}"
LOCAL_TARGET="127.0.0.1:${AI_OLLAMA_PORT}"

# Stop before installing anything if the model server is on another machine.
#
# This whole script is about the LOCAL machine: it installs a package, writes
# /etc/systemd/system/ollama.service, and puts the ollama user in the GPU groups.
# None of that helps when AI_OLLAMA_HOST points somewhere else - and running it
# anyway left the user with a local Ollama that nothing used, a systemd service
# they did not ask for, and a verify run reporting on the wrong machine.
#
# The remote flow is: set AI_OLLAMA_HOST on THIS machine, and run this script on
# the box that has the GPU. Everything else (models, verify, the agents) then
# works against that host.
if ! aiorg_ollama_is_local; then
  log_step "Model server is remote - nothing to install here"
  log_ok "AI_OLLAMA_HOST is ${AI_OLLAMA_HOST}, not this machine."
  log_dim "Ollama runs there, so there is nothing for this script to do."
  log_dim ""
  log_dim "  On ${AI_OLLAMA_HOST}, run:  ./bootstrap.sh detect && sudo ./scripts/10-ollama.sh"
  log_dim "  On this machine, just:      ./bootstrap.sh models && ./bootstrap.sh verify"
  exit 0
fi

log_step "Installing Ollama"
if command -v ollama >/dev/null 2>&1; then
  log_ok "Already installed: $(ollama --version 2>/dev/null | head -1)"
else
  need_cmd curl
  log_dim "Downloading the official installer. It needs sudo and installs a"
  log_dim "systemd service that will auto-start Ollama on boot."
  log_dim ""
  curl -fsSL https://ollama.com/install.sh | sh
  log_ok "Installed."
fi

# ---------------------------------------------------------------------------
# Confirm the GPU is actually visible to Ollama.
#
# This is the single most common failure on a fresh install: the daemon is
# running but falls back to CPU, and everything feels broken and slow. Better
# to catch it here than after an hour of confusion.
# ---------------------------------------------------------------------------
log_step "Checking that Ollama can see the GPU"

# Ask Ollama itself, not nvidia-smi, because Ollama may be running as a
# different user than your shell and could lack device access.
check_nvidia_offload() {
  # Only answerable when Ollama is on THIS machine. The previous version probed
  # AI_OLLAMA_HOST for liveness and then ran `ollama ps` against a forced
  # 127.0.0.1, so the documented remote-GPU setup raised a false "did not
  # report GPU offload" alarm - and if the far box was down it stopped the local
  # service and ran `pkill -f "ollama serve"`, a pattern that also matches the
  # systemd unit's own ExecStart and any server the user started by hand.
  if ! aiorg_ollama_is_local; then
    log_dim "Ollama is configured at ${AI_OLLAMA_HOST}, which is not this machine."
    log_dim "GPU visibility has to be checked there, not here:"
    log_dim "  ssh ${AI_OLLAMA_HOST} 'ollama ps'"
    log_dim "  ssh ${AI_OLLAMA_HOST} \"journalctl -u ollama --since '5 min ago' | grep -iE 'cuda|nvidia|gpu'\""
    return 0
  fi

  local ollama_stopped=0 started_pid="" probe=""

  if ! curl -sf "http://${LOCAL_TARGET}/api/version" >/dev/null 2>&1; then
    ollama_stopped=1
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    OLLAMA_HOST="$LOCAL_TARGET" ollama serve >/dev/null 2>&1 &
    started_pid=$!
    # Poll the port instead of sleeping a fixed four seconds, so a slow start
    # is not indistinguishable from a failed one.
    for _ in $(seq 1 20); do
      curl -sf "http://${LOCAL_TARGET}/api/version" >/dev/null 2>&1 && break
      kill -0 "$started_pid" 2>/dev/null || break
      sleep 1
    done
  fi

  probe="$(OLLAMA_HOST="$LOCAL_TARGET" ollama ps 2>/dev/null || true)"

  if [ "$ollama_stopped" = "1" ]; then
    # Kill exactly the process this script started, by PID.
    if [ -n "$started_pid" ]; then
      kill "$started_pid" 2>/dev/null || true
      wait "$started_pid" 2>/dev/null || true
    fi
    systemctl start "$SERVICE_NAME" 2>/dev/null || true
  fi

  if printf '%s' "$probe" | grep -qi "100% GPU"; then
    log_ok "GPU is visible to Ollama."
    return 0
  fi

  log_warn "Ollama did not report GPU offload."
  log_dim "A model is not loaded yet, so this may be a false alarm."
  log_dim "If speeds are bad after models are pulled, run:"
  log_dim "  journalctl -u ollama --since '5 min ago' | grep -i -E 'cuda|nvidia|gpu'"
  log_dim ""
  log_dim "Common cause: the ollama user cannot see the GPU. This script adds"
  log_dim "that below when run as root - check it with:  id -nG ollama"
}

if [ "$AI_GPU_COUNT" -eq 0 ]; then
  log_warn "No GPU detected on this machine - Ollama will run on CPU."
  log_dim "Turns will take tens of seconds instead of milliseconds."
  log_dim "This is fine for testing. Point AI_OLLAMA_HOST at your GPU box"
  log_dim "later to use a real model."
elif [ "$AI_GPU_VENDOR" = "nvidia" ]; then
  check_nvidia_offload
else
  log_dim "GPU vendor is '$AI_GPU_VENDOR'. Ollama's ROCm support needs recent"
  log_dim "drivers; if runs are slow, check the log as described above."
fi

# ---------------------------------------------------------------------------
# Configure the service from the detected tier.
# ---------------------------------------------------------------------------
log_step "Configuring the service for tier '$AI_TIER'"

if [ "$EUID" -ne 0 ]; then
  log_warn "Not running as root - skipping service configuration."
  log_dim "Ollama is installed but will use default settings."
  log_dim "Re-run with:  sudo ./scripts/10-ollama.sh"
  exit 0
fi

# ---------------------------------------------------------------------------
# Let the ollama user see the GPU.
#
# This script's own header calls the silent CPU fallback the most common failure
# on a fresh install, then used to print the fix and move on. We are root here,
# so apply it. A user that cannot open /dev/nvidia* gets no error at all - the
# daemon starts happily and serves a 50x slower model - which is exactly the
# failure worth removing rather than documenting.
# ---------------------------------------------------------------------------
if id ollama >/dev/null 2>&1; then
  added=""
  for grp in video render; do
    getent group "$grp" >/dev/null 2>&1 || continue
    if id -nG ollama 2>/dev/null | tr ' ' '\n' | grep -qx "$grp"; then
      continue
    fi
    if usermod -aG "$grp" ollama 2>/dev/null; then
      added="$added $grp"
    else
      log_warn "Could not add ollama to the '$grp' group."
    fi
  done
  if [ -n "$added" ]; then
    log_ok "Added ollama to the$added group(s) so it can reach the GPU."
  else
    log_dim "ollama can already see the GPU (id -nG ollama)."
  fi
else
  log_warn "No 'ollama' user found - skipping the GPU group check."
  log_dim "The official installer creates one. If you installed Ollama another"
  log_dim "way, add the service user to video,render by hand."
fi

# OLLAMA_NUM_PARALLEL  - how many requests can run at once. This is what lets
#                        several agents work simultaneously. Too high and every
#                        session gets a slice of KV cache, so agents start
#                        failing on long context.
# OLLAMA_MAX_LOADED_MODELS - how many different models stay resident in VRAM.
#                        One is fine; two helps if you swap roles a lot, at the
#                        cost of memory pressure.
# OLLAMA_KEEP_ALIVE    - how long a model stays warm after the last request.
#                        Long = fast follow-ups, but holds VRAM. Short = other
#                        apps get the GPU, but every new task reloads.
#
# The tradeoff: with one GPU and a fixed set of roles, keep models warm and
# accept that nothing else can use the card. This is why the creative pipeline
# (ComfyUI) should be scheduled rather than run alongside the agents.
case "$AI_TIER" in
  cpu)     KEEP_ALIVE="5m";  N_PAR="1"; N_MODELS="1" ;;
  vram_8)  KEEP_ALIVE="10m"; N_PAR="1"; N_MODELS="1" ;;
  vram_12) KEEP_ALIVE="15m"; N_PAR="1"; N_MODELS="1" ;;
  vram_16) KEEP_ALIVE="20m"; N_PAR="1"; N_MODELS="1" ;;
  vram_24) KEEP_ALIVE="30m"; N_PAR="2"; N_MODELS="1" ;;
  vram_32) KEEP_ALIVE="30m"; N_PAR="2"; N_MODELS="1" ;;
  vram_48) KEEP_ALIVE="45m"; N_PAR="3"; N_MODELS="2" ;;
  *)       KEEP_ALIVE="60m"; N_PAR="4"; N_MODELS="2" ;;
esac

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3

# Generated by ai-org/scripts/10-ollama.sh on $(date -Iseconds)
# Hardware tier: $AI_TIER ($AI_TIER_LABEL)
# GPU: $AI_GPU_NAMES, ${AI_VRAM_GB} GB
# Re-run './bootstrap.sh detect && sudo ./scripts/10-ollama.sh' after any
# hardware change - this file is regenerated, so do not hand-edit it.

Environment="OLLAMA_HOST=$BIND_ADDR"
Environment="OLLAMA_CONTEXT_LENGTH=$AI_CONTEXT"
Environment="OLLAMA_NUM_PARALLEL=$N_PAR"
Environment="OLLAMA_MAX_LOADED_MODELS=$N_MODELS"
Environment="OLLAMA_KEEP_ALIVE=$KEEP_ALIVE"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"

log_ok "Service configured:"
log_dim "  context length   ${AI_CONTEXT} tokens"
log_dim "  parallel agents  ${N_PAR}"
log_dim "  models in VRAM   ${N_MODELS}"
log_dim "  keep-alive       ${KEEP_ALIVE}"
log_dim "  listening on     ${BIND_ADDR}"

sleep 3
if curl -sf "$(aiorg_ollama_url)/api/version" >/dev/null 2>&1; then
  log_ok "Ollama is responding on port ${AI_OLLAMA_PORT}."
else
  log_warn "Ollama is not responding yet. Check:  systemctl status ollama"
fi
