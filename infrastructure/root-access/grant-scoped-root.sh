#!/usr/bin/env bash
#
# grant-scoped-root.sh
#
# Two things, both requiring root, both approved by the Founder on 2026-10-20:
#
#   1. Apply the OLLAMA_KEEP_ALIVE fix permanently (saves ~60s on every task).
#   2. Install a narrow sudoers drop-in so the CEO agent can run a short,
#      fixed list of root commands unattended.
#
# Run it once:
#
#   sudo bash /home/baba/AI/infrastructure/root-access/grant-scoped-root.sh
#
# Safe to re-run. Validates the sudoers file before installing it, so a typo
# here cannot lock you out of sudo.
#
# Written: 2026-10-20 · Author: Wadda Baba (CEO)

set -euo pipefail

AGENT_USER=baba
SUDOERS_FILE=/etc/sudoers.d/60-paperclip-agent
OLLAMA_SRC=/home/baba/AI/infrastructure/ollama/override.conf
OLLAMA_DST=/etc/systemd/system/ollama.service.d/override.conf

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo:  sudo bash $0" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
say "1/2 — OLLAMA_KEEP_ALIVE, permanently"
# ---------------------------------------------------------------------------

if [ ! -f "$OLLAMA_SRC" ]; then
  echo "Missing $OLLAMA_SRC" >&2
  exit 1
fi

if ! grep -q 'OLLAMA_KEEP_ALIVE' "$OLLAMA_SRC"; then
  echo "$OLLAMA_SRC has no OLLAMA_KEEP_ALIVE line — refusing to install it." >&2
  exit 1
fi

if [ -f "$OLLAMA_DST" ] && ! cmp -s "$OLLAMA_SRC" "$OLLAMA_DST"; then
  BK="$OLLAMA_DST.backup-$(date +%Y%m%d-%H%M%S)"
  cp -a "$OLLAMA_DST" "$BK"
  note "backed up current file to $BK"
fi

install -m 644 -o root -g root "$OLLAMA_SRC" "$OLLAMA_DST"
systemctl daemon-reload
systemctl restart ollama

sleep 2
if systemctl show ollama --property=Environment | tr ' ' '\n' | grep -q 'OLLAMA_KEEP_ALIVE=30m'; then
  note "OLLAMA_KEEP_ALIVE=30m is live"
else
  echo "OLLAMA_KEEP_ALIVE did not take effect — check 'systemctl status ollama'." >&2
  exit 1
fi
note "the first task after this restart pays the cold-load cost once. Expected."

# ---------------------------------------------------------------------------
say "2/2 — scoped passwordless sudo for $AGENT_USER"
# ---------------------------------------------------------------------------
#
# WHAT THIS ACTUALLY CHANGES
#
# $AGENT_USER is already in the `sudo` group, so $AGENT_USER can already become
# root with a password. This drop-in does not widen that. What it changes is
# that these *specific* commands no longer prompt — which is the only reason it
# is needed, because an unattended agent run has no terminal to type a password
# into.
#
# Every command below is either read-only or a service bounce. The argument
# lists are exact: `""` means "no arguments permitted", and a listed argument
# means only that argument is permitted. No wildcards anywhere.
#
# WHAT WAS DELIBERATELY LEFT OUT, AND WHY
#
# The obvious candidate was the ollama override install:
#
#   /usr/bin/install -m 644 -o root -g root <repo file> /etc/systemd/...
#
# It is NOT here. That file lives in /home/baba/AI, which $AGENT_USER can edit.
# Granting "copy that file to /etc as root" plus "daemon-reload" plus "restart"
# is arbitrary code execution as root — you could put any ExecStart= you liked
# into the source file first. It looks narrow and is not. That is why step 1
# above does the ollama install once, by you, from a file you can read first.
#
# `dmidecode` is restricted to no-args and three read-only `-t` selectors on
# purpose: `dmidecode --dump-bin FILE` writes a file as root, which would be
# the same escalation by a different door.
#
# TO REVOKE: sudo rm $SUDOERS_FILE

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

cat > "$TMP" <<EOF
# Scoped passwordless sudo for the Paperclip CEO agent running as $AGENT_USER.
# Installed by infrastructure/root-access/grant-scoped-root.sh on $(date -Is).
# Read-only diagnostics, plus an ollama bounce. No file writes. No unit edits.
# Revoke with: sudo rm $SUDOERS_FILE

Cmnd_Alias PC_DIAG = /usr/sbin/vgs "", \\
                     /usr/sbin/lvs "", \\
                     /usr/sbin/pvs "", \\
                     /usr/sbin/dmidecode "", \\
                     /usr/sbin/dmidecode -t system, \\
                     /usr/sbin/dmidecode -t memory, \\
                     /usr/sbin/dmidecode -t baseboard

Cmnd_Alias PC_OLLAMA = /usr/bin/systemctl daemon-reload, \\
                       /usr/bin/systemctl restart ollama

$AGENT_USER ALL=(root) NOPASSWD: PC_DIAG, PC_OLLAMA
EOF

if ! visudo -cqf "$TMP"; then
  echo "Generated sudoers file is invalid — NOT installing it." >&2
  visudo -cf "$TMP" || true
  exit 1
fi
note "sudoers syntax validated before install"

install -m 0440 -o root -g root "$TMP" "$SUDOERS_FILE"

if ! visudo -cqf /etc/sudoers; then
  echo "sudoers became invalid after install — removing the drop-in." >&2
  rm -f "$SUDOERS_FILE"
  exit 1
fi
note "installed $SUDOERS_FILE"

say "Verify"
note "what $AGENT_USER can now run without a password:"
sudo -u "$AGENT_USER" sudo -n -l 2>&1 | sed 's/^/      /' || true

echo
echo "Done. Both changes are live."
echo
echo "Unrelated but worth knowing: $AGENT_USER is also in the 'lxd' group, which"
echo "is a root-equivalent path on its own (an lxd container can mount the host"
echo "filesystem). If that membership is not deliberate, remove it:"
echo "  sudo gpasswd -d $AGENT_USER lxd"
