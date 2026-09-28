#!/usr/bin/env bash
# =============================================================================
# mutation-audit.sh - the shell sibling of tools/mutation-audit.py
#
# Run it from the project root:
#
#     bash tools/mutation-audit.sh
#
# Same question, same method, different language. tools/mutation-audit.py asks
# "does a test own every finding tools/check-agents.py makes?". This asks the
# same thing about a shell instrument: it enumerates the reporting call sites in
# the target, redirects ONE of them at a no-op, and requires the suite to go RED.
# A site that stays green has no test asserting it.
#
#     usage: bash tools/mutation-audit.sh [TARGET ...]
#     default target: tools/check-models.sh
#     results: /tmp/opencode/mut_shell_results.json
#
# WHY A SEPARATE SCRIPT AND NOT A FLAG ON THE PYTHON ONE
#
# The two instruments find sites by different means and have different failure
# modes, and rule 19 of AGENTS.md is the reason not to merge them. The python
# harness walks an AST; a shell script has none, so this one greps for call
# sites and confirms each one landed by re-counting. Two implementations of one
# idea is two things that can disagree - which is how this project got five
# separate conventions for naming the model server, and how the role-var rule
# ended up hand-rolled four times before it broke on a hyphen. Keeping them
# apart means each is small enough to read, and the shared traps below are
# written down twice on purpose rather than factored into a helper that neither
# language can call.
#
# THE TRAPS, both of which this project's own docs record having already
# produced numbers that looked like findings about the tree while being bugs in
# the instrument:
#
# 1. Do not pick a scratch directory with `idx % WORKERS`. That chooses a
#    directory but not a thread, so workers interleave and overwrite each
#    other's mutations; the total then moves between identical runs. Each worker
#    gets a contiguous chunk AND its own tree.
# 2. A mutation whose line window missed its target must be reported as SKIP and
#    must NOT be counted as asserted. A mutation that never happened, reported
#    as a pass, is the exact false-pass shape this script exists to detect. This
#    is not hypothetical for shell: `bad "..."` and `warn "..."` are the easy
#    ones, but a `printf` finding has no call name to match on.
#
# WHAT COUNTS AS A FINDING HERE
#
# Enumerated, not guessed. A line is a finding site if it reports a problem to
# the operator: a `bad` or `warn` call, a `die` call, or a `printf` that emits a
# `[fail]` / `[warn]` / `[ ?? ]` marker. Informational lines (`ok`, `note`, the
# section headers) are not findings - silencing one loses no information a user
# needs, and counting them would pad the denominator with sites no test could
# reasonably own.
#
# The set is discovered by this script, not copied from a doc. PENDING-WORK.md
# recorded 5 sites by hand; measurement is the point, and the hand count is
# checked against the derived one rather than assumed to be right.
# =============================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NO_ARGS=0
[ $# -eq 0 ] && NO_ARGS=1
TARGETS=("$@")
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=("tools/check-models.sh")

RESULTS=/tmp/opencode/mut_shell_results.json
WORKROOT=/tmp/opencode/mut_shell
WORKERS=4

# --- self-test: can this harness fail at all? --------------------------------
# A mutation audit that cannot detect a broken harness is a coverage claim
# bought with the same confidence as a real one - the lesson of the
# `nvidia-smi` regression, where the original assertion passed against a script
# that died before reaching the check. It costs one run and it is the only thing
# standing between "8/8" and "8/8 because nothing ran".
#
# Run against a target that no test touches. Every site must come back GREEN or
# SKIP, and none may come back RED. If a mutation is red here, either the suite
# fails for reasons unrelated to the mutation or the harness is not measuring
# what it claims to.
#
# Guarded on NO_ARGS, captured from `$#` BEFORE the default target is filled in.
# The first version tested `[ ${#TARGETS[@]} -eq 0 ]` after defaulting it, which
# is never true, so the self-test silently never ran - and a self-test that
# cannot run is the same class of bug as a self-test that cannot fail. This is
# the fourth variant of this project's standing theme, and the second time in
# this one file: the guard meant to protect the measurement was the thing that
# made the measurement untrustworthy.
if [ "${AIORG_MUT_SELFTEST:-1}" = "1" ] && [ "$NO_ARGS" -eq 1 ]; then
  # The probe lives in a throwaway copy of the tree, and the recursion runs
  # against THAT copy - both because the target has to exist somewhere and
  # because a worker tree must never be the directory the harness deletes.
  # Getting this wrong was the fifth bug in this file: the first version
  # pointed the child at $ROOT, where the probe does not exist, and at a
  # WORKROOT containing the child's own source tree.
  probe_root=/tmp/opencode/mut_shell_selftest
  probe_work=/tmp/opencode/mut_shell_selftest_work
  rm -rf "$probe_root" "$probe_work"
  mkdir -p "$probe_root/tools"
  tar -C "$ROOT" --exclude=.git --exclude=__pycache__ -cf - . | tar -C "$probe_root" -xf -
  printf '#!/usr/bin/env bash\nbad()  { :; }\nbad "finding one"\nwarn() { :; }\nwarn "finding two"\nexit 0\n' \
    > "$probe_root/tools/_probe.sh"
  probe_out="$(cd "$probe_root" && AIORG_MUT_SELFTEST=0 WORKROOT="$probe_work" \
                 bash tools/mutation-audit.sh tools/_probe.sh 2>&1)"
  probe_rc=$?
  if [ "$probe_rc" -ne 0 ] || ! grep -qE 'asserted .*0/2' <<< "$probe_out"; then
    echo "mutation-audit.sh FAILED ITS OWN SELF-TEST - do not trust any number it prints."
    echo
    printf '%s\n' "$probe_out"
    exit 3
  fi
  echo "self-test ok: a target no test touches measures 0/2 asserted, not 2/2."
  echo
fi

# --- enumerate the finding sites in one target -------------------------------
# Emits: <lineno>\t<kind>\t<match-text>
#
# The first version of this matched only lines that START with bad/warn/die, and
# the result was a confident 8-site list that did not contain the phantom
# `[fail]`. Two defects, both invisible in the output and both fatal to the
# claim:
#
#   - A call in `case` command position is not at the start of the line. The
#     line reads `404) bad "..."` and the most important finding in the whole
#     file - a tag that is not in the registry - was silently not measured.
#   - The `bad()`/`warn()`/`die()` *definitions* matched, so muting line 53
#     replaced the body of the reporting function rather than a call to it.
#     Those are the instrument, not findings, and muting one made every `bad`
#     in the file disappear at once.
#
# So: a site is a CALL in command position - the name preceded only by
# whitespace, or by a `case` pattern and `)` - and never a definition. Matched
# with an explicit token test rather than a line-anchored one, and the
# definition form is excluded by name.
find_sites() {
  local f="$1"
  awk '
    # exclude the reporting helpers themselves: bad() { ... }
    /^[[:space:]]*(bad|warn|die|note|ok)[[:space:]]*\(\)/ { next }
    {
      line = $0
      # walk every occurrence of a reporting name and test what precedes it
      rest = line
      while (match(rest, /(bad|warn|die)[[:space:]]/)) {
        name = substr(rest, RSTART, RLENGTH); gsub(/[[:space:]]/, "", name)
        pre  = substr(rest, 1, RSTART - 1)
        # command position: only whitespace, or a case pattern then ")"
        if (pre ~ /^[[:space:]]*$/ || pre ~ /^[[:space:]]*[0-9*]+[[:space:]]*\)[[:space:]]*$/) {
          printf "%d\t%s\t%s\n", NR, name, line
          break
        }
        rest = substr(rest, RSTART + RLENGTH)
      }
      rest = line
      if (line ~ /printf/ && (line ~ /\[fail\]/ || line ~ /\[warn\]/ || line ~ /\[ \?\? \]/)) {
        printf "%d\tprintf\t%s\n", NR, line
      }
    }
  ' "$f"
}

