#!/usr/bin/env bash
# common.sh - shared helpers for the ai-org scaffold.
# Sourced by every script. Not executable on its own.

# Guard against double-sourcing.
if [ -n "${AIORG_COMMON_SOURCED:-}" ]; then
  return 0
fi
AIORG_COMMON_SOURCED=1

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
AIORG_ROOT="${AIORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export AIORG_ROOT
AIORG_CONFIG="$AIORG_ROOT/config"
AIORG_STATE="$AIORG_ROOT/state"
AIORG_PROFILE="$AIORG_CONFIG/profile.env"
AIORG_HARDWARE_JSON="$AIORG_CONFIG/hardware.json"
AIORG_MODELS_JSON="$AIORG_CONFIG/models.json"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_RED=$'\033[31m'
  C_GRN=$'\033[32m'; C_YEL=$'\033[33m'; C_BLU=$'\033[34m'; C_CYN=$'\033[36m'
else
  C_RESET=""; C_DIM=""; C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_CYN=""
fi

_ts() { date +"%H:%M:%S"; }

log_step() { printf '%s[==>%s] %s%s\n' "$C_CYN$C_BLU" "$C_RESET" "$*"; }
log_info() { printf '%s[ %s]%s %s\n' "$C_DIM" "$(_ts)" "$C_RESET" "$*"; }
log_ok()   { printf '%s[ ok ]%s %s\n' "$C_GRN" "$C_RESET" "$*"; }
log_warn() { printf '%s[warn]%s %s\n' "$C_YEL" "$C_RESET" "$*" >&2; }
log_err()  { printf '%s[fail]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
log_dim()  { printf '%s       %s%s\n' "$C_DIM" "$*" "$C_RESET"; }

die() { log_err "$*"; exit 1; }

# Run a command, and if it fails, stop with a readable message.
run() {
  local desc="$1"; shift
  if "$@"; then
    return 0
  else
    die "Failed: $desc"
  fi
}

# Ask a yes/no question. Non-interactive defaults to $2.
confirm() {
  local prompt="$1" default="${2:-y}" reply
  if [ ! -t 0 ]; then
    [ "$default" = "y" ] && return 0 || return 1
  fi
  case "$default" in
    y) hint="[Y/n]" ;;
    n) hint="[y/N]" ;;
    *) hint="[y/n]" ;;
  esac
  read -r -p "${prompt} ${hint} " reply
  [ -z "$reply" ] && reply="$default"
  case "$reply" in
    [Yy]*) return 0 ;;
    *) return 1 ;;
  esac
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1
  Install it and re-run this script. See docs/00-START-HERE.md for help."
}

# ---------------------------------------------------------------------------
# An option that needs a value, and does not get one
# ---------------------------------------------------------------------------
#
#   aiorg_need_value <flag> <remaining-arg-count> <usage>
#
#     Dies unless at least one argument remains after <flag>. Returns 0
#     otherwise, so the caller does `aiorg_need_value "$1" $# "$USAGE" || exit 1`
#     and then `shift 2` as normal.
#
# WHY THIS IS A FUNCTION
#
# Every option-with-a-value in this project was parsed the same way, in
# fourteen places across four tools:
#
#     --only) ONLY="${2:-}"; shift 2 ;;
#
# which is correct until <flag> is the last argument on the command line. Then
# there is one argument left, `shift 2` fails, and under `set -e` - which all
# five of these scripts use - the script dies at the shift. Not at the check
# that would have explained it, and not after a message: just exits 1 with
# nothing on stdout or stderr.
#
# The failure mode is the problem, not the crash. A typo'd flag is the most
# ordinary thing a person does to a command, and this project's standing theme
# is that the diagnostic is what breaks, on exactly the machines most likely to
# need it. Here the caller cannot tell a missing value from a bad agent name, a
# missing model, or a failed check - they are all exit 1 - and the two words
# that would have saved the run are never printed. Found by typing
# `--only` without a value and getting nothing back.
#
# Note also that `${2:-}` silently yields the empty string, so even without the
# crash the value would have been "" rather than an error: `--only ""` and
# `--only` looked identical to the loop. Dying on a missing value is the only
# behaviour that tells the truth about what was typed.
#
# bootstrap.sh line 35 already carried `shift 2 || true` for this, which is the
# tell that somebody hit it and patched the one site they were looking at.
# A guard on a single call site is not a rule; the discipline has to be
# mechanical, or the next tool repeats it.
aiorg_need_value() {
  [ "${2:-0}" -ge 2 ] && return 0
  printf '%s\n' "[fail] $1 needs a value." >&2
  printf '%s\n' "       Nothing followed it, so there is no way to tell what you meant." >&2
  printf '%s\n' "       Usage: $3" >&2
  exit 2
}

