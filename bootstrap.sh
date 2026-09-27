#!/usr/bin/env bash
# bootstrap.sh - the single entry point.
#
#   ./bootstrap.sh detect    profile the hardware, resolve models   (always first)
#   ./bootstrap.sh all       detect -> ollama -> models -> web ui
#   ./bootstrap.sh ollama    install and tune the model server
#   ./bootstrap.sh models    download the models that fit
#   ./bootstrap.sh ui        start the browser interface
#   ./bootstrap.sh verify    check the whole thing works
#   ./bootstrap.sh check     validate the agents/ tree (no model needed)
#   ./bootstrap.sh audit     what ran, on which runtime and model, and how it went
#   ./bootstrap.sh status    show what is installed and running
#   ./bootstrap.sh doctor    diagnose problems
#
# Order matters: 'detect' writes the config every other step reads. After a
# hardware upgrade, 'detect' is the only thing you must re-run.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$AIORG_ROOT/lib/common.sh"

usage() { sed -n '2,16p' "$AIORG_ROOT/bootstrap.sh" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

step() {
  # The path is relative to the project root, spelled out in full. A hidden
  # prefix here means tools/ and scripts/ can both be called without it being
  # obvious which directory a script actually lives in.
  #
  # Executed directly, not via 'bash', so each file's shebang decides how it
  # runs. Half these tools are Python; forcing them through bash would work
  # only until the first one had a docstring at the top.
  local name="$1" script="$2"
  shift 2 || true
  echo
  log_step "==========================================================="
  log_step "  $name"
  log_step "==========================================================="
  "$AIORG_ROOT/$script" "$@"
}

cmd_detect()  { step "Detect hardware and resolve models" scripts/00-detect.sh; }
cmd_ollama()  { require_profile; step "Install and configure Ollama" scripts/10-ollama.sh; }
cmd_models()  { require_profile; step "Download models" scripts/20-models.sh; }
cmd_ui()      { require_profile; step "Open WebUI" scripts/30-openwebui.sh; }
cmd_verify()  { require_profile; step "Verify" scripts/40-verify.sh; }

# Deliberately does not require a profile or a running model server: this is a
# pure file check, so it must work on a fresh checkout with nothing installed.
# The two implementations of the risk-tier rules must agree, or the checker and
# the harness describe different permissions and nothing else would notice.
cmd_check() {
  # All three steps run even when one fails, and the exit code is non-zero if
  # any of them did. `set -e` would abort at the first failure, which hides
  # every later problem behind the first one - and it hid something specific:
  # with check-agents.py knowingly red over the auditor's model independence,
  # sync-rules.sh and the 301 assertions in test_retrieval.py were never being
  # executed at all. A build that is red for a known reason still has to report
  # the unknown ones, or "red" quietly becomes "only the thing I already know
  # about".
  #
  # Scoped to `check` on purpose. `all` and `verify` must keep aborting on the
  # first failure: there is no reason to keep installing after a step failed.
  local rc=0
  step "Validate agents" tools/check-agents.py "$@" || rc=1
  step "Cross-check risk-tier rules" tools/sync-rules.sh || rc=1
  # The retrieval tools are the one part of the tree that talks to the network,
  # so "it parses" is not evidence about them. This starts a loopback server,
  # crawls it, and asserts the refusals hold. No internet needed.
  step "Retrieval pipeline" tests/test_retrieval.py || rc=1
  return "$rc"
}

# Same: reading state/audit.log must work on a box that has never run an agent,
# and say so usefully rather than traceback.
cmd_audit()   { step "Audit log" tools/audit-log.sh "$@"; }

cmd_all() {
  cmd_detect
  cmd_ollama
  cmd_models
  cmd_ui
  cmd_verify
}

cmd_status() {
  echo
  log_step "Status"
  echo
  if [ -f "$AIORG_PROFILE" ]; then
    # source_profile, not `. "$AIORG_PROFILE"`: sourcing directly bypasses the
    # AI_OLLAMA_HOST override rule, and status is exactly where you go to find
    # out which machine it is talking to. It reported the local server as
    # running while pointed at a GPU box on the LAN.
    source_profile
    log_dim "detected:   $AI_DETECTED_AT"
    log_dim "cpu:        $AI_CPU_MODEL"
    log_dim "gpu:        $AI_GPU_NAMES (${AI_VRAM_GB} GB, ${AI_USABLE_VRAM_GB} GB usable)"
    log_dim "tier:       $AI_TIER ($AI_TIER_LABEL)"
    log_dim "context:    $AI_CONTEXT tokens"
    log_dim "parallel:   $AI_PARALLEL agent sessions"
  else
    log_warn "no profile yet - run ./bootstrap.sh detect"
  fi
  echo
  if curl -sf --max-time 3 "$(aiorg_ollama_url)/api/version" >/dev/null 2>&1; then
    log_ok "ollama: running"
    if command -v ollama >/dev/null 2>&1; then
      ollama list 2>/dev/null | sed 's/^/       /' || true
    fi
  else
    log_warn "ollama: not responding"
  fi
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    state="$(docker inspect -f '{{.State.Status}}' ai-org-openwebui 2>/dev/null || echo 'absent')"
    log_dim "open-webui: $state"
  fi
  echo
  if [ -d "$AIORG_ROOT/agents" ]; then
    agents="$(find "$AIORG_ROOT/agents" -mindepth 1 -maxdepth 1 -type d \
      ! -name '_template' ! -name '.*' -printf '%f\n' 2>/dev/null | sort)"
    if [ -n "$agents" ]; then
      log_dim "agents:"
      for a in $agents; do
        if [ -f "$AIORG_ROOT/agents/$a/agent.conf" ]; then
          log_dim "  - $a"
        else
          log_warn "  - $a  (incomplete - no agent.conf)"
        fi
      done
    else
      log_dim "agents:  none yet"
    fi
  fi
  echo
}

cmd_doctor() {
  echo
  log_step "Diagnosing"
  echo
  local problems=0

  # `need_ok LABEL COMMAND...` - the label is separate from the command, because
  # the first version passed "$@" and printed $1, which is the command. It
  # reported "[ok] test" for a missing profile.env, which is technically true
  # and completely useless: the operator needs to be told which FILE is
  # missing, not which shell builtin noticed.
  need_ok() {
    local label="$1"; shift
    if "$@" >/dev/null 2>&1; then
      log_ok "$label"
    else
      log_err "$label"
      problems=$((problems + 1))
    fi
  }

  need_ok "profile.env generated" test -f "$AIORG_PROFILE"
  if [ ! -f "$AIORG_PROFILE" ]; then
    log_dim "  run ./bootstrap.sh detect"
    # Non-zero, not 0. A diagnostic that finds a problem and exits 0 is worse
    # than one that crashes: `doctor` is what a beginner runs first, and
    # `./bootstrap.sh doctor && ./bootstrap.sh all` sails straight past a
    # missing profile on the strength of the exit code alone.
    return 1
  fi

  for c in python3 curl; do
    if command -v "$c" >/dev/null 2>&1; then
      log_ok "$c present"
    else
      log_err "$c MISSING - required"
      problems=$((problems + 1))
    fi
  done

  if [ -f "$AIORG_HARDWARE_JSON" ]; then
    log_ok "hardware.json parses"
  else
    log_err "hardware.json missing or corrupt"
    problems=$((problems + 1))
  fi

  if [ -f "$AIORG_CONFIG/models.env" ]; then
    # shellcheck disable=SC1090
    . "$AIORG_CONFIG/models.env"
    log_ok "models.env resolves a default model: ${AI_DEFAULT_MODEL:-none}"
    [ -n "${AI_DEFAULT_MODEL:-}" ] || { log_err "no model fits - add a smaller candidate to config/models.json"; problems=$((problems + 1)); }
  else
    log_warn "models.env not generated yet"
  fi

  # Staleness: did the hardware change since the last detect?
  if [ -f "$AIORG_HARDWARE_JSON" ] && command -v python3 >/dev/null 2>&1; then
    recorded="$(python3 -c "import json;print(json.load(open('$AIORG_HARDWARE_JSON'))['gpu']['total_vram_mb'])" 2>/dev/null || echo "")"
    # `live` is deliberately allowed to be empty, and the pipeline is not
    # allowed to fail the script. Two reasons, and the second one cost an
    # afternoon: `nvidia-smi` does not exist on an AMD or Intel box, and under
    # `set -o pipefail` a missing command is 127 from the whole pipeline. Since
    # this file also runs `set -e`, that killed doctor at line 1 of the
    # hardware check - so on any machine without an NVIDIA GPU the command
    # intended to diagnose problems died before printing its verdict, and
    # exited 127. It looked like the tool was missing, not like the tool was
    # broken. A CPU-only or AMD host could never run its own diagnostic.
    # The `|| true` is the fix; the comment is so nobody "simplifies" it away.
    live="$( { nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null || true; } \
             | awk '{s+=$1} END {print s+0}' )"
    if [ -z "$live" ] || [ "$live" = "0" ]; then
      live=""
    fi
    if [ -n "$recorded" ] && [ -n "$live" ] && [ "$recorded" != "$live" ]; then
      log_warn "hardware changed since last detect (profile says ${recorded} MB, now ${live} MB)"
      log_dim "  run ./bootstrap.sh detect && sudo ./scripts/10-ollama.sh"
    fi
  fi

  if [ "$problems" -eq 0 ]; then
    echo
    log_ok "No problems found with the configuration."
  else
    echo
    log_err "$problems problem(s) above."
  fi
  echo
  # Exit non-zero when it found problems. It counted them, printed them, and
  # then returned 0, so the one command whose entire job is reporting whether
  # the machine is healthy could not be used to FIND OUT. `doctor` returning 1
  # is the behaviour every other diagnostic has, and anything chaining on it
  # (`doctor && all`) depends on it.
  return "$problems"
}

# Dispatch on the subcommand, then shift it off so handlers receive only their
# own arguments. Without the shift, './bootstrap.sh check storage-engineer'
# hands 'check' to the checker as an agent name and it fails confusingly.
CMD="${1:-help}"
[ $# -gt 0 ] && shift

case "$CMD" in
  detect)  cmd_detect ;;
  ollama)  cmd_ollama ;;
  models)  cmd_models ;;
  ui)      cmd_ui ;;
  verify)  cmd_verify ;;
  check)   cmd_check "$@" ;;
  audit)   cmd_audit "$@" ;;
  all)     cmd_all ;;
  status)  cmd_status ;;
  doctor)  cmd_doctor ;;
  help|-h|--help) usage 0 ;;
  *)       log_err "Unknown command: $CMD"; echo; usage 1 ;;
esac
