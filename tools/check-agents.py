#!/usr/bin/env python3
"""
check-agents.py - static validation of the agents/ tree.

    ./tools/check-agents.py              # all agents
    ./tools/check-agents.py coder        # one agent
    ./tools/check-agents.py --quiet      # problems only

This catches the mistakes that make a test run lie to you. Every one of these
has actually happened in this project:

  * two cases sharing a name, so --only matched both and the score was
    double-counted
  * a case with empty check columns, which can never fail and so inflates the
    score
  * an agent whose model role resolved to nothing, so testing it silently
    tests the wrong thing
  * a test file still using the old '|' delimiter, silently misparsed
  * an agent naming a runtime that is not in config/runtimes.json, or a
    runtime in the registry with no adapter behind it

Run this before a test sweep. It is much faster than discovering the problem
twenty minutes into a model run.

Standard library only. Exits non-zero if anything is wrong.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"
CATALOG = ROOT / "config" / "models.json"
RESOLVED = ROOT / "config" / "models.env"
RUNTIMES = ROOT / "config" / "runtimes.json"
RUNTIME_LIB = ROOT / "lib" / "runtime.sh"

# Keys every agent.conf must define.
REQUIRED_CONF = [
    "AGENT_NAME",
    "AGENT_TITLE",
    "AGENT_MISSION",
    # AGENT_REPORTS_TO is deliberately NOT in this list. It is required in
    # spirit - the org chart is not optional - but it is allowed to be empty for
    # exactly one agent: the one at the top, which has nobody above it. Keeping
    # it out of REQUIRED_CONF and validating it properly in
    # check_reporting_graph() is better than warning about a missing key and
    # never checking the value.
    "AGENT_MODEL_ROLE",
    "AGENT_RUNTIME",
    "AGENT_SAFETY",
    "AGENT_NETWORK",
    "AGENT_MAX_TURNS",
    "AGENT_MAX_TOKENS",
    "AGENT_TIMEOUT_MIN",
    "AGENT_TEMPERATURE",
    "AGENT_THINK",
    "AGENT_STATUS",
]

VALID_SAFETY = {"read-only", "standard", "full"}
VALID_NETWORK = {"none", "limited", "unrestricted"}
VALID_STATUS = {"building", "ready", "active"}
VALID_THINK = {"on", "off"}

# Keys that must be positive. AGENT_TEMPERATURE is excluded on purpose: 0 means
# greedy decoding, which is what makes test runs reproducible.
POSITIVE_CONF = ("AGENT_MAX_TURNS", "AGENT_MAX_TOKENS", "AGENT_TIMEOUT_MIN")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks = 0

    def error(self, agent: str, msg: str) -> None:
        self.errors.append(f"{agent}: {msg}")

    def warn(self, agent: str, msg: str) -> None:
        self.warnings.append(f"{agent}: {msg}")


def parse_conf(path: Path) -> tuple[dict[str, str], str]:
    """
    Read an agent.conf by letting bash source it.

    These files are bash-sourceable by design - tools/test-agent.sh does exactly
    that. So the authoritative way to read one is with bash, not a regex: bash
    already handles quoting, trailing comments and substitution, and parsing it
    any other way means the validator can disagree with the runtime about what
    an agent's settings are. That disagreement is the exact bug this tool
    exists to prevent.

    Returns (settings, parse_error).

    Note the error check is on stderr, not the exit code: bash reports a syntax
    error while sourcing, prints it, and then carries on to the next command, so
    the overall status is still 0. Trusting the exit code here means a conf
    full of syntax errors validates as "empty but valid".
    """
    proc = subprocess.run(
        ["bash", "-c", 'set -a; . "$1"; env -0', "bash", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.stderr.strip():
        line = proc.stderr.strip().splitlines()[-1]
        return {}, line
    if proc.returncode != 0:
        return {}, f"bash exited {proc.returncode} while sourcing the file"

    conf: dict[str, str] = {}
    for entry in proc.stdout.split("\0"):
        if "=" in entry:
            key, val = entry.split("=", 1)
            conf[key] = val
    return conf, ""


def known_roles() -> set[str]:
    """Model role names from the catalog, falling back to models.env."""
    import json

    if CATALOG.exists():
        try:
            data = json.loads(CATALOG.read_text(encoding="utf-8"))
            roles = set(data.get("roles", {}).keys())
            if roles:
                return roles
        except (json.JSONDecodeError, OSError):
            pass
    if RESOLVED.exists():
        for line in RESOLVED.read_text(encoding="utf-8").splitlines():
            if line.startswith("AI_ROLES="):
                return set(line.split("=", 1)[1].strip().strip('"').split())
    return set()


def known_runtimes() -> set[str]:
    """Runtime ids from the registry. An empty set means 'could not tell'."""
    import json

    if not RUNTIMES.exists():
        return set()
    try:
        data = json.loads(RUNTIMES.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get("runtimes", {}).keys())


def check_runtime_registry(rep: Report) -> set[str]:
    """
    Check the registry itself, and return the ids it declares.

    A runtime in the registry with no adapter behind it is the one failure mode
    that would otherwise show up as a confusing error halfway through a test
    run, so it is an error here rather than a runtime surprise later.
    """
    import json

    if not RUNTIMES.exists():
        rep.error(
            "runtimes",
            f"no runtime registry at {RUNTIMES}. An agent.conf names the "
            f"program that executes it, so this file is what makes that name "
            f"mean anything.",
        )
        return set()

    try:
        data = json.loads(RUNTIMES.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rep.error("runtimes", f"config/runtimes.json is not valid JSON: {exc}")
        return set()
    except OSError as exc:
        rep.error("runtimes", f"config/runtimes.json could not be read: {exc}")
        return set()

    runtimes = data.get("runtimes", {})
    if not isinstance(runtimes, dict) or not runtimes:
        rep.error(
            "runtimes",
            "config/runtimes.json has no 'runtimes' object, so no agent can "
            "be executed",
        )
        return set()

    lib_src = RUNTIME_LIB.read_text(encoding="utf-8") if RUNTIME_LIB.exists() else ""

    for rid, meta in runtimes.items():
        if not lib_src:
            rep.error("runtimes", f"lib/runtime.sh is missing, so runtime '{rid}' has no adapter")
            continue
        for kind in ("probe", "chat"):
            if f"_rt_{rid}_{kind}(" not in lib_src:
                rep.error(
                    "runtimes",
                    f"config/runtimes.json lists runtime '{rid}' but "
                    f"lib/runtime.sh has no _rt_{rid}_{kind} adapter",
                )

        status = (meta or {}).get("status", "")
        if status and status != "ready":
            rep.warn(
                "runtimes",
                f"runtime '{rid}' has status '{status}' - only 'ready' "
                f"runtimes belong in the 'runtimes' object",
            )

    return set(runtimes.keys())


# --- per-action risk tiers ---------------------------------------------------
#
# Kept byte-identical in meaning to aiorg_safety_ceiling /
# aiorg_effective_actions in lib/common.sh. Two implementations is a real cost,
# and it is paid deliberately: check-agents.py must not shell out to bash to
# validate a config, and common.sh must not depend on python. tools/sync-rules.sh
# checks the two agree, because the failure mode - a ceiling that differs between
# the checker and the thing that enforces it - is silent.
ACTIONS = {"read", "write", "write_other", "execute", "network", "config", "deploy"}

CEILINGS = {
    "read-only": {"read"},
    "standard": {"read", "write", "write_other"},
    "full": set(ACTIONS),
}


def safety_ceiling(safety: str) -> str:
    return ",".join(sorted(CEILINGS.get(safety, set())))


def effective_actions(safety: str, declared: str) -> tuple[int, str]:
    """Return (rc, detail). rc: 0 ok, 1 unknown safety, 2 unknown action,
    3 action above the ceiling."""
    if safety not in CEILINGS:
        return 1, "unknown safety level"
    if not declared.strip():
        return 0, safety_ceiling(safety)
    allowed = CEILINGS[safety]
    for raw in declared.split(","):
        action = raw.strip()
        if not action:
            continue
        if action not in ACTIONS:
            return 2, action
        if action not in allowed:
            return 3, action
    return 0, ""


def check_no_hardcoded_loopback(rep: Report) -> None:
    """No script may name the model server by hand.

    This is the third time the same defect class has appeared: a place that talks
    to Ollama hardcoding 127.0.0.1, or reading the AI_OLLAMA_URL literal baked
    into the generated profile. Both look correct in the single-machine case and
    both silently address the wrong machine the moment the GPU is on another
    box - which is the documented setup, and the reason the override exists.

    The rule: scripts/lib source lib/common.sh and ask it. A grep cannot tell a
    legitimate loopback (a health check from inside a container, a bind address)
    from a wrong one, so this is deliberately narrow - it flags only a hardcoded
    127.0.0.1 in a curl or an AI_OLLAMA_URL read, which is never legitimate.
    """
    import re

    # (pattern, is_comment) - comments are allowed to explain the bug.
    suspect = re.compile(
        r"curl[^\n]*127\.0\.0\.1|\$\{?AI_OLLAMA_URL|\$AI_OLLAMA_URL"
    )
    root = Path(__file__).resolve().parent.parent
    # Built with extend, not a ternary. `sorted(a + b + c if cond else [])` binds
    # the condition to the whole sum, so a missing bootstrap.sh silently yields
    # an empty list and the guard passes everything. Caught by pointing the
    # guard at a fixture tree that had no bootstrap.sh.
    targets: list[Path] = []
    targets.extend((root / "scripts").glob("*.sh"))
    targets.extend((root / "lib").glob("*.sh"))
    if (root / "bootstrap.sh").exists():
        targets.append(root / "bootstrap.sh")
    targets.sort()
    for path in targets:
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if suspect.search(line):
                rel = path.relative_to(root)
                rep.warn(
                    "-",
                    f"{rel}:{lineno} names the model server directly instead of "
                    f"aiorg_ollama_url() / aiorg_ollama_target(). Use the helper.",
                )


def check_cases(agent: str, path: Path, rep: Report) -> int:
    """Validate one cases.tsv. Returns the number of real cases."""
    names: set[str] = set()
    count = 0

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        rep.checks += 1

        if ":::" not in raw:
            # Almost always one of two mistakes, and the generic message used to
            # point at neither. Say which, because this trap is easy to fall into:
            # a long case gets wrapped by habit and the must_not lands on its own
            # line, where it is read as a case and silently ignored.
            if "," in raw or "||" in raw:
                rep.error(
                    agent,
                    f"tests/cases.tsv:{lineno} looks like a check column that was "
                    f"put on its own line. must and must_not belong on the SAME "
                    f"line as the case name and prompt - a second line is parsed "
                    f"as a case with no ':::' separator. Fold it back up.",
                )
            else:
                rep.error(
                    agent,
                    f"tests/cases.tsv:{lineno} uses '|' or no separator. The format "
                    f"is 'name ::: prompt ::: must ::: must_not'",
                )
            continue

        parts = [p.strip() for p in raw.split(":::")]

        if len(parts) < 2:
            rep.error(agent, f"tests/cases.tsv:{lineno} has no prompt column")
            continue

        name = parts[0]
        if not name:
            rep.error(agent, f"tests/cases.tsv:{lineno} has an empty case name")
            continue

        if not parts[1]:
            rep.error(agent, f"tests/cases.tsv:{lineno} '{name}' has an empty prompt")
            continue

        must = parts[2] if len(parts) > 2 else ""
        mustnot = parts[3] if len(parts) > 3 else ""
        if not must and not mustnot:
            rep.error(
                agent,
                f"tests/cases.tsv:{lineno} '{name}' has no checks at all, so it "
                f"can never fail and only inflates the score",
            )
            continue

        if name in names:
            rep.error(
                agent,
                f"tests/cases.tsv:{lineno} duplicate case name '{name}' - --only "
                f"would match both and the score would double-count",
            )
        names.add(name)

        if len(parts) > 4:
            rep.warn(
                agent,
                f"tests/cases.tsv:{lineno} '{name}' has {len(parts)} columns; "
                f"only the first four are read",
            )

        count += 1

        _check_case_satisfiable(agent, lineno, name, must, mustnot, rep)

    if count == 0:
        rep.error(agent, "tests/cases.tsv contains no usable test cases")

    return count


def _check_case_satisfiable(
    agent: str, lineno: int, name: str, must: str, mustnot: str, rep: Report
) -> None:
    """Fail a case whose must and must_not cannot both be satisfied.

    test-agent.sh matches case-insensitively and by substring. So a case is
    unsatisfiable when a BANNED string is itself a substring of a REQUIRED one:
    any reply containing the required string has therefore already contained the
    banned string. Required-inside-banned is fine and happens constantly - a
    case may require the word "deploy" while banning the phrase "i have granted
    deploy", because a refusal that says "I refuse to grant deploy" contains the
    first and not the second. Getting this backwards produced five false
    positives against cto on the first run, which is the check's own version of
    the lesson this file keeps learning.

    Three cases in this tree were built the bad way before the check existed:
    `cto no-write-claim` demanded the word "applied" in a `||` group while
    must_not banned "applied". The fix was to make the replacement must_not
    values affirmative first-person claims ("i have applied") rather than the
    bare verb, because banning "applied the change" would also ban the correct
    refusal *"I have not applied the change"* - which is the exact failure the
    case exists to catch. That reasoning is worth keeping; the mistake is worth
    catching mechanically.

    Reported per must_contain GROUP, not per case, because must_contain is
    "any one complete group passes". A case is only unsatisfiable when *every*
    group is poisoned - one clean group is a way for the case to pass. This
    mirrors check_field() in test-agent.sh exactly, because a satisfiability
    check that disagrees with the matcher is worse than none.
    """
    if not must or not mustnot:
        return

    banned = [i.strip().lower() for i in mustnot.replace("||", ",").split(",")]
    banned = [b for b in banned if b]
    if not banned:
        return

    groups = [g.strip() for g in must.split("||") if g.strip()]
    if not groups:
        return

    def clashes(item: str) -> bool:
        """True if a banned string sits inside this required string."""
        return any(b in item for b in banned)

    clean = []
    poisoned = []
    for g in groups:
        items = [i.strip().lower() for i in g.split(",") if i.strip()]
        hits = sorted({i for i in items if clashes(i)})
        (poisoned if hits else clean).append((g, hits))

    if clean or not poisoned:
        return

    detail = "; ".join(
        f"group {i + 1} ({g!r}) requires {hits}" for i, (g, hits) in enumerate(poisoned)
    )
    offender = poisoned[0][1][0]
    # `inside` cannot be empty while `hits` is non-empty, because hits is
    # computed with the same test as clashes(). The fallback is belt and
    # braces: this runs over a file the author wrote by hand, and a checker
    # that raises IndexError on one malformed line is worse than no checker,
    # because it takes the whole tree down instead of reporting the one line.
    inside = [b for b in banned if b in offender] or banned[:1]
    rep.error(
        agent,
        f"tests/cases.tsv:{lineno} '{name}' can never pass. Every must_contain "
        f"group collides with must_not_contain: {detail}. Matching is "
        f"case-insensitive substring, so a reply satisfying must_contain has "
        f"already broken must_not_contain - the banned {inside[0]!r} sits inside "
        f"the required {offender!r}. Leave one must_contain group with no "
        f"collision, or reword the banned string so a correct reply can satisfy "
        f"both.",
    )


def check_agent(d: Path, rep: Report, roles: set[str], runtimes: set[str]) -> int:
    agent = d.name

    conf_path = d / "agent.conf"
    soul_path = d / "SOUL.md"
    cases_path = d / "tests" / "cases.tsv"
    skills_dir = d / "skills"

    if not conf_path.exists():
        rep.error(agent, "no agent.conf")
        return 0
    if not soul_path.exists():
        rep.error(agent, "no SOUL.md")
    if not cases_path.exists():
        rep.error(agent, "no tests/cases.tsv")
        return 0
    if not skills_dir.is_dir():
        rep.error(agent, "no skills/ directory")

    # --- agent.conf ---
    conf, parse_error = parse_conf(conf_path)
    if parse_error:
        rep.error(agent, f"agent.conf will not parse as bash: {parse_error}")
        return 0

    for key in REQUIRED_CONF:
        if key not in conf:
            rep.warn(agent, f"agent.conf is missing {key}")

    if conf.get("AGENT_NAME") and conf["AGENT_NAME"] != agent:
        rep.error(
            agent,
            f"AGENT_NAME is '{conf['AGENT_NAME']}' but the directory is '{agent}'",
        )

    safety = conf.get("AGENT_SAFETY", "")
    if safety and safety not in VALID_SAFETY:
        rep.error(agent, f"AGENT_SAFETY='{safety}' is not one of {sorted(VALID_SAFETY)}")

    # --- per-action risk tiers ---
    # An action above the agent's own safety ceiling is an error, not a warning.
    # A ceiling that its own config file can widen is not a ceiling.
    if safety:
        declared = conf.get("AGENT_ACTIONS", "").strip()
        rc, detail = effective_actions(safety, declared)
        if rc == 1:
            rep.error(agent, f"AGENT_SAFETY='{safety}' has no known ceiling")
        elif rc == 2:
            bad = [a for a in declared.split(",") if a.strip() and a.strip() not in ACTIONS]
            rep.error(
                agent,
                f"AGENT_ACTIONS names {bad}, which is not an action. "
                f"Valid: {sorted(ACTIONS)}",
            )
        elif rc == 3:
            allowed = set(safety_ceiling(safety).split(","))
            over = [a.strip() for a in declared.split(",") if a.strip() and a.strip() not in allowed]
            rep.error(
                agent,
                f"AGENT_SAFETY allows {sorted(allowed)} but AGENT_ACTIONS asks for "
                f"{over}. AGENT_ACTIONS may only narrow AGENT_SAFETY, never widen it.",
            )

    network = conf.get("AGENT_NETWORK", "")
    if network and network not in VALID_NETWORK:
        rep.error(agent, f"AGENT_NETWORK='{network}' is not one of {sorted(VALID_NETWORK)}")

    # --- open-book declaration ---
    # Records that this agent is meant to be run WITH retrieved sources. It is a
    # declaration about how the agent is used, not a switch: the test harness
    # never retrieves, so an on here does not make a test open-book. That
    # separation is the point - a test case needs one right answer that does not
    # change between Tuesday and Thursday, or the score measures the index
    # rather than the agent.
    retrieval = conf.get("AGENT_RETRIEVAL", "").strip()
    if retrieval and retrieval not in ("on", "off"):
        rep.error(agent, f"AGENT_RETRIEVAL='{retrieval}' must be 'on' or 'off'")

    status = conf.get("AGENT_STATUS", "")
    if status and status not in VALID_STATUS:
        rep.error(agent, f"AGENT_STATUS='{status}' is not one of {sorted(VALID_STATUS)}")

    think = conf.get("AGENT_THINK", "")
    if think and think not in VALID_THINK:
        rep.error(agent, f"AGENT_THINK='{think}' is not one of {sorted(VALID_THINK)}")

    for key in POSITIVE_CONF:
        val = conf.get(key, "")
        if not val:
            continue
        try:
            num = float(val)
        except ValueError:
            rep.error(agent, f"{key}='{val}' is not a number")
            continue
        if num <= 0:
            rep.error(agent, f"{key}='{val}' must be greater than zero")

    temp = conf.get("AGENT_TEMPERATURE", "")
    if temp:
        try:
            if float(temp) < 0:
                rep.error(agent, f"AGENT_TEMPERATURE='{temp}' cannot be negative")
        except ValueError:
            rep.error(agent, f"AGENT_TEMPERATURE='{temp}' is not a number")

    role = conf.get("AGENT_MODEL_ROLE", "")
    if role and roles and role not in roles:
        rep.error(
            agent,
            f"AGENT_MODEL_ROLE='{role}' is not a role in config/models.json. "
            f"Known roles: {', '.join(sorted(roles))}",
        )

    if role and role.upper() + "_MODEL" in conf:
        rep.error(
            agent,
            f"AGENT_MODEL_ROLE should be the role name ('{role}'), not the "
            f"resolved variable name '{role.upper()}_MODEL'",
        )

    runtime = conf.get("AGENT_RUNTIME", "")
    if runtime and runtimes and runtime not in runtimes:
        rep.error(
            agent,
            f"AGENT_RUNTIME='{runtime}' is not a runtime in config/runtimes.json. "
            f"Known runtimes: {', '.join(sorted(runtimes))}. An agent naming a "
            f"runtime that does not exist cannot be tested, and silently falling "
            f"back to a different one would make the score a lie",
        )

    if role and runtime and conf.get("AGENT_RUNTIME", "") == "ollama" and not RESOLVED.exists():
        rep.warn(
            agent,
            "uses the ollama runtime but config/models.env does not exist yet - "
            "run ./bootstrap.sh detect",
        )

    if status == "ready" and conf.get("AGENT_LAST_SCORE", "never") in ("never", ""):
        rep.error(
            agent,
            "AGENT_STATUS is 'ready' but AGENT_LAST_SCORE was never set - an "
            "agent should not be marked ready before its tests have run",
        )

    # --- SOUL.md ---
    if soul_path.exists():
        words = len(soul_path.read_text(encoding="utf-8").split())
        if words < 60:
            rep.warn(agent, f"SOUL.md is only {words} words - that is very little to work with")
        elif words > 1400:
            rep.warn(
                agent,
                f"SOUL.md is {words} words. Small models follow the beginning and "
                f"the end best, so the middle is where rules go to die",
            )

    # --- skills ---
    if skills_dir.is_dir():
        skills = [p for p in skills_dir.glob("*.md") if p.name != "README.md"]
        if not skills:
            rep.warn(agent, "skills/ has no skills yet")

    return check_cases(agent, cases_path, rep)


def check_reporting_graph(dirs: list[Path], rep: Report) -> None:
    """Validate the org chart itself, which needs every agent at once.

    Until now AGENT_REPORTS_TO was checked for presence and never for value, so
    five agents could report to a `ceo` that does not exist and the tree passed.
    That is the same failure as everything else this project has learned the hard
    way: a structural invariant that was assumed rather than checked. A typo in a
    manager's name would have been equally invisible, and a reporting cycle
    between two agents would have made delegation a loop with nobody at the top.

    Checked here, over the whole tree, rather than per agent, because the
    interesting failures are all about the graph rather than about one file.
    """
    parent: dict[str, str] = {}
    for d in dirs:
        conf_path = d / "agent.conf"
        if not conf_path.is_file():
            continue
        conf, err = parse_conf(conf_path)
        if err:
            continue                       # already reported by check_agent
        parent[d.name] = conf.get("AGENT_REPORTS_TO", "").strip()

    known = set(parent)

    # a parent must be a real agent
    orphans = sorted(f"{a} -> {p!r}" for a, p in parent.items() if p and p not in known)
    for o in orphans:
        agent, _, p = o.partition(" -> ")
        p = p.strip("'\"")
        if p == "human":
            continue                       # an explicit non-agent parent
        rep.error(
            agent,
            f"AGENT_REPORTS_TO='{p}' but there is no agent called '{p}'. "
            f"Either build it, or point at one that exists. Known agents: "
            f"{', '.join(sorted(known))}",
        )

    # exactly one agent may sit at the top with no parent
    roots = sorted(a for a, p in parent.items() if not p)
    if len(roots) > 1:
        rep.error(
            "org",
            f"more than one agent has no AGENT_REPORTS_TO (the top of the org "
            f"must be unique): {', '.join(roots)}",
        )

    # A cycle means nobody is at the top and delegation loops forever.
    #
    # Reported once per distinct cycle, not once per agent that flows into one.
    # The first version of this printed the same finding for all thirteen
    # agents, which is technically true and practically useless: a checker that
    # shouts thirteen identical lines trains people to skim past it, and the
    # one real mistake is buried in the noise.
    reported: set[frozenset[str]] = set()
    for start in sorted(parent):
        path: list[str] = []
        index: dict[str, int] = {}
        cur = start
        while cur in parent and parent[cur]:
            if cur in index:
                cycle = path[index[cur]:]
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    shown = " -> ".join(cycle + [cycle[0]])
                    rep.error(
                        "org",
                        f"reporting cycle: {shown}. There is no one to escalate "
                        f"to, and it affects {len(cycle)} agent(s): "
                        f"{', '.join(sorted(cycle))}.",
                    )
                break
            index[cur] = len(path)
            path.append(cur)
            nxt = parent[cur]
            if nxt not in parent:
                break                       # already reported as an orphan
            cur = nxt

    # a chain nobody terminates is an org chart with a missing link
    if roots:
        unreachable = sorted(
            a for a in parent
            if a not in roots and _chain_root(a, parent) not in roots
        )
        for a in unreachable:
            rep.error(a, f"does not lead to the top of the org (root: {', '.join(roots)})")


def _model_family(tag: str) -> str:
    """The model family a tag belongs to: the repo, i.e. what precedes the tag.

    `deepseek-r1:70b` and `deepseek-r1:32b` are two sizes of one recipe, one
    trained by one lab on one corpus. Treating them as two independent judges is
    the monoculture wearing a different hat, and the tag comparison cannot see
    it because the tags differ.

    Ollama references are `repo:tag`, so the family is everything before the
    FIRST colon. A bare name with no colon is its own family, which is the right
    default: two distinct bare names are not evidence of a shared recipe, and
    guessing a relationship the catalog does not state would be worse than
    staying quiet. An empty result means the reference is malformed (`:8b`), and
    callers treat that as "no family" rather than as a match.
    """
    repo, sep, _ = tag.partition(":")
    return repo.strip() if sep else tag.strip()


def _independence_claims(dirs: list[Path]) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """agent name -> model role, and every declared (agent, other) pair."""
    roles: dict[str, str] = {}
    claims: list[tuple[str, str]] = []
    for d in dirs:
        conf_path = d / "agent.conf"
        if not conf_path.is_file():
            continue
        conf, err = parse_conf(conf_path)
        if err:
            continue
        roles[d.name] = conf.get("AGENT_MODEL_ROLE", "").strip()
        for other in conf.get("AGENT_INDEPENDENT_OF", "").split():
            claims.append((d.name, other))
    return roles, claims


def _tier_sampler(rep: Report) -> dict | None:
    """Everything needed to ask "what would this role pick on a card that size?".

    Two checks need this - independence across tiers, and whether the resolved
    model can think - and this project's own hard-won rule is that a rule
    implemented twice is a rule that will drift. It has now been implemented
    twice here (three ways to name the model server, four hand-rolled copies of
    the role-to-shell-variable rule, two timeout unit conventions), so this
    exists to delete the second copy rather than add a third. Returns None after
    warning, if the resolver or catalog cannot be read.

    Fit logic is imported from tools/resolve_models.py and the headroom ratio
    from lib/hwdetect.py rather than reimplemented here, for the same reason: a
    second copy of a constant is a second thing that can be wrong.
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "aiorg_resolve_models", ROOT / "tools" / "resolve_models.py")
        resolver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(resolver)
    except Exception as exc:                       # noqa: BLE001
        rep.warn(
            "models",
            f"could not load tools/resolve_models.py ({exc}), so model "
            f"independence across hardware tiers was NOT checked",
        )
        return None

    try:
        import json

        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        rep.warn("models", f"could not read {CATALOG.name} ({exc})")
        return None

    role_specs = catalog.get("roles", {})
    fit = catalog.get("fit", {"comfortable_max": 0.75, "tight_max": 0.92})
    tight = float(fit.get("tight_max", 0.92))

    # Every distinct candidate size is a breakpoint of the resolution function.
    #
    # The breakpoint is vram_gb / tight_max, NOT vram_gb. A candidate is
    # eligible when vram_gb / usable <= tight_max, so it first becomes eligible
    # at usable = vram_gb / tight_max - which with the catalog's 0.92 margin is
    # ABOVE its own vram_gb. Sampling at vram_gb instead therefore probes
    # strictly below every real transition, where a candidate that is about to
    # become eligible is still excluded and the resolver reports a smaller model
    # than it really would. That silently misses collisions: a role pair that
    # converges at 21.7GB usable reads as non-converging when sampled at 20GB.
    # The first version of the independence check had exactly that bug and the
    # regression test in tests/test_retrieval.py is what caught it.
    if tight <= 0:
        rep.warn("models", f"fit.tight_max is {tight}, which cannot be used to "
                           f"compute hardware tiers")
        return None
    tiers = sorted({float(c["vram_gb"]) / tight
                    for spec_ in role_specs.values()
                    for c in spec_.get("candidates", [])})
    if not tiers:
        return None

    def resolved(role: str, usable: float) -> str | None:
        spec_ = role_specs.get(role)
        if spec_ is None:
            return None
        got = resolver.resolve_role(role, spec_, usable, fit)
        return got["model"] if got else None

    def candidate(role: str, usable: float) -> dict | None:
        """The whole winning candidate, not just its name - `thinks` lives on it."""
        spec_ = role_specs.get(role)
        if spec_ is None:
            return None
        return resolver.resolve_role(role, spec_, usable, fit)

    try:
        spec2 = importlib.util.spec_from_file_location(
            "aiorg_hwdetect", ROOT / "lib" / "hwdetect.py")
        hwdetect = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(hwdetect)
        headroom = float(hwdetect.HEADROOM_RATIO)
    except Exception:                              # noqa: BLE001
        headroom = 0.0

    def card_gb(usable: float) -> str:
        """A card size, because that is the number people buy.

        The breakpoints are usable-VRAM figures, and 'collides at 11GB usable'
        makes someone do the arithmetic to work out that it means their 16GB
        card. The ratio comes from lib/hwdetect.py rather than a local literal,
        for the same reason the fit rule is imported: a second copy of a
        constant is a second thing that can be wrong.
        """
        if headroom <= 0:
            return f"{usable:.1f}GB usable"
        return f"{usable:.1f}GB usable (~{usable / headroom:.0f}GB card)"

    return {
        "role_specs": role_specs,
        "fit": fit,
        "tiers": tiers,
        "resolved": resolved,
        "candidate": candidate,
        "card_gb": card_gb,
    }


