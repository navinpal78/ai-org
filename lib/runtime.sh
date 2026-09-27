#!/usr/bin/env bash
# runtime.sh - the runtime adapter layer.
# Sourced by tools/test-agent.sh and anything else that executes an agent.
# Not executable on its own.
#
# ---------------------------------------------------------------------------
# Why this file exists
# ---------------------------------------------------------------------------
# An agent is a role. A runtime is the program that executes it. The whole
# project is built so those can change independently: if the runtime turns out
# to be bad at something, you replace the runtime and the agent's name, mission,
# SOUL.md, tests and place in the org are all untouched.
#
# That is only true if the choice of runtime is made in exactly one place, in
# data, and everything else asks this file to do the work. So:
#
#   agent.conf          AGENT_RUNTIME="ollama"     <- the choice, per agent
#   config/runtimes.json                           <- which runtimes exist
#   lib/runtime.sh       this file                  <- how to talk to them
#
# Nothing else in the project is allowed to know that Ollama exists.
#
# ---------------------------------------------------------------------------
# The interface
# ---------------------------------------------------------------------------
# Two functions, per runtime. A runtime named <id> must provide:
#
#   _rt_<id>_probe  <model>
#       Check the runtime is reachable and has <model>. Print a reason and
#       return non-zero if not. Must not print anything on success.
#
#   _rt_<id>_chat  <model> <system> <prompt> <maxtok> <temp> <think> <timeout_secs>
#       Execute one turn. Print one JSON object on stdout, or nothing at all if
#       the call failed (the caller turns an empty reply into a readable error).
#       Never print progress or logging - stdout is the payload.
#
# Callers use only these two, never the _rt_ functions directly:
#
#   runtime_ids                          list the runtimes that work
#   runtime_is_known <id>                0 if <id> is in the registry
#   runtime_probe <id> <model>           thin wrapper, readable errors
#   runtime_chat <id> ...same args...    thin wrapper, dispatches by name
#
# The wrappers exist so the error messages are written once, in one style, and
# so a missing adapter produces "no adapter for runtime X" instead of
# "command not found".

# Guard against double-sourcing.
if [ -n "${AIORG_RUNTIME_SOURCED:-}" ]; then
  return 0
fi
AIORG_RUNTIME_SOURCED=1

# This file already depended on $AIORG_ROOT arriving from lib/common.sh without
# saying so, and then started calling aiorg_ollama_url() as well. Stated
# explicitly now: source common.sh. Re-sourcing is harmless - it only sets
# defaults with ${VAR:-...} and redefines functions.
if ! declare -F aiorg_ollama_url >/dev/null 2>&1; then
  # shellcheck source=lib/common.sh
  . "$AIORG_ROOT/lib/common.sh"
fi

AIORG_RUNTIMES_JSON="$AIORG_ROOT/config/runtimes.json"

# Print the ids of every runtime in the registry, one per line.
runtime_ids() {
  [ -f "$AIORG_RUNTIMES_JSON" ] || return 0
  jq -r '.runtimes // {} | keys[]' "$AIORG_RUNTIMES_JSON" 2>/dev/null || true
}

# True if <id> is a runtime this project can actually execute.
runtime_is_known() {
  local id="${1:-}"
  [ -n "$id" ] || return 1
  runtime_ids | grep -qxF -- "$id"
}

# The adapter function name for a runtime, e.g. ollama -> _rt_ollama_chat.
_runtime_fn() {
  local kind="$1" id="$2"
  printf '_rt_%s_%s' "$id" "$kind"
}

