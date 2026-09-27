#!/usr/bin/env bash
# test-agent.sh - the training loop.
#
#   ./tools/test-agent.sh coder
#   ./tools/test-agent.sh coder --verbose
#   ./tools/test-agent.sh coder --only boundary
#
# Runs an agent's test cases against its resolved model, with its SOUL.md as
# the system prompt, and checks the reply against what the case demands.
#
# This script does not know which program is executing the agent. It reads
# AGENT_RUNTIME from the agent's agent.conf and asks lib/runtime.sh to do the
# work, so the same test suite runs unchanged on any runtime in
# config/runtimes.json. If you find yourself adding a curl call to this file,
# the thing you want is a new adapter in lib/runtime.sh instead.
#
# Test case format, in agents/<name>/tests/cases.tsv:
#
#   name ::: prompt ::: must_contain ::: must_not_contain
#
# The columns are separated by ':::' rather than '|' so that a prompt is free
# to contain a pipe - which matters when the agent you are testing writes shell
# commands, and a pipe is the most common character in a shell prompt.
#
# Within the check columns, ',' means "all of these" and '||' separates
# alternative groups where any one complete group passes:
#
#   error, traceback          both words must appear
#   dont know, not real       neither is required - use:  not real || fictional
#   error, traceback || None  the first pair, or "None" on its own
#
# When writing a SAFETY case, remember that the alternatives must be exclusive
# to correct behaviour. A case asserting "counters || read the rules" will pass
# a reply that also says "sudo iptables -F", because both contain the same
# words. Put the refusal language in must_contain and the destructive command
# itself in must_not_contain.
#
# This is how you make an agent good:
#
#   1. write a test case describing behaviour you need
#   2. run it
#   3. edit SOUL.md (or add a skill) to fix what failed
#   4. run it again
#
# It feels slow and it is not. It is also the only way to know you have not
# broken something that used to work, which is the failure that actually bites
# when you have a dozen agents.
#
# Every run is recorded in state/audit.log: which agent, which runtime, which
# model, which result. See lib/audit.sh for the format, and for why no prompt
# and no reply is ever written to it. Read it back with ./tools/audit-log.sh.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"
# shellcheck source=../lib/runtime.sh
. "$AIORG_ROOT/lib/runtime.sh"
# shellcheck source=../lib/audit.sh
. "$AIORG_ROOT/lib/audit.sh"

VERBOSE=0
ONLY=""
THRESHOLD="${AI_TEST_THRESHOLD:-80}"
AGENT=""

while [ $# -gt 0 ]; do
  case "$1" in
    -v|--verbose) VERBOSE=1; shift ;;
    --only) ONLY="${2:-}"; shift 2 ;;
    --threshold) THRESHOLD="${2:-80}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: ./tools/test-agent.sh <agent-name> [options]

Options may come before or after the agent name.

  -v, --verbose      print every full reply
  --only <substr>    only run cases whose name contains <substr>
  --threshold <n>    minimum pass percent to exit 0. Default 80.
EOF
      exit 0 ;;
    -*) die "Unknown option: $1  (try --help)" ;;
    *)
      if [ -z "$AGENT" ]; then
        AGENT="$1"
        shift
      else
        die "Unexpected argument: $1  (one agent at a time)"
      fi ;;
  esac
done

[ -n "$AGENT" ] || { log_err "Which agent? Try: ./tools/test-agent.sh coder"; exit 1; }

DIR="$AIORG_ROOT/agents/$AGENT"
CONF="$DIR/agent.conf"
SOUL="$DIR/SOUL.md"
CASES="$DIR/tests/cases.tsv"

[ -f "$CONF" ] || die "No such agent: $AGENT
  Create one with:  ./tools/new-agent.sh $AGENT
  Or list existing: ./tools/new-agent.sh --list"
[ -f "$SOUL" ] || die "$AGENT has no SOUL.md. That is the agent's personality - create it first."
[ -f "$CASES" ] || die "$AGENT has no tests/cases.tsv. Nothing to test is the same as failing."

require_profile

# shellcheck disable=SC1090
. "$CONF"
[ -f "$AIORG_CONFIG/models.env" ] || die "No resolved models. Run: ./bootstrap.sh detect"
# shellcheck disable=SC1090
. "$AIORG_CONFIG/models.env"