def check_think_matches_model(dirs: list[Path], rep: Report) -> None:
    """AGENT_THINK must be true of the model that will actually run.

    Ollama 0.33.3 answers a `think:true` request sent to a model with no
    reasoning channel with a hard error, not a shrug. Verified on this box
    against a non-thinking model:

        think=true  -> ERROR: "qwen2.5:0.5b" does not support thinking
        think=false -> ok

    And `lib/runtime.sh` (`_rt_ollama_json`) sends the flag unconditionally, so
    there is nothing in the request that adapts. An agent declaring
    `AGENT_THINK="on"` whose role resolves to an instruct model therefore fails
    every single run - with a runtime error rather than a bad score, which is
    the one failure mode the harness cannot misread.

    This was not hypothetical. Eight of the fifteen agents declared
    `AGENT_THINK="on"` while their role resolved to a non-thinking model on
    small cards: `reasoning` picks llama3.1:8b at 8GB, gemma3:12b at 12GB and
    phi4:14b at 14GB, and `coding` picks qwen2.5-coder:7b - all instruct models.
    The low-VRAM candidates added on 2026-09-26 to break the independence
    monoculture are what exposed it. Nothing caught it: the tier check only
    compared resolved models for equality, and a crash is not a collision.

    Capability is read from the candidate's own `thinks` field, which is
    omitted where it has not been verified. Unverified is treated as unknown and
    stays silent, which is the safe asymmetry: claiming `thinks:false` wrongly
    costs a thinking model its deliberation, while claiming `thinks:true` wrongly
    breaks every run. So this check only fires on a positive claim of
    non-thinking, and `tools/check-models-exist.sh` is what turns the unknowns
    into facts by asking a running Ollama what each model can do.
    """
    sampler = _tier_sampler(rep)
    if sampler is None:
        return
    tiers, candidate, card_gb = sampler["tiers"], sampler["candidate"], sampler["card_gb"]

    # One aggregated warning, not one per agent. Every affected agent needs the
    # same decision from the operator - either accept think=off at the small
    # end, or put thinking models in the low rungs - so 8 separate complaints
    # would be 8 copies of one thing, and a check that cries wolf on a healthy
    # tree is a check people learn to skim. This project has fixed that once
    # already (a blanket independence rule that fired eight times).
    affected: list[str] = []
    unknown: list[str] = []
    for d in sorted(dirs):
        conf_path = d / "agent.conf"
        if not conf_path.is_file():
            continue
        conf, err = parse_conf(conf_path)
        if err:
            continue
        role = conf.get("AGENT_MODEL_ROLE", "").strip()
        if not role or conf.get("AGENT_THINK", "off").strip().lower() not in (
                "on", "true", "1", "yes"):
            continue
        broke: set[str] = set()
        unrecorded: set[str] = set()
        for usable in tiers:
            cand = candidate(role, usable)
            if not cand:
                continue
            if cand.get("thinks") is False:
                broke.add(f"{cand['model']} ({card_gb(usable)})")
            elif "thinks" not in cand:
                # Every tier, not just the largest. devstral:24b is the 24GB
                # design-target model for `coder` and it is unrecorded, and
                # sampling only the top tier would report the 80GB candidate
                # instead and let the one that matters pass unmentioned.
                unrecorded.add(f"{cand['model']} ({card_gb(usable)})")
        if broke:
            affected.append(f"{d.name} (role '{role}') -> " + ", ".join(sorted(broke)))
        if unrecorded:
            unknown.append(f"{d.name} -> " + ", ".join(sorted(unrecorded)))

    if affected:
        rep.warn(
            "models",
            f"{len(affected)} agent(s) ask for thinking but their role picks a "
            f"model with no thinking channel on a smaller card. This is NOT a "
            f"broken run any more - aiorg_effective_think downgrades think=on to "
            f"think=off for those tiers, because Ollama rejects think:true "
            f"outright and a lost deliberation beats a failed run. It does mean "
            f"those agents think on a big card and do not on a small one: "
            + "; ".join(affected)
            + ". Either accept that, or add thinking candidates to the low rungs "
            "of those roles.",
        )
    if unknown:
        rep.warn(
            "models",
            f"thinking capability is not recorded for {', '.join(sorted(set(unknown)))}. "
            f"Unrecorded is treated as 'cannot think', so those tiers run "
            f"think=off. Confirm with tools/check-models.sh, which asks a "
            f"running Ollama what each model can actually do.",
        )


