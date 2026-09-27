#!/usr/bin/env bash
# sync-rules.sh - check that the two implementations of the risk-tier rules agree.
#
# WHY THIS EXISTS
#
# The safety ceiling and the action vocabulary are implemented twice:
#
#   lib/common.sh          aiorg_safety_ceiling / aiorg_effective_actions
#   tools/check-agents.py  CEILINGS / ACTIONS / effective_actions
#
# Two implementations is a real cost and it is paid on purpose. check-agents.py
# must not shell out to bash just to validate a config, and common.sh must not
# depend on python being installed. But the failure mode is silent and severe: if
# the checker believes `standard` includes `execute` and the harness does not,
# then either check passes a config the harness refuses to run, or - worse - the
# reverse, and a run proceeds with permissions nobody validated.
#
# Nothing else in the tree would notice. So this compares them on every case
# that matters and fails loudly when they diverge.
#
# Run:  ./tools/sync-rules.sh

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"

CHECKER="$AIORG_ROOT/tools/check-agents.py"
fail=0

# Run an expression against check-agents.py, loaded by path (the filename has a
# hyphen, so `import check_agents` cannot work). Importing does not run main().
py() {
  python3 - "$CHECKER" "$@" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ca", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
mode = sys.argv[2]
if mode == "actions":
    print(" ".join(sorted(m.ACTIONS)))
elif mode == "ceiling":
    print(" ".join(sorted(m.CEILINGS[sys.argv[3]])))
elif mode == "rc":
    print(m.effective_actions(sys.argv[3], sys.argv[4])[0])
else:
    raise SystemExit(f"unknown mode {mode}")
PYEOF
}

norm() { tr ',' '\n' | sed '/^$/d' | sort | tr '\n' ' ' | sed 's/ $//'; }
note() { printf '  %s\n' "$1"; }
bad()  { printf '  \033[31m[MISMATCH]\033[0m %s\n' "$1"; fail=1; }

printf '\n\033[1m[==>]\033[0m Checking bash and python agree on the risk tiers\n\n'

# --- 1. the action vocabulary ------------------------------------------------
bash_actions="$(printf '%s\n' $AIORG_ACTIONS | norm)"
py_actions="$(py actions | norm)"
if [ "$bash_actions" = "$py_actions" ]; then
  note "action vocabulary: $bash_actions"
else
  bad "action vocabulary differs"
  note "bash:   $bash_actions"
  note "python: $py_actions"
fi

# --- 2. every ceiling --------------------------------------------------------
for safety in read-only standard full; do
  b="$(aiorg_safety_ceiling "$safety" | norm)"
  p="$(py ceiling "$safety" | norm)"
  if [ "$b" = "$p" ]; then
    note "ceiling $safety: $b"
  else
    bad "ceiling '$safety' differs"
    note "bash:   $b"
    note "python: $p"
  fi
done

# --- 3. accept/reject must agree, including the exit codes --------------------
# The rc values are the interface: test-agent.sh switches on them to choose which
# refusal message to print. A renumbering in one file would make the harness
# report the wrong reason or fall through with no message at all - which is
# exactly the bug that was in there when this script was written.
check_rc() {
  local safety="$1" declared="$2" want="$3" label="$4"
  local brc=0 prc
  aiorg_effective_actions "$safety" "$declared" >/dev/null 2>&1 || brc="$?"
  prc="$(py rc "$safety" "$declared")"
  if [ "$brc" != "$prc" ]; then
    bad "$label: bash rc=$brc but python rc=$prc"
  elif [ "$brc" != "$want" ]; then
    bad "$label: expected rc=$want, both said $brc"
  else
    note "rc=$brc  $label"
  fi
}

check_rc read-only ""                        0 "empty list inherits the ceiling"
check_rc read-only "read"                    0 "exactly the ceiling"
check_rc read-only "read,write"              3 "read-only asking to write"
check_rc read-only "read,bogus"              2 "invented action name"
check_rc standard  "read,write"              0 "standard narrowed to own workspace"
check_rc standard  "read,execute"            3 "standard asking to execute"
check_rc standard  "read,write,write_other"  0 "teacher's actual permission set"
check_rc full      "read,deploy"             0 "full narrowed to deploy only"
check_rc full      ""                        0 "full inherits everything"
check_rc nonsense  ""                        1 "unknown safety level"

echo
if [ "$fail" -ne 0 ]; then
  printf '  \033[31m[fail]\033[0m The two implementations disagree. The checker and the\n'
  printf '         harness must never describe different permissions.\n\n'
  exit 1
fi
printf '  \033[32m[ ok ]\033[0m bash and python agree on every case.\n\n'