# Which runtime executes this agent. Resolved here, once, so the rest of this
# script never has to know what is on the other end of the socket.
RUNTIME="${AGENT_RUNTIME:-}"

MODEL_VAR="$(aiorg_role_var "${AGENT_MODEL_ROLE:-fast}")_MODEL"
MODEL="${!MODEL_VAR:-}"

# What the agent ASKED for, and what will actually be sent. These are different
# questions: AGENT_THINK is static, the resolved model is not, and Ollama
# refuses think:true outright for a model with no reasoning channel. Resolved
# once here so the audit log records what was really sent rather than what was
# requested - a log that says think=on for a run that ran think=off is a lie
# about the one thing you would use it to diagnose.
EFFECTIVE_THINK="$(aiorg_effective_think "${AGENT_MODEL_ROLE:-fast}" "${AGENT_THINK:-off}")"
if [ "$EFFECTIVE_THINK" != "${AGENT_THINK:-off}" ]; then
  log_dim "  think downgraded: '${AGENT_THINK:-off}' requested, '$EFFECTIVE_THINK' sent"
  log_dim "    '$MODEL' has no thinking channel. See aiorg_effective_think in lib/common.sh."
fi

if [ -z "$MODEL" ]; then
  die "No model resolved for role '$AGENT_MODEL_ROLE'.
  Available roles: $AI_ROLES
  If this role resolved to nothing, your hardware cannot fit a candidate for it
  yet. Add a smaller one in config/models.json, or change AGENT_MODEL_ROLE in
  agents/$AGENT/agent.conf"
fi

# The system prompt is the whole SOUL.md. A long persona eats context, so check
# we are not about to blow the window. Read before the probe because the audit
# record wants the persona size even for a run that never starts.
SOUL_WORDS="$(wc -w < "$SOUL")"
SYSTEM_PROMPT="$(cat "$SOUL")"

# --- per-action risk tiers: resolve the permission set before anything runs ---
#
# This is the enforcement point. check-agents.py reports a bad AGENT_ACTIONS, but
# a report is not a gate - someone can skip the checker, and an agent.conf is a
# text file anyone can edit. So the harness re-derives the set and refuses to
# start a run whose config asks for more than its safety level allows.
#
# An inconsistent config must not produce a score. A score from a run whose
# declared permissions were never valid is worse than no score, because it looks
# like a measurement.
EFFECTIVE_ACTIONS=""
# `if ! cmd; then case "$?"` is wrong: the bang inverts the status, so $? is 0
# inside the then-block, no branch matched, and the script carried on with an
# empty permission set and then died silently on the next assignment. A refusal
# that prints nothing is worse than no check, because it looks like nothing ran.
if EFFECTIVE_ACTIONS="$(aiorg_effective_actions "${AGENT_SAFETY:-}" "${AGENT_ACTIONS:-}")"; then
  :
else
  case "$?" in
    1) die "AGENT_SAFETY='${AGENT_SAFETY:-}' is not a known level in $AIORG_ROOT/agents/$AGENT/agent.conf" ;;
    2) die "AGENT_ACTIONS in $AIORG_ROOT/agents/$AGENT/agent.conf names an action that does not exist. Run ./bootstrap.sh check" ;;
    3) die "AGENT_ACTIONS in $AIORG_ROOT/agents/$AGENT/agent.conf asks for more than AGENT_SAFETY='${AGENT_SAFETY:-}' allows. AGENT_ACTIONS may only narrow it. Run ./bootstrap.sh check" ;;
  esac
fi
ACTIONS_LOG="$(aiorg_actions_for_log "${AGENT_SAFETY:-}" "${AGENT_ACTIONS:-}")"

# Open the audit record BEFORE the probe. A run that never started because the
# runtime was down is a thing that happened, and it is exactly the kind of thing
# you want to be able to look back at.
audit_open run \
  "agent=$AGENT" \
  "runtime=$RUNTIME" \
  "model=$MODEL" \
  "role=${AGENT_MODEL_ROLE:-}" \
  "safety=${AGENT_SAFETY:-}" \
  "actions=$ACTIONS_LOG" \
  "network=${AGENT_NETWORK:-}" \
  "think=$EFFECTIVE_THINK" \
  "temp=${AGENT_TEMPERATURE:-0}" \
  "persona_words=$SOUL_WORDS"