def check_last_score_is_backed(dirs: list[Path], rep: Report) -> None:
    """AGENT_LAST_SCORE is a claim; state/audit.log is the record.

    `AGENT_LAST_SCORE` is a hand-editable line in `agent.conf`, which is the
    point - it is the number a human reads. It is also, for exactly that reason,
    the easiest number in the project to write by hand, and this project has
    already had a fake 100% sit in that field. The audit log exists because it
    also records the runtime and the model that produced the number, so a score
    there can be traced and one in `agent.conf` cannot.

    Nothing compared them. `check-agents.py` already failed an agent that was
    marked `ready` with a score of `never`, which catches the honest beginner -
    it does not catch the number somebody typed in to look finished.

    Three claims are rejected:

    - not a number, or outside 0-100. `AGENT_LAST_SCORE="great"` is not a
      score, and a `pct` outside 0-100 means the harness computed something
      wrong upstream.
    - a number for an agent with no scored run in the log. There is no run
      behind it, so it was not measured.
    - a number higher than any percentage the log has ever recorded for that
      agent. A score may fall - a prompt edit or a model change can cost cases -
      so a lower claim is suspicious but not a lie, and only inflation is an
      error. This is the one that catches an optimistic edit.

    Runs with no `pct` at all (a failed probe) are ignored, and a `verdict=pass`
    computed from a handful of cases is called out as a warning rather than an
    error: the log really did record it, but "100% of 1 case" is not a score,
    and the log line next to it is the honest version of that number.
    """
    audit = ROOT / "state" / "audit.log"
    scored: dict[str, list[tuple[float, float]]] = {}   # agent -> [(pct, cases)]
    if audit.is_file():
        for line in audit.read_text(encoding="utf-8", errors="replace").splitlines():
            fields = dict(
                (m.group(1), m.group(2))
                for m in re.finditer(r"(\w+)=([^\s]+)", line)
            )
            name, pct = fields.get("agent"), fields.get("pct")
            if not name or pct is None:
                continue
            try:
                value = float(pct)
            except ValueError:
                continue
            try:
                cases = float(fields.get("cases", "0") or 0)
            except ValueError:
                cases = 0.0
            scored.setdefault(name, []).append((value, cases))

    for d in sorted(dirs):
        conf_path = d / "agent.conf"
        if not conf_path.is_file():
            continue
        conf, err = parse_conf(conf_path)
        if err:
            continue
        raw = conf.get("AGENT_LAST_SCORE", "never").strip()
        if raw in ("", "never"):
            continue
        try:
            claimed = float(raw.rstrip("%"))
        except ValueError:
            rep.error(
                d.name,
                f"AGENT_LAST_SCORE='{raw}' is not a number. Use a 0-100 "
                f"percentage, or 'never' if the tests have not run. The value "
                f"is a claim a human reads; state/audit.log is the record that "
                f"backs it.",
            )
            continue
        if not 0 <= claimed <= 100:
            rep.error(
                d.name,
                f"AGENT_LAST_SCORE={claimed} is outside 0-100. A score is a "
                f"percentage of cases passed.",
            )
            continue
        history = scored.get(d.name, [])
        if not history:
            rep.error(
                d.name,
                f"AGENT_LAST_SCORE={claimed} but state/audit.log has no scored "
                f"run for this agent, so nothing produced that number. Run "
                f"./tools/test-agent.sh {d.name}, or set it to 'never'.",
            )
            continue
        best = max(pct for pct, _ in history)
        if claimed > best:
            rep.error(
                d.name,
                f"AGENT_LAST_SCORE={claimed} is higher than any score this agent "
                f"has ever recorded (best {best:g}% in state/audit.log). A score "
                f"can fall when a prompt or a model changes, so a lower number is "
                f"not automatically wrong - but a higher one is not something the "
                f"log can support.",
            )
            continue
        # Backed by the log, but was it backed by the whole suite? A pass line
        # records how many cases ran, and "100% of 1 case, 20 skipped" is a
        # number that will be quoted as a score.
        for pct, cases in history:
            if pct == claimed and 0 < cases < 5:
                rep.warn(
                    d.name,
                    f"AGENT_LAST_SCORE={claimed:g} is backed by a run of "
                    f"{cases:g} case(s). The log line has the full picture; this "
                    f"field will be read without it.",
                )
                break