# --- build an isolated tree per worker ---------------------------------------
build() {
  local w="$1" d="$WORKROOT/w$w"
  rm -rf "$d"
  mkdir -p "$d"
  tar -C "$ROOT" --exclude=.git --exclude=__pycache__ -cf - . | tar -C "$d" -xf -
  printf '%s' "$d"
}

# --- mute exactly one site, then run the suite -------------------------------
# $1=target relpath  $2=lineno  $3=kind
run_one() {
  local rel="$1" lineno="$2" kind="$3" w="$4"
  # Two statements, not one. `local d=X f="$d/$rel"` evaluates the second
  # assignment before `d` has a value, and under `set -u` that is an unbound
  # variable - which killed every single mutation in the first run of this
  # script. See the accounting note below for why that produced 8/8.
  local d="$WORKROOT/w$w"
  local f="$d/$rel"
  local base mut target
  base="$(cat "$f")"

  case "$kind" in
    bad|warn|die) target="${kind} " ;;
    printf)       target="printf" ;;
    *) return 2 ;;
  esac

  mut="$(MUTE_KIND="$kind" MUTE_LINENO="$lineno" MUTE_TEXT="$target" python3 - "$f" <<'PY'
import os, pathlib, sys
p = pathlib.Path(sys.argv[1])
lines = p.read_text().splitlines(keepends=True)
i = int(os.environ["MUTE_LINENO"]) - 1
kind = os.environ["MUTE_KIND"]; text = os.environ["MUTE_TEXT"]
before = sum(1 for L in lines if text in L)
if not (0 <= i < len(lines)) or text not in lines[i]:
    sys.exit(3)                      # window missed -> SKIP
lines[i] = lines[i].replace(text, "_mute " if kind != "printf" else "_mutepr", 1)
after = sum(1 for L in lines if text in L)
if after != before - 1:
    sys.exit(3)                      # mutation did not land -> SKIP
if "_mute " not in "".join(lines) and "_mutepr" not in "".join(lines):
    sys.exit(3)
