#!/usr/bin/env bash
# audit-log.sh - read state/audit.log.
#
#   ./tools/audit-log.sh                 the last 20 records, as a table
#   ./tools/audit-log.sh --tail 50
#   ./tools/audit-log.sh --agent coder   everything one agent has run
#   ./tools/audit-log.sh --failures      only runs that did not pass
#   ./tools/audit-log.sh --stats         counts by agent and verdict
#   ./tools/audit-log.sh --raw           the log lines, unformatted
#
# An audit log nobody reads is decoration. This is the read path.
#
# The format is one line per run, `event=` first and the rest as key=value in
# a fixed order. Column order is fixed on purpose so cut and awk work on it:
#
#   <timestamp> event=<event> [dur=<n>s] <k=v>...
#
# lib/audit.sh is the only writer. Nothing here parses free text, because there
# is no free text - see the header there for why no prompt or reply is ever
# recorded.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"
# shellcheck source=../lib/audit.sh
. "$AIORG_ROOT/lib/audit.sh"

TAIL=20
FILTER_AGENT=""
ONLY_FAILURES=0
RAW=0
STATS=0

usage() { sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--tail)     TAIL="${2:-20}"; shift 2 ;;
    -a|--agent)    FILTER_AGENT="${2:-}"; shift 2 ;;
    -f|--failures) ONLY_FAILURES=1; shift ;;
    -r|--raw)      RAW=1; shift ;;
    -s|--stats)    STATS=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) die "Unknown option: $1  (try --help)" ;;
  esac
done

LOG="$AIORG_AUDIT_LOG"

if [ ! -f "$LOG" ]; then
  log_err "No audit log yet at $LOG"
  log_dim "It is written by ./tools/test-agent.sh, so run an agent first:"
  log_dim "  ./tools/test-agent.sh coder --only boundary"
  exit 1
fi

# Pull one key=value out of a record line. Used for filtering, where a
# substring match would also catch model=coder or agent=coder-engineer.
#
# Scans every field and keeps the last match, which is what the awk below does
# too. lib/audit.sh can write a key twice if audit_open and audit_close both set
# it, and the two readers must not disagree about which one counts.
field() {
  local line="$1" key="$2" tok val=""
  for tok in $line; do
    case "$tok" in
      "$key="*) val="${tok#"$key="}" ;;
    esac
  done
  printf '%s' "$val"
}

# --- stats -------------------------------------------------------------------
if [ "$STATS" -eq 1 ]; then
  TOTAL="$(grep -c . "$LOG" || true)"
  echo
  log_step "Audit log: $LOG"
  log_dim "  $TOTAL record(s)"
  echo
  printf '  %-24s %7s %7s %7s\n' AGENT RUNS PASSED FAILED
  printf '  %-24s %7s %7s %7s\n' '------------------------' '-------' '-------' '-------'
  awk -v OFS=' ' '
    { agent="?"; verdict=""
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^agent=/)   agent = substr($i, 7)
        if ($i ~ /^verdict=/) verdict = substr($i, 9)
      }
      runs[agent]++
      if (verdict == "pass") passed[agent]++; else failed[agent]++
    }
    END {
      for (a in runs)
        printf "  %-24s %7d %7d %7d\n", a, runs[a], passed[a]+0, failed[a]+0
    }' "$LOG" | sort
  echo
  exit 0
fi

# --- filter ------------------------------------------------------------------
SELECTED="$(mktemp)"
trap 'rm -f "$SELECTED"' EXIT

while IFS= read -r line; do
  [ -n "$line" ] || continue
  if [ -n "$FILTER_AGENT" ] && [ "$(field "$line" agent)" != "$FILTER_AGENT" ]; then
    continue
  fi
  if [ "$ONLY_FAILURES" -eq 1 ]; then
    case "$(field "$line" verdict)" in
      pass|"") continue ;;
    esac
  fi
  printf '%s\n' "$line" >> "$SELECTED"
done < "$LOG"

MATCHED="$(grep -c . "$SELECTED" || true)"

if [ "$RAW" -eq 1 ]; then
  cat "$SELECTED"
  exit 0
fi

if [ "$MATCHED" -eq 0 ]; then
  echo
  log_warn "No records matched."
  if [ -n "$FILTER_AGENT" ]; then
    log_dim "  agent '$FILTER_AGENT' has never run. The agents that have:"
    # A typo in the filter is the likely reason we are here, so name the real
    # ones. Strips the agent= prefix so they are copy-pasteable.
    grep -o 'agent=[^ ]*' "$LOG" 2>/dev/null | sort -u | sed 's/^agent=//;s/^/    /' || true
  else
    log_dim "  The log exists but nothing in it passed the filter."
  fi
  exit 1
fi

# --- table -------------------------------------------------------------------
echo
log_step "Audit log: $LOG"
if [ "$TAIL" -eq 0 ]; then
  log_dim "  $MATCHED record(s), all of them"
elif [ "$MATCHED" -gt "$TAIL" ]; then
  log_dim "  $MATCHED record(s), showing the last $TAIL.  --tail 0 for all."
else
  log_dim "  $MATCHED record(s)"
fi
echo
printf '  %-16s %-20s %-18s %-9s %-8s %-22s %s\n' \
  WHEN AGENT MODEL VERDICT SCORE DURATION ACTIONS
printf '  %-16s %-20s %-18s %-9s %-8s %-22s %s\n' \
  '----------------' '--------------------' '------------------' '---------' '--------' \
  '----------------------' '--------'

tail -n "$([ "$TAIL" -gt 0 ] && echo "$TAIL" || echo "+0")" "$SELECTED" | awk '
  {
    # Drop the year from the table view. It is in the raw line, and a column
    # wide enough to hold it leaves no gap before the agent name.
    ts = $1
    sub(/^[0-9][0-9][0-9][0-9]-/, "", ts)
    gsub(/T/, " ", ts)
    agent = model = verdict = pct = dur = actions = "-"
    for (i = 2; i <= NF; i++) {
      if ($i ~ /^agent=/)   agent   = substr($i, 7)
      if ($i ~ /^model=/)   model   = substr($i, 7)
      if ($i ~ /^verdict=/) verdict = substr($i, 9)
      if ($i ~ /^pct=/)     pct     = substr($i, 5)
      if ($i ~ /^dur=/)     dur     = substr($i, 5)
      # The permission set the run actually had. A score is only interpretable
      # next to what the agent was allowed to do - two runs of the same agent at
      # different permission sets are not the same measurement.
      if ($i ~ /^actions=/) actions = substr($i, 9)
    }
    printf "  %-16s %-20s %-18s %-9s %-8s %-22s %s\n", ts, agent, model, verdict, pct, dur, actions
  }'

# A run with no verdict died between audit_open and audit_close. Only count
# event=run: a record of some other kind legitimately has no verdict, and
# warning about it would train you to ignore the warning.
INCOMPLETE="$(grep 'event=run' "$SELECTED" 2>/dev/null | grep -c -v 'verdict=' || true)"
echo
[ "$INCOMPLETE" -gt 0 ] && log_warn "$INCOMPLETE run(s) have no verdict - those did not finish. Raw: --raw"
exit 0