# If this run dies between here and the audit_close at the bottom, the record
# still has to say so. A crash that leaves no trace is the one failure an audit
# log exists to prevent.
_audit_on_exit() {
  local rc=$?
  if audit_is_open; then
    audit_close verdict=error \
      "reason=${AUDIT_REASON:-died-before-finishing}" \
      "exit_code=$rc"
  fi
}
trap _audit_on_exit EXIT

# Ask the runtime whether it can do this job, before running 30 cases against
# it. The message comes from the adapter, so it stays correct when the runtime
# changes.
if ! probe_err="$(runtime_probe "$RUNTIME" "$MODEL")"; then
  AUDIT_REASON="runtime-probe-failed"
  die "$probe_err"
fi

# Thinking models (qwen3, deepseek-r1) put their reasoning in a separate
# "thinking" field and can spend the entire token budget there, returning an
# empty answer. Off by default, so the checks inspect the reply a user would
# actually see. Set AGENT_THINK=on in agent.conf to test the thinking variant.
MAXTOK="${AGENT_MAX_TOKENS:-512}"
# Temperature 0 by default. A test suite that returns a different score every
# run cannot tell a regression from noise, and you will end up chasing changes
# that were never there. Raise it only when you are testing something where
# variation is the point. Both of these are passed to the runtime as-is; how
# they turn into a request is the adapter's problem, not this script's.
TIMEOUT_SECS="$(( ${AGENT_TIMEOUT_MIN:-30} * 60 ))"

echo
log_step "Testing agent '$AGENT'"
log_dim "  title:   $AGENT_TITLE"
log_dim "  runtime: $RUNTIME"
log_dim "  model:   $MODEL  (role: $AGENT_MODEL_ROLE)"
log_dim "  persona: $SOUL_WORDS words"
log_dim "  limits:  safety=$AGENT_SAFETY network=$AGENT_NETWORK turns=$AGENT_MAX_TURNS max_tokens=$MAXTOK think=$EFFECTIVE_THINK temp=${AGENT_TEMPERATURE:-0} timeout=${AGENT_TIMEOUT_MIN}m"
log_dim "  actions: $ACTIONS_LOG"
if [ "${AGENT_RETRIEVAL:-off}" = "on" ]; then
  # Said every run, because this agent is normally used WITH sources and this
  # number is produced without any. A reader comparing a researcher's score to
  # its usefulness in the real world would otherwise be reading two different
  # measurements under one name.
  log_dim "  note:    this agent is normally run open-book (AGENT_RETRIEVAL=on)."
  log_dim "           tests are closed-book by design, so this score measures"
  log_dim "           judgement WITHOUT sources - a deliberately narrower thing."
fi
echo

PASS=0
FAIL=0
SKIP=0
FAILED_CASES=()

REASONS=()

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

# check_field <spec> <haystack> <negate>
#
# A spec is one or more groups of items:
#
#   "a,b"          every item must appear
#   "a,b || c,d"   any ONE complete group is enough
#
# In negate mode an item is a violation instead, so a group is clean when none
# of its items appear, and every group must be clean.
check_field() {
  local spec="$1" hay="$2" negate="$3"
  [ -z "$(trim "$spec")" ] && return 0

  local groups group item group_pass all_clean=1 best_found=-1 best_missing=""
  local -a items missing
  local found

  groups="$(printf '%s' "$spec" | sed 's/||/\n/g')"

  while IFS= read -r group || [ -n "$group" ]; do
    group="$(trim "$group")"
    [ -z "$group" ] && continue
    IFS=',' read -ra items <<< "$group"
    missing=(); found=0; group_pass=1

    for item in "${items[@]}"; do
      item="$(trim "$item")"
      [ -z "$item" ] && continue
      if printf '%s' "$hay" | grep -qiF -- "$item"; then
        found=$((found + 1))
        if [ "$negate" -eq 1 ]; then
          REASONS+=("should not contain: \"$item\"")
          group_pass=0
          all_clean=0
        fi
      elif [ "$negate" -eq 0 ]; then
        missing+=("$item")
        group_pass=0
      fi
    done

    if [ "$negate" -eq 0 ]; then
      [ "$group_pass" -eq 1 ] && return 0
      if [ "$found" -gt "$best_found" ]; then
        best_found="$found"
        best_missing=""
        for m in ${missing[@]+"${missing[@]}"}; do
          best_missing="${best_missing}${best_missing:+, }$m"
        done
      fi
    fi
  done <<< "$groups"

  if [ "$negate" -eq 1 ]; then
    [ "$all_clean" -eq 1 ] && return 0
    return 1
  fi

  if [ -n "$best_missing" ]; then
    REASONS+=("no complete match; closest group was missing: $best_missing")
  else
    REASONS+=("nothing matched: $spec")
  fi
  return 1
}

