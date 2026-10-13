#!/usr/bin/env bash
# Run every agent's closed-book suite against qwen3:0.6b on this CPU box.
#
# On the COPY at /tmp/aiorg-cpu, never the real tree: test-agent.sh writes
# AGENT_LAST_SCORE into agent.conf and appends to state/audit.log, and a 0.6B
# score would be a real-looking number that measures nothing.
set -u

ROOT=/tmp/aiorg-cpu
LOG=/tmp/aiorg-cpu-runs
mkdir -p "$LOG"
cd "$ROOT" || exit 1

# Order: cheapest/most-signal first, so there is something to look at early
# instead of eight hours of nothing. helpdesk and coder already have a
# measured per-case cost from the earlier spot checks.
ORDER="helpdesk coder personal languages teacher research-officer security-engineer \
network-engineer storage-engineer tech-researcher design-researcher \
education-researcher web-researcher cto ceo storyteller"

for a in $ORDER; do
  [ -d "agents/$a" ] || { echo "SKIP $a (no such agent)" >> "$LOG/summary.txt"; continue; }
  start=$(date +%s)
  echo "=== $a start $(date -Iseconds)" >> "$LOG/progress.txt"
  bash ./tools/test-agent.sh "$a" > "$LOG/$a.out" 2>&1
  rc=$?
  dur=$(( $(date +%s) - start ))
  pct=$(grep -oE '[0-9]+/[0-9]+ passed \([0-9]+%\)' "$LOG/$a.out" | tail -1)
  [ -z "$pct" ] && pct="no result"
  printf '%-20s rc=%-2s %5ss  %s\n' "$a" "$rc" "$dur" "$pct" >> "$LOG/summary.txt"
  echo "=== $a done rc=$rc ${dur}s $pct" >> "$LOG/progress.txt"
done

echo "ALL DONE $(date -Iseconds)" >> "$LOG/progress.txt"