def check_independent_models(dirs: list[Path], rep: Report) -> None:
    """An agent that must disagree with another must not run its weights.

    The 24GB card resolves `reasoning` to gpt-oss:20b, and every role that
    wants judgement resolves to the same model - so 11 of 14 agents, including
    the auditor, the audited and the arbitrator. Three instances of one model
    agreeing is not a second opinion, and the org's central safety argument
    (security audits what the technical department hands out; the CEO
    arbitrates) rests on those three disagreeing when they should.

    A blanket "parent and child must differ" rule was the first attempt and it
    is wrong: 8 of the 14 agents share a role with the agent they report to,
    including all four research specialists under the research officer, where
    sharing a model is exactly what you want. A checker that fires eight times
    on a healthy tree is a checker people learn to skim, which this project has
    already had to fix once.

    So this is opt-in and narrow. `AGENT_INDEPENDENT_OF` names the agents a
    given agent has to be independent of; absent or empty means no requirement.
    As of 2026-09-26 three agents set it: `security-engineer` (vs `cto`), `ceo`
    (vs `cto` and `research-officer`), and `research-officer` (vs its four
    specialists). An empty value is not a declaration - `storyteller` carries an
    empty one and is unconstrained, which is correct, since nobody audits
    fiction. An error, not a warning: the agent has explicitly declared a
    constraint, so breaking it is a contradiction in the config rather than a
    matter of taste.
    """
    roles, claims = _independence_claims(dirs)

    for agent, other in claims:
        if other not in roles:
            rep.error(
                agent,
                f"AGENT_INDEPENDENT_OF names '{other}', which is not an agent. "
                f"Known agents: {', '.join(sorted(roles))}",
            )
            continue
        if agent not in roles:
            continue
        if roles[agent] == roles[other]:
            rep.error(
                agent,
                f"AGENT_INDEPENDENT_OF='{other}' but both are on model role "
                f"'{roles[agent]}'. They would run identical weights, so their "
                f"agreement would be one opinion counted twice, not the "
                f"disagreement this agent exists to provide. Give one of them a "
                f"different role in config/models.json.",
            )


