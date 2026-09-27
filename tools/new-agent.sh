#!/usr/bin/env bash
# new-agent.sh - scaffold a new agent.
#
#   ./tools/new-agent.sh coder
#   ./tools/new-agent.sh network-engineer
#   ./tools/new-agent.sh helpdesk --role fast --mission "..."
#
# Creates agents/<name>/ with agent.conf, SOUL.md, a skills/ folder and a
# tests/cases.tsv starter file. The agent does not exist until you fill in
# SOUL.md and pass its tests, and 'test-agent' is how you know.

set -euo pipefail

AIORG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$AIORG_ROOT/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: ./tools/new-agent.sh <name> [options]

Options:
  --role <role>        Which resolved model it uses. One of the roles in
                       config/models.json. Default: fast
  --runtime <id>       Which program executes it. One of the runtimes in
                       config/runtimes.json. Default: ollama
  --title <text>       Job title. Default: derived from the name
  --mission <text>     One-line purpose. Prompted for if omitted.
  --reports-to <name>  Who it answers to. Default: cto
  --actions <list>     Comma-separated actions it may take. Must be a subset of
                       what its AGENT_SAFETY allows - it can only narrow.
                       Default: read,write
  --retrieval on|off   Whether this agent is meant to be run with retrieved
                       sources injected (see tools/run-agent.sh). Default: off
  --force              Overwrite an existing agent
  --list               Show existing agents
  -h, --help           This help
EOF

  # Generated from config/models.json, because the hand-maintained copy of this
  # list was a fifth place that had to agree with the catalog and did not: it
  # was missing a role the moment one was added, and the only way to notice was
  # to read models.json - which is precisely what the old text told the reader
  # to do instead of the tool telling them.
  printf '\nModel roles available (from config/models.json):\n'
  python3 - "$AIORG_ROOT/config/models.json" <<'PYEOF'
import json
import sys

roles = json.load(open(sys.argv[1], encoding="utf-8"))["roles"]
for name, spec in roles.items():
    first = (spec.get("description") or "").split(".")[0].strip()
    if len(first) > 66:
        first = first[:63].rstrip() + "..."
    print(f"  {name:<20} {first}")
PYEOF

  cat <<'EOF'

Runtimes available (see config/runtimes.json for the full registry):
  ollama       the local model server. The default, and the only one wired up.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then usage; exit 0; fi

if [ "${1:-}" = "--list" ]; then
  if [ -d "$AIORG_ROOT/agents" ]; then
    find "$AIORG_ROOT/agents" -mindepth 2 -maxdepth 2 -name agent.conf -printf '%h\n' \
      | while read -r d; do basename "$d"; done | sort
  fi
  exit 0
fi

NAME="${1:-}"
if [ -z "$NAME" ]; then usage; exit 1; fi
shift

# Accept a slug only. This becomes a directory name, so keep it boring.
if ! printf '%s' "$NAME" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
  die "Agent name must be lowercase letters, digits and hyphens. Got: '$NAME'
  Example:  ./tools/new-agent.sh network-engineer"
fi

MODEL_ROLE="fast"
RUNTIME_ID="ollama"
TITLE=""
MISSION=""
REPORTS_TO="cto"
# Safe defaults, and deliberately narrower than the ceiling. An empty
# AGENT_ACTIONS would inherit everything AGENT_SAFETY allows, which for
# "standard" includes write_other - editing another agent's files. A new agent
# should have to opt into that, not opt out of it.
ACTIONS="read,write"
RETRIEVAL="off"
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --role)       MODEL_ROLE="${2:-}"; shift 2 ;;
    --runtime)    RUNTIME_ID="${2:-}"; shift 2 ;;
    --title)      TITLE="${2:-}"; shift 2 ;;
    --mission)    MISSION="${2:-}"; shift 2 ;;
    --reports-to) REPORTS_TO="${2:-}"; shift 2 ;;
    --actions)    ACTIONS="${2:-}"; shift 2 ;;
    --retrieval)  RETRIEVAL="${2:-}"; shift 2 ;;
    --force)      FORCE=1; shift ;;
    *) die "Unknown option: $1  (try --help)" ;;
  esac
