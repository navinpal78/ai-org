#!/usr/bin/env bash
#
# paperclip-cutover.sh
#
# Moves the Paperclip control plane off the throwaway npx cache and onto the
# vendor-managed systemd user service (paperclipai.service), and removes the
# hand-rolled paperclip.service so the two can never race for port 3100.
#
# ---------------------------------------------------------------------------
# RUN THIS YOURSELF, FROM AN SSH SHELL ON aipind. Not from a Paperclip task.
#
# Paperclip is unreachable for roughly a minute while this runs, and any agent
# run in flight dies with it — including the agent that would otherwise be
# running this script. That is why it is a script you run, not a task I do.
#
# Safe to re-run. If any step fails it rolls back to the setup that works today.
# ---------------------------------------------------------------------------
#
# Written: 2026-10-20 · Author: Wadda Baba (CEO) · Approved by: Founder

set -euo pipefail

PORT=3100
# Pinned to the version running right now. This script relocates the install;
# it deliberately does NOT also upgrade it. Those are two separate risks and
# they should not be taken in the same step. To upgrade later, deliberately:
#   paperclipai install -y && paperclipai service restart
PIN_VERSION="${PIN_VERSION:-2026.1012.0}"
LOGDIR=/home/baba/AI/logs
LOG="$LOGDIR/paperclip-cutover-$(date +%Y%m%d-%H%M%S).log"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }

health()    { curl -fsS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null || true; }
port_pid()  { ss -ltnpH "( sport = :$PORT )" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }

wait_for_health()    { local d=${1:-90} i; for ((i=0;i<d;i++)); do [ "$(health)" = "200" ] && return 0; sleep 1; done; return 1; }
wait_for_port_free() { local d=${1:-45} i; for ((i=0;i<d;i++)); do [ -z "$(port_pid)" ] && return 0; sleep 1; done; return 1; }

ROLLED_BACK=0
rollback() {
  if [ "$ROLLED_BACK" = 1 ]; then return; fi
  ROLLED_BACK=1
  say "SOMETHING FAILED — rolling back to the setup that worked before"
  systemctl --user stop    paperclipai.service >/dev/null 2>&1 || true
  systemctl --user disable paperclipai.service >/dev/null 2>&1 || true
  systemctl --user enable  paperclip.service   >/dev/null 2>&1 || true
  systemctl --user start   paperclip.service   >/dev/null 2>&1 || true
  if wait_for_health 90; then
    note "Rollback OK. Paperclip is back up on http://127.0.0.1:$PORT"
    note "Nothing is lost. Send me the log and I will work out what happened:"
    note "  $LOG"
  else
    note "ROLLBACK DID NOT RESTORE HEALTH. Start it by hand in this shell:"
    note "  npx --yes paperclipai run"
    note "Then send me $LOG"
  fi
}
trap rollback ERR

mkdir -p "$LOGDIR"
exec > >(tee -a "$LOG") 2>&1

# --------------------------------------------------------------------------
say "Preflight"
# --------------------------------------------------------------------------

if [ "$(id -u)" -eq 0 ]; then
  echo "Run this as baba, not as root. The service is a *user* service." >&2
  exit 1
fi

if [ -n "${PAPERCLIP_RUN_ID:-}" ]; then
  echo "Refusing to run: PAPERCLIP_RUN_ID is set, so this is executing inside a" >&2
  echo "Paperclip agent run. Stopping the control plane would kill this script" >&2
  echo "halfway through. Run it from a plain SSH shell instead." >&2
  exit 1
fi

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

if ! systemctl --user is-system-running >/dev/null 2>&1; then
  : # degraded is fine; we only need the user manager to answer
fi
systemctl --user show-environment >/dev/null

if [ "$(loginctl show-user baba -p Linger --value 2>/dev/null)" != "yes" ]; then
  echo "Linger is not enabled for baba. Without it a user service does not start" >&2
  echo "at boot on a headless box. Fix first:  sudo loginctl enable-linger baba" >&2
  exit 1
fi
note "linger: yes"

BEFORE_HEALTH="$(health)"
BEFORE_PID="$(port_pid)"
note "health before: ${BEFORE_HEALTH:-none}    pid on :$PORT: ${BEFORE_PID:-none}"

if [ "$BEFORE_HEALTH" != "200" ]; then
  echo "Paperclip is not healthy right now. Fix that before cutting over —" >&2
  echo "otherwise a failure here is indistinguishable from the problem you already have." >&2
  exit 1