def check_independence_survives_resolution(dirs: list[Path], rep: Report) -> None:
    """Declared model-independence must survive resolution, not just the role names.

    `check_independent_models` above compares ROLE NAMES, because comparing
    resolved models would misfire everywhere: on a machine with no GPU the 8GB
    fallback collapses every role onto one model, so the check would be red for
    a reason that is documented and unavoidable. Roles were the right proxy for
    "did the author make a mistake in the config".

    They are the wrong proxy for "will these two actually run different weights
    on the card this person buys". A role is a list of candidates and the
    resolver takes the largest that fits, so two disjoint role lists can still
    converge on the same model at a given size. The auditor role is exactly
    that case:

                total VRAM   reasoning        adversarial-review
        16GB         phi4:14b         qwen3:14b     <- different (fixed 2026-09-26)
        24GB         gpt-oss:20b      qwen3:14b     <- different (design target)
        32GB         qwen3:32b        qwen3:32b     <- identical (still open)

    16GB used to read `qwen3:14b` on both sides and was fixed by giving
    `reasoning` a second model family below 20GB. 32GB is the remaining trap:
    it looks like a straight upgrade, it is what anyone buys next, and it
    silently turns the auditor into a second copy of the CTO. It cannot be
    fixed by adding a candidate without moving the 24GB design target - see
    AGENTS.md for that arithmetic. It failed the same way it did at 16GB:
  `check_independent_models` passed it,
    because `adversarial-review` and `reasoning` really are different role
    names. That is a green check over a safety guarantee that does not hold.

    So this check resolves the pair at every tier the catalog can produce, which
    needs no GPU and no guess about what hardware is coming: resolution is a step
    function whose breakpoints are exactly the candidates' own vram_gb values,
    so testing each distinct size covers every distinct outcome. The whole
    catalog is ~15 candidate sizes, so this is microseconds.

    Fit logic is imported from tools/resolve_models.py rather than reimplemented.
    That is the point: a second copy of the fit rule is a second thing that can
    disagree with the resolver, and this project has now been bitten by exactly
    that shape five times (three ways to name the model server, four copies of
    the role-to-shell-variable rule, two timeout unit conventions, a blanket
    independence rule that fired eight times on a healthy tree).
    """
    sampler = _tier_sampler(rep)
    if sampler is None:
        return
    tiers = sampler["tiers"]
    card_gb = sampler["card_gb"]
    resolved = sampler["resolved"]

    role_of, claims = _independence_claims(dirs)

    for agent, other in claims:
        if agent not in role_of or other not in role_of:
            continue                               # reported elsewhere
        ra, rb = role_of[agent], role_of[other]
        if ra == rb:
            continue                               # reported by the role check
        # One entry per colliding model, listing every tier it collides at, so
        # a catalog with three bad tiers produces one error naming all three
        # rather than three near-identical errors.
        #
        # The family comparison below is folded into this same walk rather than
        # written as a second one. Two walks over the same tiers is two things
        # that can disagree, and this project has collected five separate
        # incidents of exactly that shape - three ways to name the model server,
        # four copies of the role-to-shell-variable rule, two timeout unit
        # conventions, a blanket independence rule that fired eight times, and
        # one phantom model that four different probes all described
        # differently. One walk, two comparisons.
        collisions: dict[str, list[float]] = {}
        families: dict[tuple[str, str, str], list[float]] = {}
        for usable in tiers:
            ma, mb = resolved(ra, usable), resolved(rb, usable)
            if not (ma and mb):
                continue
            if ma == mb:
                collisions.setdefault(ma, []).append(usable)
                continue
            # Different tags, same family. `continue` above is load-bearing: a
            # tag collision is already an error above, and reporting it a second
            # time as a family overlap would be two findings for one fault.
            fa, fb = _model_family(ma), _model_family(mb)
            if fa and fa == fb:
                families.setdefault((fa, ma, mb), []).append(usable)
        for model, sizes in sorted(collisions.items()):
            where = ", ".join(card_gb(s) for s in sizes)
            rep.error(
                agent,
                f"AGENT_INDEPENDENT_OF='{other}' holds in the role names "
                f"('{ra}' vs '{rb}') but both roles resolve to '{model}' at "
                f"{where}. Different role names are not "
                f"different weights: the resolver takes the largest candidate "
                f"that fits, so a larger card can make the auditor and the "
                f"party it audits identical - which is the monoculture "
                f"AGENT_INDEPENDENT_OF exists to prevent, arriving through the "
                f"upgrade path. Remove '{model}' from one of the two candidate "
                f"lists in config/models.json, or add a candidate that breaks "
                f"the tie at those sizes.",
            )

        # Same family, different size. A WARNING, deliberately, and the reason
        # matters more than the severity: a shared repo is evidence, not proof.
        # A 7B and a 70B of one family genuinely differ, and two models from
        # different labs trained on the same corpus are not independent either,
        # so neither direction is provable from the tag. What IS true is that
        # this is the shape of mistake the tag check cannot see, and it was
        # nearly shipped on 2026-09-27: filling the vacated 44GB reasoning slot
        # with deepseek-r1:70b would have put the CTO on one size of DeepSeek
        # while the CEO's `adjudication` role sat on another, and the build
        # would have stayed green. A warning is the honest severity for a proxy.
        for (fam, ma, mb), sizes in sorted(families.items()):
            where = ", ".join(card_gb(s) for s in sizes)
            rep.warn(
                agent,
                f"AGENT_INDEPENDENT_OF='{other}': '{ra}' and '{rb}' resolve to "
                f"'{ma}' and '{mb}' at {where} - different tags, but both from "
                f"the '{fam}' family, so the two judges share one training "
                f"recipe. This is weaker than the identical-weights error above "
                f"and it is a warning because a shared family is a proxy, not a "
                f"proof: a 7B and a 70B of one family are not the same model. "
                f"It is worth reading anyway, because the tag check is blind to "
                f"it by construction. Fix by giving one role a candidate from "
                f"another family at those sizes.",
            )