# ---------------------------------------------------------------------------
# Naming a model role's resolved variables
# ---------------------------------------------------------------------------

# The env var PREFIX for a model role: `reasoning` -> `REASONING`,
# `adversarial-review` -> `ADVERSARIAL_REVIEW`.
#
# WHY THIS IS A FUNCTION
#
# Four places used to do this conversion by hand - tools/resolve_models.py
# (which writes the names), tools/test-agent.sh, tools/run-agent.sh and
# scripts/20-models.sh (twice) which read them back. All of them uppercased.
# None of them stripped hyphens, because no role name had one, so it never
# mattered and nothing tested it.
#
# Then `adversarial-review` arrived, and every one of the four was wrong in the
# same way. A hyphen is not legal in a shell identifier, so the generated
# models.env grew lines like
#
#     ADVERSARIAL-REVIEW_MODEL="qwen3:14b"
#
# which bash does not parse as an assignment at all - it tries to run a command
# called `ADVERSARIAL-REVIEW_MODEL=qwen3:14b`, prints "command not found", and
# carries on. The variable is never set, the harness reads an empty model, and
# the failure surfaces as "no model resolved for role" - pointing at the
# hardware, when the hardware is fine.
#
# The mistake was never the missing `tr`. It was having four copies of a rule
# and no test that any two of them agreed. tools/resolve_models.py cannot call
# this function (python must not depend on bash), so it carries its own copy;
# tests/test_retrieval.py asserts the two agree over hyphenated names, which is
# the same bargain already struck for the risk-tier rules in
# tools/sync-rules.sh. One rule, two implementations, one mechanical check.
aiorg_role_var() {
  printf '%s' "${1:-}" | tr '[:lower:]-' '[:upper:]_'
}

# ---------------------------------------------------------------------------
# Can this agent think on this card?
# ---------------------------------------------------------------------------
#
#   aiorg_effective_think <role> <want>
#       'on' only if the agent asked for it AND the model the resolver picked
#       for that role can think. 'off' otherwise. Prints 'off' and a reason to
#       stderr when it downgrades something the agent asked for.
#
# This exists because AGENT_THINK is a static setting and the model is not.
# An agent that wants deliberation declares "on" once, and whether that is even
# possible depends on which candidate won - and the candidate changes with the
# card. Ollama 0.33.3 treats a `think:true` request sent to a model with no
# reasoning channel as a hard error rather than ignoring it:
#
#     think=true  -> ERROR: "qwen2.5:0.5b" does not support thinking
#     think=false -> ok
#
# and lib/runtime.sh sends the flag unconditionally, so there is nothing in the
# request that could adapt. Eight of the fifteen agents declared
# AGENT_THINK="on" while their role resolved to an instruct model on a small
# card - llama3.1:8b at 8GB, gemma3:12b at 12GB, phi4:14b at 14GB - so every run
# of those agents would have failed there. Setting them to "off" instead is not
# a fix: it would also switch thinking OFF on a 24GB card, where reasoning
# resolves to gpt-oss:20b and does think, and that is the design target.
#
# The downgrade is deliberately one-directional. An unconfirmed capability
# (the catalog's `thinks` is absent) is treated as "cannot think", because the
# two errors are not symmetric:
#
#     think=off on a thinking model   -> loses deliberation, run still works
#     think=on  on a non-thinking one -> Ollama refuses, the run does not happen
#
# The second is a total failure and the first is a downgrade, so the ambiguity
# resolves towards the one that still produces a result. The cost is that an
# unverified model silently forgoes thinking, which is why the resolver's
# output and tools/check-agents.py both name the ones that are unverified
# rather than leaving it to be discovered.
aiorg_effective_think() {
  local role="${1:-}" want="${2:-off}" var value
  case "$want" in
    on|ON|true|TRUE|1|yes|YES) want="on" ;;
    *) want="off" ;;
  esac
  [ "$want" = "on" ] || { printf 'off'; return 0; }

  var="$(aiorg_role_var "$role")_THINKS"
  value="${!var:-}"
  if [ "$value" = "true" ]; then
    printf 'on'
    return 0
  fi
  if [ "$value" = "false" ]; then
    printf 'off'
    printf 'aiorg_effective_think: %s resolves to a model with no thinking channel; running think=off\n' \
      "$role" >&2
    return 0
  fi
  # Capability not recorded. Still downgrade - see the note above.
  printf 'off'
  printf 'aiorg_effective_think: %s has no recorded thinking capability; running think=off until it is confirmed with tools/check-models.sh\n' \
    "$role" >&2
}