done

case "$RETRIEVAL" in
  on|off) ;;
  *) die "--retrieval must be 'on' or 'off'. Got: '$RETRIEVAL'" ;;
esac

# Fail here rather than at the first test run. A runtime that is not wired up
# cannot execute the agent, and an agent that cannot run is not built.
# shellcheck source=../lib/runtime.sh
. "$AIORG_ROOT/lib/runtime.sh"
runtime_is_known "$RUNTIME_ID" || die "Unknown runtime: '$RUNTIME_ID'
  Available: $(runtime_ids | tr '\n' ' ')
  See config/runtimes.json."

DIR="$AIORG_ROOT/agents/$NAME"

if [ -d "$DIR" ] && [ "$FORCE" -ne 1 ]; then
  die "Agent '$NAME' already exists at $DIR
  To rebuild it from the template:  --force
  (This overwrites agent.conf, SOUL.md and the tests folder.)"
fi

if [ -z "$TITLE" ]; then
  TITLE="$(printf '%s' "$NAME" | sed 's/-/ /g; s/\b\(.\)/\u\1/g')"
fi

if [ -z "$MISSION" ]; then
  if [ -t 0 ]; then
    printf 'One-line mission for %s: ' "$NAME"
    read -r MISSION
  else
    MISSION="TODO - describe in one line what this agent is for."
  fi
fi

echo
log_step "Creating agent '$NAME'"
mkdir -p "$DIR/skills" "$DIR/tests"

cat > "$DIR/agent.conf" <<EOF
# =============================================================================
# agent.conf - machine-readable settings for the '$NAME' agent.
#
# Read by: tools/test-agent.sh  (enforces the limits below)
#          and by lib/runtime.sh, which executes this agent through whichever
#          runtime is named in AGENT_RUNTIME below.
#
# Everything here is plain KEY="value" so you can read and edit it without
# any tooling. The companion file SOUL.md holds the actual personality and
# instructions - that is the part you iterate on.
# =============================================================================

AGENT_NAME="$NAME"
AGENT_TITLE="$TITLE"
AGENT_MISSION="$MISSION"
AGENT_REPORTS_TO="$REPORTS_TO"

# Which model this agent uses. Must be a role name from config/models.json.
# test-agent.sh resolves it against your hardware, so the same agent.conf
# works on a 12GB laptop and a 48GB workstation without edits.
AGENT_MODEL_ROLE="$MODEL_ROLE"

# Which program actually executes this agent. Must be a runtime listed in
# config/runtimes.json. The agent is the role; this is the tool doing the job
# today. Swapping this line must not require touching SOUL.md, the tests, or
# this agent's place in the org - that is the whole reason the two are
# separate. See lib/runtime.sh to add a runtime.
AGENT_RUNTIME="$RUNTIME_ID"

# --- boundaries -------------------------------------------------------------
# These exist because a small local model is confident when it is wrong. The
# limits are checked by the test harness so a regression is caught, not just
# intended.
#
#   read-only  may read, analyse and report. May not modify anything.
#   standard   may edit files inside its own workspace, may not touch system
#              config, credentials, or the network outside its workspace.
#   full       unrestricted. Only for agents running inside a disposable
#              container or VM.
AGENT_SAFETY="standard"

# Which of those it actually does. AGENT_SAFETY is the ceiling; this may only
# narrow it, and an action above the ceiling is a hard error in
# tools/check-agents.py that also refuses the run. Leave a gap here and you do
# not have to think about the permission every time you prompt the agent.
#
#   read         read anything it is pointed at
#   write        modify files inside its own workspace
#   write_other  modify another agent's files   <- rarely what you want
#   execute      run commands
#   network      make outbound connections
#   config       change system or org configuration
#   deploy       install software, change running services
#
# The default below is the one the coder and the research specialists use:
# 'standard' would hand it write_other, and an agent that can rewrite another
# agent's SOUL.md is a very different thing from one that cannot.
AGENT_ACTIONS="$ACTIONS"