run_case() {
  local cname="$1" prompt="$2" must="$3" mustnot="$4"
  local raw reply think needle reason

  raw="$(runtime_chat "$RUNTIME" "$MODEL" "$SYSTEM_PROMPT" "$prompt" \
          "$MAXTOK" "${AGENT_TEMPERATURE:-0}" "$EFFECTIVE_THINK" \
          "$TIMEOUT_SECS")" || raw=''

  if [ -z "$raw" ]; then
    log_err "$cname: runtime '$RUNTIME' returned nothing"
    log_dim "    Either it timed out after ${AGENT_TIMEOUT_MIN:-30}m, or it is"
    log_dim "    overloaded. runtime_probe passed, so the runtime is reachable"
    log_dim "    and has the model - check whether the GPU is busy with another"
    log_dim "    agent, or raise AGENT_TIMEOUT_MIN in $CONF."
    FAILED_CASES+=("$cname (no response)")
    FAIL=$((FAIL + 1))
    return
  fi

  if ! printf '%s' "$raw" | jq -e . >/dev/null 2>&1; then
    log_err "$cname: server did not return JSON"
    log_dim "    $(printf '%s' "$raw" | tr '\n' ' ' | cut -c1-200)"
    FAILED_CASES+=("$cname (bad response)")
    FAIL=$((FAIL + 1))
    return
  fi

  reason="$(printf '%s' "$raw" | jq -r '.error // empty')"
  if [ -n "$reason" ]; then
    log_err "$cname: $reason"
    FAILED_CASES+=("$cname (api error)")
    FAIL=$((FAIL + 1))
    return
  fi

  reply="$(printf '%s' "$raw" | jq -r '.message.content // ""')"
  think="$(printf '%s' "$raw" | jq -r '.message.thinking // ""')"

  if [ -z "$reply" ] && [ -n "$think" ]; then
    log_err "$cname: model spent its whole budget thinking and never answered"
    log_dim "    Its reply was empty. Raise AGENT_MAX_TOKENS in $CONF,"
    log_dim "    or set AGENT_THINK=off in agent.conf."
    FAILED_CASES+=("$cname (thinking ate the budget)")
    FAIL=$((FAIL + 1))
    return
  fi

  if [ -z "$reply" ]; then
    log_err "$cname: model returned an empty reply"
    FAILED_CASES+=("$cname (empty reply)")
    FAIL=$((FAIL + 1))
    return
  fi

  local case_ok=1
  REASONS=()

  check_field "$must" "$reply" 0 || case_ok=0
  check_field "$mustnot" "$reply" 1 || case_ok=0

  if [ "$case_ok" -eq 1 ]; then
    log_ok "$cname"
    PASS=$((PASS + 1))
  else
    log_err "$cname"
    for r in "${REASONS[@]}"; do log_dim "    $r"; done
    FAILED_CASES+=("$cname")
    FAIL=$((FAIL + 1))
  fi

  if [ "$VERBOSE" -eq 1 ]; then
    log_dim "    prompt: $prompt"
    log_dim "    reply:  $(printf '%s' "$reply" | head -c 600 | tr '\n' ' ')"
    echo
  fi
}

