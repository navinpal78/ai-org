#!/usr/bin/env bash
set -u

AI_HOME="/home/dell/AI"
CEO_HOME="$AI_HOME/organisation/agents/ceo"
LOG_DIR="$AI_HOME/logs/ceo"
STATUS_FILE="$LOG_DIR/status"

timestamp() {
    date '+%Y-%m-%d %H:%M:%S %z'
}

log() {
    echo "[$(timestamp)] $*"
}

fail() {
    log "CEO BOOTSTRAP FAILED: $*"
    echo "NOT_READY" > "$STATUS_FILE"
    exit 1
}

mkdir -p "$LOG_DIR"

exec >> "$LOG_DIR/bootstrap.log" 2>&1

log "========================================"
log "CEO BOOTSTRAP START"
log "========================================"

echo "STARTING" > "$STATUS_FILE"

# ------------------------------------------------------------
# Core filesystem
# ------------------------------------------------------------

[ -d "$AI_HOME" ] || fail "AI directory missing: $AI_HOME"
[ -d "$CEO_HOME" ] || fail "CEO directory missing: $CEO_HOME"

# ------------------------------------------------------------
# Required CEO files
# ------------------------------------------------------------

for file in \
    CEO.md \
    CONSTITUTION.md \
    ROLE.md \
    SYSTEM.md \
    MEMORY.md
do
    [ -f "$CEO_HOME/$file" ] || fail "Required CEO file missing: $file"
done

log "CEO package: OK"

# ------------------------------------------------------------
# Required organisational registries
# ------------------------------------------------------------

for file in \
    "$AI_HOME/organisation/registries/RUNTIMES.md" \
    "$AI_HOME/organisation/registries/MODELS.md" \
    "$AI_HOME/organisation/registries/AGENTS.md"
do
    [ -f "$file" ] || fail "Required registry missing: $file"
done

log "Organisation registries: OK"

# ------------------------------------------------------------
# Runtime
# ------------------------------------------------------------

OPENCODE="$HOME/.opencode/bin/opencode"

[ -x "$OPENCODE" ] || fail "OpenCode executable missing: $OPENCODE"

OPENCODE_VERSION="$("$OPENCODE" --version 2>&1)" || \
    fail "OpenCode failed version check"

log "OpenCode: $OPENCODE_VERSION"

# ------------------------------------------------------------
# Basic environment
# ------------------------------------------------------------

PYTHON_VERSION="$(python3 --version 2>&1)" || \
    fail "Python unavailable"

NODE_VERSION="$(node --version 2>&1)" || \
    fail "Node unavailable"

log "Python: $PYTHON_VERSION"
log "Node: $NODE_VERSION"

# ------------------------------------------------------------
# Governance presence checks
# ------------------------------------------------------------

grep -q "Read-Only Means Read-Only" \
    "$CEO_HOME/CONSTITUTION.md" || \
    fail "CEO Constitution governance gate missing"

grep -q "Agent Creation Gate" \
    "$CEO_HOME/CONSTITUTION.md" || \
    fail "Agent Creation Gate missing"

grep -q "Runtime and Model Independence" \
    "$CEO_HOME/CONSTITUTION.md" || \
    fail "Runtime/Model Independence gate missing"

grep -q "Foundation Before Expansion" \
    "$CEO_HOME/CONSTITUTION.md" || \
    fail "Foundation Before Expansion gate missing"

log "Governance checks: OK"

# ------------------------------------------------------------
# Final status
# ------------------------------------------------------------

cat > "$STATUS_FILE" <<STATUS
READY
timestamp=$(timestamp)
hostname=$(hostname)
user=$(whoami)
opencode=$OPENCODE_VERSION
python=$PYTHON_VERSION
node=$NODE_VERSION
STATUS

log "========================================"
log "CEO STATUS: READY"
log "========================================"

exit 0