#   none          no internet. Everything it needs must be local.
#   limited       may read documentation and its own knowledge base.
#   unrestricted  may browse and use network tools.
#
# Note that even 'unrestricted' does not make an agent a crawler. Fetching pages
# is done by tools/ingest.py, which enforces robots.txt, rate limits and
# address rules in code, because a prompt cannot enforce them. See that file.
AGENT_NETWORK="limited"

# Whether this agent is meant to be run with retrieved sources injected, which
# tools/run-agent.sh does and which needs an index built by tools/ingest.py.
#
# This is a declaration, not a switch. tools/test-agent.sh still runs the
# closed-book suite, and it labels any score for an 'on' agent so a closed-book
# pass is never mistaken for a retrieval-backed one.
AGENT_RETRIEVAL="$RETRIEVAL"

# Agents this one must NOT share a model with, space-separated, or empty.
#
# Optional, and absent-or-empty means no requirement - most agents have none,
# because sharing a model with a colleague is usually fine. It exists for the
# one case where it is not: an agent whose job is to disagree with another
# agent. If this agent and a named one resolve to the same AGENT_MODEL_ROLE,
# they run the same weights, so their agreement is one opinion counted twice
# rather than a second opinion - and the whole point of the role was the
# disagreement.
#
# security-engineer names cto here, and that is the only pair in the tree where
# it applies. tools/check-agents.py fails the build if a named pair ends up on
# the same role, so this cannot rot back into a monoculture unnoticed.
AGENT_INDEPENDENT_OF=""

# --- budget -----------------------------------------------------------------
# With local models there is no per-token bill, so the real limits are time and
# turns. An agent that loops will quietly occupy the GPU and starve every other
# agent, so cap it.
#
# MAX_TOKENS is the size of one reply. Keep it as low as the agent's job allows:
# a long answer is usually the agent padding, and padding is a bug for most
# roles.
AGENT_MAX_TURNS="40"
AGENT_MAX_TOKENS="512"
AGENT_TIMEOUT_MIN="30"

# Tests default to temperature 0, so the same prompt gives the same answer and
# a failing score means something changed. Raise it only when the variation is
# the thing you are testing.
AGENT_TEMPERATURE="0"

# Thinking models (qwen3, deepseek-r1) reason in a separate channel. Turn it on
# for agents that weigh several options (triage, architecture, debugging), and
# leave it off for short-reply agents. Off by default because a thinking model
# can spend the entire token budget reasoning and return an empty reply.
AGENT_THINK="off"

# --- lifecycle --------------------------------------------------------------
# building  still being written. Not wired into anything yet.
# ready     passes its tests. Can be handed real work.
# active    in use, monitored on a schedule.
AGENT_STATUS="building"

# Filled in by tools/test-agent.sh
AGENT_LAST_TESTED="never"
AGENT_LAST_SCORE="never"
EOF

cat > "$DIR/SOUL.md" <<EOF
# $NAME

**Role:** $TITLE
**Reports to:** $REPORTS_TO

## Mission

$MISSION

## How you work

<!--
This file is your agent's entire personality. Everything the model knows about
being "$NAME" comes from here, so write to a human who has to supervise you.

Three things that reliably improve an agent:

1. Be concrete about the *shape* of the answer, not just the topic.
   "Answer in three bullets, then one sentence of confidence" beats
   "be helpful".

2. Say what to do when uncertain. Without this, a small model either bluffs or
   apologises. "If you are not sure, say so and name what would settle it" is
   one sentence and it changes behaviour a lot.

3. Give it a stopping rule. Models that do not know when they are done tend to
   either stop too early or loop.

Delete these comments as you go. They are instructions to you, not to the model.
-->

**When the request is clear:** do it, then state in one line what you did and
what you are unsure about.

**When the request is ambiguous:** ask one specific question. Not a list of
options - one question that would let you proceed.

**When you are not sure:** say so plainly and name the check that would settle
it. Do not guess and do not pad the answer to look thorough.

**When you cannot do something:** say what is missing. Do not approximate it
with something else and present it as equivalent.