# ---- parse the cases file ---------------------------------------------------
FORMAT_WARNED=0
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ''|'#'*) continue ;;
  esac

  # Catch the two mistakes that silently corrupt a run: the old '|' delimiter,
  # and a line that is missing its prompt. A wrong prompt still produces output,
  # so without this the failure looks like a bad model rather than a bad file.
  case "$line" in
    *':::'*) ;;
    *'|'*)
      if [ "$FORMAT_WARNED" -eq 0 ]; then
        log_warn "That line uses '|' as the column separator. The format is now"
        log_dim "    name ::: prompt ::: must_contain ::: must_not_contain"
        log_dim "    Columns are separated by ':::' so a prompt can contain a pipe."
        FORMAT_WARNED=1
      fi
      SKIP=$((SKIP + 1))
      continue ;;
  esac

  # ':::' is more than one character, which cut cannot use as a delimiter, so
  # awk does the split and the four fields come back one per line.
  mapfile -t fields < <(printf '%s\n' "$line" | awk -F':::' '{print $1; print $2; print $3; print $4}')

  cname="$(trim "${fields[0]-}")"
  prompt="$(trim "${fields[1]-}")"
  must="$(trim "${fields[2]-}")"
  mustnot="$(trim "${fields[3]-}")"

  if [ -z "$prompt" ]; then
    log_warn "Skipping '$cname': no prompt. A case needs at least"
    log_dim "    name ::: prompt"
    continue
  fi
  if [ -n "$ONLY" ] && ! printf '%s' "$cname" | grep -qiF -- "$ONLY"; then
    SKIP=$((SKIP + 1))
    continue
  fi

  run_case "$cname" "$prompt" "$must" "$mustnot"
done < "$CASES"

TOTAL=$((PASS + FAIL))
if [ "$TOTAL" -eq 0 ]; then
  echo
  log_err "No test cases ran. In $CASES a real case looks like:"
  log_dim "    name ::: prompt ::: must_contain ::: must_not_contain"
  log_dim "  Lines starting with '#' are comments, and a case needs a prompt."
  AUDIT_REASON="no-cases-ran"
  exit 1
fi

PCT=$(( PASS * 100 / TOTAL ))

echo
log_step "Result: $PASS/$TOTAL passed ($PCT%)"
[ "$SKIP" -gt 0 ] && log_dim "  $SKIP case(s) filtered out by --only"
echo

if [ "$FAIL" -gt 0 ]; then
  log_warn "Failing:"
  for c in "${FAILED_CASES[@]}"; do log_dim "  - $c"; done
  echo
  log_dim "The fix is almost always in SOUL.md, not in the model. Add or sharpen"
  log_dim "the instruction that covers this case, then re-run. If the case"
  log_dim "itself is wrong or unfair, fix the test - a test you disagree with"
  log_dim "is not a useful test."
  echo
fi

# ---- record the result ------------------------------------------------------
# Both places, deliberately. agent.conf is what a human reads; the audit log is
# what you trust, because it also holds the runtime and the model. A score in
# agent.conf with no corresponding line here is a score that came from nowhere.

# The failed case NAMES, not their content. Names are identifiers the author
# chose; prompts and replies are outside-world data, and the reason this project
# keeps its read-only agents read-only is that such data never becomes an
# instruction. See lib/audit.sh.
AUDIT_EXTRA=()
if [ "$FAIL" -gt 0 ]; then
  failed_list=""
  for c in "${FAILED_CASES[@]:0:12}"; do
    failed_list="${failed_list:+$failed_list,}$c"
  done
  [ "$FAIL" -gt 12 ] && failed_list="$failed_list,+$((FAIL - 12))more"
  AUDIT_EXTRA+=("failed=$failed_list")
fi

audit_close \
  "verdict=$([ "$PCT" -ge "$THRESHOLD" ] && echo pass || echo fail)" \
  "cases=$TOTAL" \
  "pass=$PASS" \
  "fail=$FAIL" \
  "skipped=$SKIP" \
  "pct=$PCT" \
  "threshold=$THRESHOLD" \
  "${AUDIT_EXTRA[@]}"

sed -i "s|^AGENT_LAST_TESTED=.*|AGENT_LAST_TESTED=\"$(date -Iseconds)\"|" "$CONF"
sed -i "s|^AGENT_LAST_SCORE=.*|AGENT_LAST_SCORE=\"$PCT%\"|" "$CONF"

if [ "$PCT" -ge "$THRESHOLD" ]; then
  if [ "${AGENT_STATUS:-building}" = "building" ]; then
    log_dim "Tip: when this is reliable, set AGENT_STATUS=\"ready\" in $CONF"
  fi
  log_ok "Above threshold ($THRESHOLD%)."
  exit 0
else
  log_err "Below threshold ($THRESHOLD%). Not ready for real work."
  exit 1
fi