# ---------------------------------------------------------------------------
# Reaching the model server
# ---------------------------------------------------------------------------

# The address a CLIENT should use, as host:port.
#
# Three scripts talk to Ollama and all three used to do it differently - one
# honoured AI_OLLAMA_HOST, two called the bare `ollama` CLI and so always meant
# localhost. In a setup where the GPU is on another machine that difference is
# not cosmetic: the "already downloaded?" check asks the wrong box, decides the
# model is absent, and re-downloads it. One function, one convention.
#
# 0.0.0.0 is a bind address, not a destination, so it is mapped back to
# loopback rather than passed to a client.
aiorg_ollama_target() {
  local host="${AI_OLLAMA_HOST:-127.0.0.1}"
  case "$host" in
    0.0.0.0|'') host="127.0.0.1" ;;
  esac
  printf '%s:%s' "$host" "${AI_OLLAMA_PORT:-11434}"
}

# True when the model server is on THIS machine, which is the only case where a
# local check answers anything.
aiorg_ollama_is_local() {
  case "${AI_OLLAMA_HOST:-127.0.0.1}" in
    127.0.0.1|localhost|0.0.0.0|'') return 0 ;;
    *) return 1 ;;
  esac
}

# The base URL a CLIENT should use, e.g. http://127.0.0.1:11434
#
# Prefer this over $AI_OLLAMA_URL. That variable is written into the generated
# profile.env as a literal, so `export AI_OLLAMA_HOST=192.168.1.50` - the exact
# remedy the error message suggests - changes the host but leaves the URL
# pointing at 127.0.0.1. Everything reading AI_OLLAMA_URL therefore kept talking
# to the local machine no matter what the user exported.
#
# This computes the URL at call time from the current host and port, so the
# documented override works immediately, with no `detect` re-run and no edit to a
# generated file.
aiorg_ollama_url() {
  printf 'http://%s' "$(aiorg_ollama_target)"
}

# ---------------------------------------------------------------------------
# Per-action risk tiers
# ---------------------------------------------------------------------------
#
# AGENT_SAFETY is per AGENT, so a `standard` agent is equally trusted to draft a
# patch and to deploy it. The stated principle is per ACTION, and nothing could
# express "may draft, may not deploy" until now.
#
# Two keys, and the order matters:
#
#   AGENT_SAFETY    the CEILING. Coarse, three values, unchanged meaning.
#   AGENT_ACTIONS   optional. May only ever be NARROWER than the ceiling.
#
# Narrower is the whole point. A ceiling that can be widened by the same file it
# limits is not a ceiling, so an action above the ceiling is a hard error in
# check-agents.py and refuses the run in test-agent.sh - not a warning.
#
# What this does NOT do, stated plainly: it does not sandbox anything. An agent
# that can run commands can still run the wrong ones. This makes the permission
# set explicit, checkable, and recorded next to every score, and it stops a
# config from claiming more than its safety level allows. Real enforcement is
# the OS's job, and nothing here pretends otherwise.
AIORG_ACTIONS="read write write_other execute network config deploy"

# The most an agent at this safety level may ever do.
aiorg_safety_ceiling() {
  case "${1:-}" in
    read-only) printf 'read' ;;
    # write_other is in the standard ceiling because the teacher's entire job is
    # producing skills inside OTHER agents' workspaces. That made the old
    # one-line description of `standard` ("its own workspace") wrong for the one
    # agent that most needs the tier, so it is spelled out here instead.
    standard)  printf 'read,write,write_other' ;;
    full)      printf '%s' "$AIORG_ACTIONS" | tr ' ' ',' ;;
    *)         return 1 ;;
  esac
}