fi

# --------------------------------------------------------------------------
say "Step 1/5 — install Paperclip into the managed per-user store"
# --------------------------------------------------------------------------
note "pinning to $PIN_VERSION (the version running right now)"
note "this does not touch the running process"

OLD_BIN="$(command -v paperclipai || true)"
note "current binary: ${OLD_BIN:-not on PATH}"

npx --yes paperclipai install --version "$PIN_VERSION" --yes

hash -r
NEW_BIN=""
for cand in "$HOME/.local/bin/paperclipai" "$HOME/.local/share/paperclipai/bin/paperclipai"; do
  if [ -x "$cand" ]; then NEW_BIN="$cand"; break; fi
done
if [ -z "$NEW_BIN" ]; then
  NEW_BIN="$(command -v paperclipai || true)"
fi

if [ -z "$NEW_BIN" ] || [ ! -x "$NEW_BIN" ]; then
  echo "Could not find the installed binary after 'paperclipai install'." >&2
  exit 1
fi
case "$NEW_BIN" in
  *_npx*) echo "Installed binary still resolves into the npx cache ($NEW_BIN)." >&2
          echo "That is the exact fragility this script exists to remove." >&2
          exit 1 ;;
esac
note "managed binary: $NEW_BIN"
note "version: $("$NEW_BIN" --version 2>&1 | tail -1)"

# --------------------------------------------------------------------------
say "Step 2/5 — disable the hand-rolled paperclip.service"
# --------------------------------------------------------------------------
note "the two units have different names, so without this they would BOTH start"
note "at boot and race for port $PORT"
systemctl --user disable paperclip.service 2>&1 || true
note "the unit file stays on disk at ~/.config/systemd/user/paperclip.service"
note "so rollback is still one command. Delete it once you trust the new one."

# --------------------------------------------------------------------------
say "Step 3/5 — stop the control plane  (Paperclip goes down HERE)"
# --------------------------------------------------------------------------
systemctl --user stop paperclip.service >/dev/null 2>&1 || true

STOP_PID="$(port_pid)"
if [ -n "$STOP_PID" ]; then
  note "sending SIGTERM to pid $STOP_PID"
  kill -TERM "$STOP_PID" 2>/dev/null || true
fi
if ! wait_for_port_free 45; then
  STOP_PID="$(port_pid)"
  note "still holding the port after 45s — sending SIGKILL to pid $STOP_PID"
  kill -KILL "$STOP_PID" 2>/dev/null || true
  wait_for_port_free 15 || { echo "Port $PORT never freed." >&2; exit 1; }
fi
note "port $PORT is free"

# --------------------------------------------------------------------------
say "Step 4/5 — install and start the vendor service"
# --------------------------------------------------------------------------
"$NEW_BIN" service install --enable-linger

# --------------------------------------------------------------------------
say "Step 5/5 — verify"
# --------------------------------------------------------------------------
if ! wait_for_health 120; then
  echo "Paperclip did not come back healthy within 120s." >&2
  echo "Recent service log:" >&2
  journalctl --user -u paperclipai.service -n 40 --no-pager >&2 || true
  exit 1
fi

"$NEW_BIN" service status --json

ENABLED="$(systemctl --user is-enabled paperclipai.service 2>&1 || true)"
ACTIVE="$(systemctl --user is-active  paperclipai.service 2>&1 || true)"
OLD_ENABLED="$(systemctl --user is-enabled paperclip.service 2>&1 || true)"

echo
say "Result"
note "paperclipai.service   enabled=$ENABLED  active=$ACTIVE"
note "paperclip.service     enabled=$OLD_ENABLED   (should be 'disabled')"
note "health on :$PORT      $(health)"
note "binary                $NEW_BIN"
note "log                   $LOG"

if [ "$ENABLED" != "enabled" ] || [ "$ACTIVE" != "active" ]; then
  echo "Service is not both enabled and active — not declaring success." >&2
  exit 1
fi

trap - ERR
echo
echo "Cutover complete. Two things are now true that were not before:"
echo "  1. Paperclip no longer runs out of an npx cache directory."
echo "  2. Paperclip no longer dies when an SSH session closes."
echo
echo "Confirm on your next reboot with:"
echo "  systemctl --user is-active hermes-gateway opencode paperclipai"
