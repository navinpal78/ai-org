# Boot persistence and headless remote access

**Written:** 2026-10-20 · **Host:** `aipind` (headless) · **Author:** Wadda Baba (CEO)
**Answers:** *"how to ensure that I can access Paperclip & all the agents in it after every
reboot, remotely, as the aiserver is running headless"*

> **Amendment 2 — 2026-10-20 08:00.** Boot persistence is solved, but **crash
> persistence is not.** Paperclip is right now a foreground process inside one
> SSH login shell, and it dies the moment that shell closes. See
> [Amendment 2](#amendment-2--the-control-plane-is-living-in-an-ssh-window)
> at the bottom. Fix: [`paperclip-cutover.sh`](paperclip-cutover.sh).

---

## Short answer

It works now. Four things were missing and three of them are fixed; the fourth needs you.

| Component | Before | Now |
|---|---|---|
| Ollama | system unit, enabled | unchanged — starts at boot |
| SSH | `ssh.socket` enabled | unchanged — starts at boot |
| Tailscale | snap unit enabled | unchanged — starts at boot |
| **Hermes gateway (CEO)** | unit existed but **disabled** | **enabled** |
| **OpenCode server (CTO)** | no unit, started by hand | **unit created and enabled** |
| **Paperclip control plane** | no unit, started by hand | **unit created and enabled** |
| Reaching Paperclip remotely | bound to localhost only | **SSH tunnel over Tailscale — see below** |

**The thing that was actually broken:** `hermes-gateway.service` was running but *disabled*,
and OpenCode and Paperclip had no units at all. After a reboot you would have had an Ollama
daemon and nothing else — no CEO, no CTO, no control plane.

---

## Why user services, not system services

`loginctl show-user baba` reports **`Linger=yes`**, which was already set. Lingering means
systemd starts this user's services at boot without anyone logging in — exactly what a headless
box needs. So everything below runs as a **user** unit and **requires no root at all**.

```bash
systemctl --user status opencode
journalctl --user -u paperclip -f
```

---

## What was installed

Units live in `~/.config/systemd/user/`. All three are `WantedBy=default.target` and enabled.

| Unit | Starts |
|---|---|
| `hermes-gateway.service` | pre-existing; now enabled |
| `opencode.service` | `opencode serve --service` on 127.0.0.1:49374 |
| `paperclip.service` | `npx --yes paperclipai run` on 127.0.0.1:3100 |

### One detail in `opencode.service` that matters

The unit sets a deliberately minimal environment and **must not** inherit
`OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG` or `OPENCODE_CONFIG_CONTENT`.

OpenCode records its managed-service state in its config directory. If the server is started
with one config directory and the CLI reads another, the CLI cannot see the running server,
tries to start a second one, and dies on the port collision — which is exactly the failure that
made `opencode` look broken from the command line. A comment in the unit says so, because this
is not guessable from the error message.

**Verified after installing:** service came up under systemd, the CLI saw it, and Chalaak
answered correctly on the local model in 36 s.

### Verification status, stated honestly

| Unit | Verified |
|---|---|
| `opencode.service` | **Yes** — started under systemd and used end-to-end |
| `hermes-gateway.service` | Enabled; it was already running and was not restarted |
| `paperclip.service` | **Not fully tested.** Testing means stopping the Paperclip instance that is currently running the session doing this work. `npx --yes paperclipai --version` resolves (2026.1012.0), so the command is valid, but the unit has not been exercised as a full `run`. |

**Confirm the Paperclip unit on your next reboot.** If it does not come up:

```bash
systemctl --user status paperclip
journalctl --user -u paperclip -n 100 --no-pager
```

Then start it by hand the way you always have, and tell me what the log said.

---

## Reaching it remotely

Tailscale is up and both machines are on the tailnet:

| Machine | Tailnet address |
|---|---|
| `aipind` (this server) | `100.100.168.107` · `aipind.tailfc47f1.ts.net` |
| `desktop-go1khur` (your Windows desktop) | `100.67.148.117` |

Paperclip binds **127.0.0.1:3100** — localhost only. That is the right default: it keeps the
control plane off the network. So reach it through a tunnel rather than by exposing the port.

### Recommended: SSH tunnel over Tailscale

Works today, needs no changes, no root, and nothing new exposed. From your Windows desktop:

```powershell
ssh -L 3100:127.0.0.1:3100 baba@aipind.tailfc47f1.ts.net
```

Leave that window open and browse to **http://localhost:3100** on the desktop.

Everything travels inside the Tailscale tunnel and nothing is published beyond it.
`AllowTcpForwarding` is at its default (`yes`), so no SSH configuration change is needed.

### Optional, needs root once: `tailscale serve`

Removes the need to keep an SSH window open — Paperclip becomes a normal HTTPS URL on your
tailnet, reachable from any of your devices:

```bash
sudo tailscale serve --bg 3100
tailscale serve status
```

Paperclip would then be at `https://aipind.tailfc47f1.ts.net/`.

This needs root because `tailscale debug prefs` shows `OperatorUser: None` — no non-root user is
permitted to change serve configuration. Grant it permanently with:

```bash
sudo tailscale set --operator=baba
```

Undo at any time with `tailscale serve reset`.

**Only do this if you want it.** It is still private to your tailnet, but it is a standing
exposure rather than one you open and close. The SSH tunnel is the more conservative choice and
is the one I would keep unless the tunnel becomes annoying.

### A correction worth recording

While investigating I noted that `ssh.service` is `disabled` and nearly reported SSH as broken.
**It is not.** Ubuntu uses socket activation here: `ssh.socket` is `enabled` and `active`, so
sshd starts on demand and survives reboot. `ssh.service` showing `disabled` is normal and
correct. Same pattern as the Hermes false alarm — the surface reading was wrong.

---

## Post-reboot checklist

```bash
systemctl is-active ollama snap.tailscale.tailscaled.service ssh.socket
systemctl --user is-active hermes-gateway opencode paperclip
ss -lntp | grep -E '11434|49374|3100'
```

Expected: everything `active`, and all three ports listening on 127.0.0.1.

Then from your desktop, open the SSH tunnel and load http://localhost:3100.

## Rollback

```bash
systemctl --user disable --now opencode paperclip
systemctl --user disable hermes-gateway
rm ~/.config/systemd/user/opencode.service ~/.config/systemd/user/paperclip.service
systemctl --user daemon-reload
```

`hermes-gateway.service` was not created by this work — only enabled. Disabling it returns it
to how it was.

---

## Amendment 2 — the control plane is living in an SSH window

**Added 2026-10-20 08:00, after the Founder approved the vendor-service cutover.**

### What the earlier version of this document missed

It checked that `paperclip.service` was *enabled*. It did not check whether it was
*running*. It is not:

```
systemctl --user is-enabled paperclip   ->  enabled
systemctl --user is-active  paperclip   ->  inactive
```

Port 3100 is served by a different process entirely. Its ancestry:

```
sshd-session: baba [priv]
  └─ sshd-session: baba@pts/4
      └─ -bash
          └─ npm exec paperclipai run
              └─ node /home/baba/.npm/_npx/43414d9b790239bb/.../paperclipai run   (pid 55438)
```

**Paperclip is a foreground job in an interactive login shell.** When that SSH
session ends — you close the window, the laptop sleeps, the Wi-Fi drops — the
shell sends `SIGHUP` to its job and the entire control plane dies, taking every
running agent with it. `Linger=yes` does not help; lingering keeps *user
services* alive, and this is not a service.

This is strictly worse than the reboot problem that Amendment 1 fixed, because a
reboot is something you choose and a dropped connection is not. On a headless box
you reach only over the network, the failure also removes your means of noticing.

**Until the cutover is run, treat the pts/4 SSH session as load-bearing. Do not
close it.**

### The second problem: it is installed in a temp directory

```
which paperclipai
/home/baba/.npm/_npx/43414d9b790239bb/node_modules/.bin/paperclipai
```

That is an npx cache directory. `npm cache clean`, or ordinary cache eviction,
can remove it. And `paperclip.service`'s `ExecStart` is `npx --yes paperclipai
run`, which means that after a reboot with a cold cache systemd would **silently
fetch whatever version is newest on npm** and run your company on it. Pinning is
not optional for a control plane.

### Two units that do not collide — which is the danger

Paperclip ships its own service manager:

```
paperclipai service install | start | stop | restart | status | logs
```

The unit it installs is called **`paperclipai.service`**. The hand-rolled one is
**`paperclip.service`**. Different names, so systemd sees no conflict and will
happily enable both — and then **both start at boot and race for port 3100.**
Anyone installing the official service must disable the hand-rolled one in the
same breath. The cutover script does exactly that.

The vendor unit is also better on its own merits: `service restart` hot-restarts
while **preserving active agent runs**. The hand-rolled unit only knows
`SIGTERM`, which kills an agent mid-task.

### The fix: `paperclip-cutover.sh`

```bash
bash /home/baba/AI/infrastructure/boot-and-remote-access/paperclip-cutover.sh
```

**Run it yourself from an SSH shell — not as a Paperclip task.** Step 3 stops the
control plane, which would kill the agent running the script halfway through. The
script refuses to run if it detects `PAPERCLIP_RUN_ID`, for that reason.

What it does, in order:

1. `paperclipai install` into the managed per-user store, **pinned to 2026.1012.0** —
   the version running today. Relocating the install and upgrading it are two
   separate risks and the script deliberately does not take them together.
2. Disables `paperclip.service`, so the two units cannot race at boot. The unit
   file stays on disk, so rollback remains one command.
3. Stops the control plane. **Paperclip is down from here — about a minute.**
4. `paperclipai service install --enable-linger`.
5. Verifies: health 200 on :3100, and `paperclipai.service` both enabled and active.

Any failure rolls back automatically to the setup that works today, and tells you
what to do if even that fails. Full transcript at `logs/paperclip-cutover-*.log`.

### Post-cutover checklist (replaces the one above)

```bash
systemctl is-active ollama snap.tailscale.tailscaled.service ssh.socket
systemctl --user is-active hermes-gateway opencode paperclipai   # note the new name
systemctl --user is-enabled paperclip                            # expect: disabled
ss -lntp | grep -E '11434|49374|3100'
```

Once you trust the new unit, delete the old file:

```bash
rm ~/.config/systemd/user/paperclip.service && systemctl --user daemon-reload
```