sys.stdout.write("".join(lines))
PY
)" || { printf 'SKIP-mutation-did-not-land\n'; return 0; }

  # no-op siblings, so silencing one finding is not a crash of the whole script
  if ! grep -q '^_mute()' "$f"; then
    sed -i '51i _mute()   { :; }\n_mutepr() { :; }' "$f"
  fi
  printf '%s' "$mut" > "$f"

  ( cd "$d" && python3 tests/test_retrieval.py ) >/dev/null 2>&1
  local rc=$?
  printf '%s' "$base" > "$f"           # restore
  if [ "$rc" -ne 0 ]; then printf 'RED\n'; else printf 'GREEN\n'; fi
}

# --- collect all sites across all targets ------------------------------------
: > "$RESULTS.tmp"
total=0
for t in "${TARGETS[@]}"; do
  [ -f "$ROOT/$t" ] || { echo "no such target: $t" >&2; exit 1; }
  n=$(find_sites "$ROOT/$t" | wc -l | tr -d ' ')
  echo "$t: $n finding site(s)"
  total=$((total + n))
done
echo

sites_list=()
for t in "${TARGETS[@]}"; do
  while IFS=$'\t' read -r ln kind text; do
    [ -n "$ln" ] && sites_list+=("$t"$'\t'"$ln"$'\t'"$kind"$'\t'"$text")
  done < <(find_sites "$ROOT/$t")
done

rm -rf "$WORKROOT"; mkdir -p "$WORKROOT"
for w in $(seq 0 $((WORKERS - 1))); do build "$w" >/dev/null; done

n=${#sites_list[@]}
echo "mutating $n site(s), $WORKERS workers each with their own tree"
echo

# contiguous chunks: index class must not be the same as directory
chunk_bounds() { echo $(( $1 * n / WORKERS )) $(( ($1 + 1) * n / WORKERS )); }

run_chunk() {
  local w="$1" s e i out=""
  read -r s e < <(chunk_bounds "$w")
  for (( i=s; i<e; i++ )); do
    IFS=$'\t' read -r t ln kind text <<< "${sites_list[$i]}"
    out+="$(printf '%s\t%s\t%s\t%s\t%s\n' "$t" "$ln" "$kind" "$i" "$(run_one "$t" "$ln" "$kind" "$w")")"$'\n'
  done
  printf '%s' "$out"
}

: > "$RESULTS"
for w in $(seq 0 $((WORKERS - 1))); do
  run_chunk "$w" >> "$RESULTS"
done

# --- report ------------------------------------------------------------------
# THE ACCOUNTING IS THE WHOLE POINT, and the first version of this script got
# it wrong in the exact way it exists to catch.
#
# It printed `asserted = n - green - skips`. A mutation that never ran - because
# the harness crashed, or the subshell died - produced an EMPTY status, matched
# neither GREEN nor SKIP, and therefore fell out of both subtractions and was
# counted as **asserted**. Every one of the 8 sites died on an unbound variable,
# the script printed a clean 8/8 with zero false passes, and that number was
# fiction. A coverage claim derived by subtracting the failures from a constant
# cannot distinguish "the test caught it" from "nothing happened".
#
# So the total is now derived from rows that actually reported, and a missing
# row is a hard error rather than a silent pass:
green=0; skips=0; reds=0; missing=0
while IFS=$'\t' read -r t ln kind idx st; do
  [ -z "${t:-}" ] && continue
  if [ -z "${st:-}" ]; then
    missing=$((missing + 1))
    printf '  NO RESULT  %s:%s  %s()  <- the harness did not measure this\n' "$t" "$ln" "$kind"
  elif [[ "$st" == GREEN* ]]; then
    green=$((green + 1))
    printf '  FALSE PASS  %s:%s  %s()\n' "$t" "$ln" "$kind"
  elif [[ "$st" == SKIP* ]]; then
    skips=$((skips + 1))
    printf '  SKIPPED (counts for nothing)  %s:%s  %s()\n' "$t" "$ln" "$kind"
  else
    reds=$((reds + 1))
  fi
done < "$RESULTS"

measured=$((reds + green + skips))

echo
echo "  sites enumerated:  $n"
echo "  sites measured:    $measured"
echo "  asserted (suite goes red when silenced): $reds/$measured"
echo "  false passes:      $green"
echo "  skipped:           $skips"
echo "  no result:         $missing"

if [ "$missing" -gt 0 ]; then
  echo
  echo "  THE HARNESS IS BROKEN. $missing site(s) were never measured, so the"
  echo "  ratio above does not describe the tree. Fix this script before"
  echo "  believing anything it says - an unmeasured site reported as a pass is"
  echo "  the exact false-pass shape this audit exists to detect."
  exit 2
fi
if [ "$skips" -gt 0 ]; then
  echo
  echo "  NOTE: skipped sites are NOT asserted, so the ratio above understates"
  echo "  coverage. A skipped mutation is a mutation that did not happen."
fi
[ "$measured" -ne "$n" ] && { echo "  ERROR: measured $measured of $n sites"; exit 2; }
echo
echo "  full results: $RESULTS"