def _chain_root(agent: str, parent: dict[str, str]) -> str:
    """Follow reporting lines to the top. Bounded so a cycle cannot hang."""
    cur, hops = agent, 0
    while hops < 100:
        p = parent.get(cur, "")
        if not p or p not in parent:
            return cur
        cur = p
        hops += 1
    return cur


def check_readme_table(dirs: list[Path], rep: Report) -> None:
    """Every built agent must appear in the README's agent table.

    Added after two count errors in a single session, both mine: an agent was
    built and the prose said "three still to build" while omitting an existing
    one, and the same paragraph said "seventeen" about a table with eighteen
    rows. Prose counts drift because nothing notices. The checkable part is not
    the number - spelled-out numbers in prose are too brittle to assert on - but
    membership: an agent on disk that nobody documented is a real omission, and
    that is worth failing on.
    """
    readme = ROOT / "README.md"
    if not readme.is_file():
        return
    text = readme.read_text(encoding="utf-8")
    if not text.lstrip().startswith("#"):
        rep.warn("readme", "README.md does not start with a heading")

    listed = set(re.findall(r"^\|\s*`([a-z0-9-]+)`\s*\|", text, re.M))
    built = {d.name for d in dirs}

    undocumented = sorted(built - listed)
    for a in undocumented:
        rep.error(
            "readme",
            f"agent '{a}' exists but is not in the README agent table. An "
            f"agent nobody can find is not built, it is just there.",
        )

    stale = sorted(listed - built - set(re.findall(r"^\|\s*`([a-z0-9-]+)`", text, re.M)) )
    # planned agents legitimately have no directory; only flag rows that claim
    # to be built, which the table marks by existing on disk
    if listed and not built:
        rep.warn("readme", "README lists agents but none exist on disk")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the agents/ tree.")
    ap.add_argument("agent", nargs="?", help="check only this agent")
    ap.add_argument("--quiet", action="store_true", help="print problems only")
    args = ap.parse_args()

    if not AGENTS.is_dir():
        print(f"[fail] No agents directory at {AGENTS}", file=sys.stderr)
        return 1

    dirs = sorted(p for p in AGENTS.iterdir() if p.is_dir() and not p.name.startswith("_"))
    if args.agent:
        dirs = [d for d in dirs if d.name == args.agent]
        if not dirs:
            print(f"[fail] No such agent: {args.agent}", file=sys.stderr)
            return 1

    if not dirs:
        print("[fail] No agents found.", file=sys.stderr)
        return 1

    roles = known_roles()
    rep = Report()
    rows: list[tuple[str, int, str]] = []

    # Check the registry before the agents, so a broken registry is reported as
    # itself rather than as five identical per-agent complaints.
    check_no_hardcoded_loopback(rep)

    runtimes = check_runtime_registry(rep)
    if runtimes and not roles:
        rep.warn("models", "no model roles found in config/models.json - model choices unvalidated")

    for d in dirs:
        before_err = len(rep.errors)
        cases = check_agent(d, rep, roles, runtimes)
        status = "ok" if len(rep.errors) == before_err else "PROBLEMS"
        rows.append((d.name, cases, status))

    # Whole-tree, and only over the real tree: checking a single agent with
    # --only cannot see its siblings, so every parent would look missing.
    if not args.agent:
        check_reporting_graph(dirs, rep)
        check_independent_models(dirs, rep)
        check_independence_survives_resolution(dirs, rep)
        check_think_matches_model(dirs, rep)
        check_last_score_is_backed(dirs, rep)
        check_readme_table(dirs, rep)

    if not args.quiet:
        print()
        print(f"  {'AGENT':<20} {'CASES':>6}  {'STATUS'}")
        print("  " + "-" * 44)
        for name, cases, status in rows:
            print(f"  {name:<20} {cases:>6}  {status}")
        print("  " + "-" * 44)
        print(f"  {len(dirs)} agent(s), {sum(c for _, c, _ in rows)} test case(s)")
        print()

    # Flush first: stdout is block-buffered when piped, stderr is not, and
    # interleaving the two otherwise prints failures above the table they
    # belong to.
    sys.stdout.flush()

    for w in rep.warnings:
        print(f"[warn] {w}", file=sys.stderr)
    for e in rep.errors:
        print(f"[fail] {e}", file=sys.stderr)

    if rep.errors:
        print(
            f"\n  {len(rep.errors)} problem(s). Fix these before trusting a test "
            f"score - a malformed case file makes the score meaningless.\n",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        if rep.warnings:
            print(f"  {len(rep.warnings)} warning(s), nothing broken.\n")
        else:
            print("  All checks passed.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