# The actions actually in force: the declared list, validated and intersected
# with the ceiling. Empty AGENT_ACTIONS means "the whole ceiling".
#
# Exit codes: 0 ok, 1 unknown safety value, 2 unknown action name,
# 3 an action the ceiling does not allow.
aiorg_effective_actions() {
  local safety="${1:-}" declared="${2:-}"
  local ceiling a out=""
  ceiling="$(aiorg_safety_ceiling "$safety")" || return 1
  [ -n "${declared// /}" ] || { printf '%s' "$ceiling"; return 0; }

  local IFS=','
  for a in $declared; do
    a="${a// /}"
    [ -n "$a" ] || continue
    case " $AIORG_ACTIONS " in
      *" $a "*) ;;
      *) return 2 ;;
    esac
    case ",$ceiling," in
      *",$a,"*) out="${out:+$out,}$a" ;;
      *) return 3 ;;
    esac
  done
  [ -n "$out" ] || return 3
  printf '%s' "$out"
}

# May this agent do this? Reads AGENT_SAFETY / AGENT_ACTIONS from the environment,
# so call it after sourcing an agent.conf.
#
# Exit: 0 allowed, 1 not allowed, 2 the config is inconsistent.
aiorg_agent_may() {
  local action="${1:-}" eff
  [ -n "$action" ] || return 2
  eff="$(aiorg_effective_actions "${AGENT_SAFETY:-}" "${AGENT_ACTIONS:-}")" || return 2
  case ",$eff," in
    *",$action,"*) return 0 ;;
    *) return 1 ;;
  esac
}

# The audit-log spelling. '+' rather than ',' because the audit sanitiser keeps
# '+' and turns ',' into '_', which would run write_other into write_other's
# neighbour. Fits the 64-char value cap at full width.
aiorg_actions_for_log() {
  local eff
  eff="$(aiorg_effective_actions "${1:-}" "${2:-}")" || return 1
  printf '%s' "${eff//,/+}"
}

# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

# The one subtlety: config/profile.env is GENERATED and contains a plain
# AI_OLLAMA_HOST="127.0.0.1" assignment, because that is what a generated file
# should look like. Sourcing it therefore overwrites an AI_OLLAMA_HOST the
# operator exported on purpose - while the comment in that same file says
# "Override by exporting AI_OLLAMA_HOST before bootstrap". The documented
# override silently did nothing, and every reader went to localhost instead of
# the GPU box.
#
# This is the third round of the same bug in this project, and the shape is
# always the same: one canonical helper (aiorg_ollama_url), several readers, and
# a generated file quietly winning the argument. So the pre-set value is saved
# and restored around the source, rather than by editing profile.env - which
# rule 2 forbids anyway, since `./bootstrap.sh detect` would just rewrite it.
# Source config/profile.env, letting a deliberate AI_OLLAMA_HOST override win.
#
# This is a function rather than a bare `.` at each call site on purpose. The
# override rule was first implemented inside require_profile(), and `./bootstrap.sh
# status` then kept bypassing it by sourcing the profile directly - so status
# still reported the local server as running while pointed at another box. The
# bug came back the moment a second caller appeared, which is the same lesson as
# the three model-server conventions and the two timeout units: the rule has to
# live somewhere every caller is forced through.
#
# Any code that needs the profile must call this (or require_profile, which
# calls this). Never `. "$AIORG_PROFILE"` directly.
source_profile() {
  # A pre-set host is a deliberate override and wins. An empty one is just an
  # unset variable, which must not be mistaken for an override of "".
  local _host="" _port=""
  if [ -n "${AI_OLLAMA_HOST:-}" ]; then _host="$AI_OLLAMA_HOST"; fi
  if [ -n "${AI_OLLAMA_PORT:-}" ]; then _port="$AI_OLLAMA_PORT"; fi

  # shellcheck disable=SC1090
  . "$AIORG_PROFILE"

  if [ -n "$_host" ]; then
    export AI_OLLAMA_HOST="$_host"
    # Recompute rather than restoring a stale AI_OLLAMA_URL: a caller that
    # overrode only the host should get a matching URL, and this file already
    # has a helper for turning a host into a URL.
    export AI_OLLAMA_URL="$(aiorg_ollama_url)"
    [ -n "$_port" ] && export AI_OLLAMA_PORT="$_port"
    [ "${AIORG_VERBOSE:-0}" != "0" ] && \
      log_dim "AI_OLLAMA_HOST override honoured: $AI_OLLAMA_HOST"
  fi
  return 0
}