# Print a human-readable one-liner about a runtime, for --verbose output.
runtime_describe() {
  local id="${1:-}"
  [ -f "$AIORG_RUNTIMES_JSON" ] || return 0
  jq -r --arg id "$id" '.runtimes[$id].notes // [] | join(" ")' \
    "$AIORG_RUNTIMES_JSON" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# runtime_probe <id> <model>
#
# Deliberately does not exit on failure. The caller decides whether an
# unreachable runtime is fatal (it is, for a test run) or informational.
# ---------------------------------------------------------------------------
runtime_probe() {
  local id="${1:-}" model="${2:-}"
  local fn

  if [ -z "$id" ]; then
    printf 'No AGENT_RUNTIME set in agent.conf.\n'
    return 1
  fi

  if ! runtime_is_known "$id"; then
    printf 'AGENT_RUNTIME="%s" is not a runtime in config/runtimes.json.\n' "$id"
    printf 'Available: %s\n' "$(runtime_ids | tr '\n' ' ')"
    printf 'If you meant to try it, add an adapter in lib/runtime.sh and an entry\n'
    printf 'in config/runtimes.json first - do not name a runtime that is not there.\n'
    return 1
  fi

  fn="$(_runtime_fn probe "$id")"
  if ! declare -F "$fn" >/dev/null 2>&1; then
    printf 'config/runtimes.json lists "%s" but lib/runtime.sh has no %s.\n' "$id" "$fn"
    return 1
  fi

  "$fn" "$model"
}

# ---------------------------------------------------------------------------
# runtime_chat <id> <model> <system> <prompt> <maxtok> <temp> <think> <timeout>
#
#   maxtok   integer, size of one reply
#   temp     decimal string; 0 means greedy, which is what makes tests
#            reproducible
#   think    on | off - off is the default, because a thinking model can
#            spend the whole token budget reasoning and return an empty reply
#   timeout  seconds
#
# The caller passes these in plain human form and the adapter converts them to
# whatever its own API wants. That is the adapter's job, not the caller's,
# because a thinking toggle and a temperature mean different things in
# different engines.
# ---------------------------------------------------------------------------
runtime_chat() {
  local id="${1:-}" model="${2:-}" system="${3:-}" prompt="${4:-}"
  local maxtok="${5:-512}" temp="${6:-0}" think="${7:-off}" timeout="${8:-1800}"
  local fn

  [ -n "$id" ] || return 1
  fn="$(_runtime_fn chat "$id")"
  declare -F "$fn" >/dev/null 2>&1 || return 1
  "$fn" "$model" "$system" "$prompt" "$maxtok" "$temp" "$think" "$timeout"
}

# ===========================================================================
# ADAPTERS
#
# One section per runtime. To add a runtime, copy the ollama section, change
# the two function names and the request body, and add the id to
# config/runtimes.json. Keep the signatures identical - that is the contract.
# ===========================================================================

# ---------------------------------------------------------------------------
# ollama - the default. Talks to a local Ollama model server over HTTP.
# ---------------------------------------------------------------------------

# Ollama puts temperature and num_predict under "options", and has a top-level
# "think" flag for models with a separate reasoning channel. Other engines
# spell all of this differently, which is why this lives here and not in the
# caller.
_rt_ollama_json() {
  local temp="$1" think="$2" maxtok="$3" model="$4" system="$5" prompt="$6"
  local temp_json think_json

  case "$temp" in
    0|0.0)  temp_json=0 ;;
    1|1.0)  temp_json=1 ;;
    *)      temp_json="$temp" ;;
  esac
  case "$think" in
    on|true|1|yes) think_json=true ;;
    *)             think_json=false ;;
  esac

  jq -n \
    --arg model "$model" \
    --arg system "$system" \
    --arg prompt "$prompt" \
    --argjson think "$think_json" \
    --argjson max "$maxtok" \
    --argjson temp "$temp_json" \
    '{model:$model, stream:false, think:$think,
      options:{num_predict:$max, temperature:$temp},
      messages:[{role:"system",content:$system},{role:"user",content:$prompt}]}'
}

_rt_ollama_probe() {
  local model="${1:-}"
  # Computed, not read from the profile. AI_OLLAMA_URL is a literal baked into
  # the generated profile.env, so `export AI_OLLAMA_HOST=<gpu box>` - the exact
  # remedy printed below on failure - changed the host and left this pointing at
  # 127.0.0.1. The agents kept using the local machine in the remote setup that
  # override exists to support.
  local url
  url="$(aiorg_ollama_url)"

  # Ask the API, not the ollama CLI: the CLI only ever talks to localhost, so
  # the CLI gives the wrong answer when AI_OLLAMA_HOST points at another
  # machine's GPU.
  if ! curl -sf --max-time 10 "$url/api/tags" >/dev/null 2>&1; then
    printf 'No model server answering at %s\n' "$url"
    printf '  On this machine:      systemctl status ollama\n'
    printf '  If it is another PC:  export AI_OLLAMA_HOST=192.168.1.50\n'
    return 1
  fi

  if [ -z "$model" ]; then
    return 0
  fi

  if ! curl -sf --max-time 10 "$url/api/tags" 2>/dev/null \
       | jq -e --arg m "$model" 'any(.models[]?; .name == $m)' >/dev/null 2>&1; then
    printf "Model '%s' is not available at %s\n" "$model" "$url"
    printf '  On this machine:      ./bootstrap.sh models\n'
    printf '  If it is another PC:  run that there, or export AI_OLLAMA_HOST=<ip>\n'
    return 1
  fi

  return 0
}

_rt_ollama_chat() {
  local model="$1" system="$2" prompt="$3" maxtok="$4" temp="$5" think="$6" timeout="$7"
  local url
  url="$(aiorg_ollama_url)"

  _rt_ollama_json "$temp" "$think" "$maxtok" "$model" "$system" "$prompt" \
    | curl -s --max-time "$timeout" \
        -H 'Content-Type: application/json' -d @- \
        "$url/api/chat"
}