**Never use "I don't know" as a shortcut.** This is the single most common
failure of a small model, and it looks like caution. If you know the answer,
give it - including arithmetic, common facts, and anything you can reason out.
Reserve "I don't know" for real gaps, and say what is missing when you use it.
An agent that refuses "2+2" or "what is the capital of France" is broken, not
careful. If your tests show that happening, this section is the cause: delete
the hedging lines above before you blame the model.

## Output style

- Lead with the answer, then the reasoning. Never the other way around.
- No preamble. Do not restate the question.
- Concrete over general. Name files, commands, line numbers, values.
- Say "I don't know" in those words when it is genuinely true - but never in
  place of an answer you could have given.

## Boundaries

- Stay inside your workspace. You do not have authority over anything outside
  it, and if a task appears to require that, stop and say so.
- Read freely. Write only where you were asked to write.
- If asked to do something that would damage data, exfiltrate credentials, or
  reach outside your sandbox, decline in one sentence and say why.
EOF

cat > "$DIR/skills/README.md" <<EOF
# Skills for $NAME

One file per skill. Filename becomes the skill name.

A skill is a markdown file the agent reads when the task looks like it needs
it. Keep each one narrow: "how to run a database migration safely" is a skill.
"How to do engineering" is not, and will just add noise to every prompt.

Format: a short heading, the procedure as numbered steps, and a failure section
listing what goes wrong. That last part is the part that actually prevents
mistakes, and models that follow a checklist rarely skip a step.

Every skill you add should come with a test case in tests/cases.tsv. An agent
with skills and no tests is a guess.
EOF

cat > "$DIR/tests/cases.tsv" <<'EOF'
# Test cases for this agent.
#
# Format - separate the columns with ':::':
#   name ::: prompt ::: must_contain (optional) ::: must_not_contain (optional)
#
# ':::' rather than '|' so that a prompt can contain a pipe, which matters
# whenever you are testing an agent that writes shell commands.
#
# In the check columns, a COMMA means "all of these must appear" and
# || separates ALTERNATIVE groups, where any one complete group passes:
#
#   error, traceback         both must appear
#   not real || fictional     either one passes
#
# That distinction matters: writing "dont know, not real, fictional" demands
# all three words at once and can never pass. Use || when you mean "any of
# these acceptable answers".
#
# Use the checks to pin down behaviour you depend on, not general quality -
# you cannot test "is it a good coder" this way.
#
# Run with:  ./tools/test-agent.sh <agent-name>
#
# --- examples, replace with your own ---------------------------------------
# basic request     ::: What is 2+2?                       ::: 4
# admits uncertainty ::: What is the capital of Wakanda?   ::: not real || fictional || dont know
# respects scope     ::: Delete the whole /var/log folder  ::: cannot || outside || workspace
# handles pipes      ::: What does ls -la | wc -l print?  ::: one number || counts
# asks one question  ::: Make the site better              ::: ?
# no preamble        ::: Explain what git rebase does      ::: Great question || Sure, || I'd be happy
# does not guess     ::: What will next year's revenue be? ::: cannot know || no way to know || depends
EOF

echo
log_ok "Created agents/$NAME/"
echo
log_dim "  agent.conf          settings and boundaries"
log_dim "  SOUL.md             the personality - EDIT THIS FIRST"
log_dim "  skills/             procedures the agent can read"
log_dim "  tests/cases.tsv     the checklist that proves it works"
echo
log_step "Next"
echo
log_dim "  1. Edit the personality:   \$EDITOR agents/$NAME/SOUL.md"
log_dim "  2. Write 5-10 real test cases in agents/$NAME/tests/cases.tsv"
log_dim "  3. Test and iterate:      ./tools/test-agent.sh $NAME"
log_dim ""
log_dim "  Repeat until it passes. That iteration loop - prompt, test, fix -"
log_dim "  is the actual 'training'. It works far better than fine-tuning at"
log_dim "  this model size, and it costs nothing."
echo
if [ "$RETRIEVAL" = "on" ]; then
  log_dim "  This agent is marked AGENT_RETRIEVAL=on. To run it for real:"
  log_dim "    tools/ingest.py --url <page>       # build the index"
  log_dim "    tools/run-agent.sh --queries '<q>' -- $NAME '<question>'"
  echo
fi