# Every script except 00-detect requires a resolved profile.
require_profile() {
  if [ ! -f "$AIORG_PROFILE" ]; then
    log_err "No hardware profile found."
    log_dim "Run:  $AIORG_ROOT/bootstrap.sh detect"
    exit 1
  fi
  source_profile
}

# ---------------------------------------------------------------------------
# Hardware tier
#
# The tier is a coarse label derived from usable VRAM. Every model choice and
# context length in this project keys off the tier, never off a hardcoded size.
# Adding a bigger GPU later changes the tier, which changes the models, with
# no edits to any script.
#
#   cpu      no usable GPU
#   vram_8   6 - 10 GB
#   vram_12  11 - 15 GB
#   vram_16  16 - 23 GB
#   vram_24  24 - 31 GB     single 24GB card (3090 / A5000)
#   vram_32  32 - 47 GB     RTX 5090
#   vram_48  48 - 79 GB     dual 24GB, or a single 48GB pro card
#   vram_80  80 GB +        multi-GPU workstation / server
# ---------------------------------------------------------------------------
tier_for_vram_mb() {
  local mb="${1:-0}"
  # Guard against a GPU-less box reporting something silly.
  if [ "$mb" -lt 4000 ]; then echo "cpu"; return 0; fi
  local gb=$((mb / 1024))
  if   [ "$gb" -lt 11 ]; then echo "vram_8"
  elif [ "$gb" -lt 16 ]; then echo "vram_12"
  elif [ "$gb" -lt 24 ]; then echo "vram_16"
  elif [ "$gb" -lt 32 ]; then echo "vram_24"
  elif [ "$gb" -lt 48 ]; then echo "vram_32"
  elif [ "$gb" -lt 80 ]; then echo "vram_48"
  else                        echo "vram_80"
  fi
}

tier_label() {
  case "$1" in
    cpu)     echo "CPU only" ;;
    vram_8)  echo "6-10 GB VRAM" ;;
    vram_12) echo "11-15 GB VRAM" ;;
    vram_16) echo "16-23 GB VRAM" ;;
    vram_24) echo "24-31 GB VRAM (single card)" ;;
    vram_32) echo "32-47 GB VRAM" ;;
    vram_48) echo "48-79 GB VRAM (multi-GPU or pro card)" ;;
    vram_80) echo "80+ GB VRAM (workstation)" ;;
    *)       echo "unknown" ;;
  esac
}

# Context window to request for a given tier. Deliberately conservative:
# agent loops re-send the conversation every turn, so KV cache is the thing
# that actually kills you. Raise AI_CONTEXT_OVERRIDE to override.
tier_context() {
  local override="${AI_CONTEXT_OVERRIDE:-}"
  if [ -n "$override" ]; then echo "$override"; return 0; fi
  case "$1" in
    cpu)     echo 8192 ;;
    vram_8)  echo 8192 ;;
    vram_12) echo 16384 ;;
    vram_16) echo 16384 ;;
    vram_24) echo 32768 ;;
    vram_32) echo 49152 ;;
    vram_48) echo 65536 ;;
    vram_80) echo 98304 ;;
    *)       echo 8192 ;;
  esac
}

# Threads to run in parallel. More VRAM = more concurrent agent sessions.
tier_parallel() {
  case "$1" in
    cpu)     echo 1 ;;
    vram_8)  echo 1 ;;
    vram_12) echo 1 ;;
    vram_16) echo 2 ;;
    vram_24) echo 2 ;;
    vram_32) echo 3 ;;
    vram_48) echo 4 ;;
    vram_80) echo 6 ;;
    *)       echo 1 ;;
  esac
}

# Whether heavy creative work (video/image models) can share this GPU with
# the LLM agents, or needs the card to itself.
tier_creative_isolation() {
  case "$1" in
    vram_24|vram_32) echo "shared" ;;   # 24-32GB: queue creative work
    vram_48|vram_80) echo "shared" ;;   # enough headroom for both
    *)               echo "exclusive" ;; # too small, must stop agents first
  esac
}

human_gb() {
  local mb="${1:-0}"
  awk -v mb="$mb" 'BEGIN { printf "%.1f", mb/1024 }'
}
