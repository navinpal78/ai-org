# Scoped root access for the CEO agent

**Written:** 2026-10-20 · **Decided by:** Founder, 2026-10-20
**Decision:** *"Give me a way to run specific root commands"* — chosen over doing
each root action by hand, and over leaving the Ollama fix as a runtime-only hack.

---

## Run this once

```bash
sudo bash /home/baba/AI/infrastructure/root-access/grant-scoped-root.sh
```

It does two things:

1. Installs the `OLLAMA_KEEP_ALIVE=30m` override permanently and restarts Ollama.
2. Installs `/etc/sudoers.d/60-paperclip-agent`, a narrow passwordless sudo list.

It validates the sudoers file with `visudo` **before** installing it and removes it
again if `/etc/sudoers` fails to parse afterwards, so a mistake here cannot lock you
out of sudo.

---

## What is actually being granted

```
Cmnd_Alias PC_DIAG   = /usr/sbin/vgs "", /usr/sbin/lvs "", /usr/sbin/pvs "",
                       /usr/sbin/dmidecode "",
                       /usr/sbin/dmidecode -t system,
                       /usr/sbin/dmidecode -t memory,
                       /usr/sbin/dmidecode -t baseboard

Cmnd_Alias PC_OLLAMA = /usr/bin/systemctl daemon-reload,
                       /usr/bin/systemctl restart ollama

baba ALL=(root) NOPASSWD: PC_DIAG, PC_OLLAMA
```

Everything on that list is read-only or a service bounce. The argument lists are
exact — `""` means *no arguments permitted*, a named argument means *only that
argument*. There are no wildcards.

### This does not make `baba` more powerful

`baba` is already in the `sudo` group and can already become root with a password.
The drop-in does not widen that. It removes the *password prompt* for this exact
list — which is the entire point, because an unattended agent run has no terminal
to type a password into. The change is "unattended", not "more".

### Why these commands

| Command | Answers |
|---|---|
| `vgs` / `lvs` / `pvs` | The ~850 GB of this disk that is unaccounted for. The root volume is 100 GB of a 950 GB partition and nothing non-root can explain the rest. |
| `dmidecode -t memory` | The RAM section of the spec review, which came back empty because `dmidecode` produced no output without root. |
| `systemctl restart ollama` | Re-apply tuning after an Ollama config change without waiting for you. |

---

## What was deliberately left out, and why it matters

The obvious thing to grant was the Ollama override install itself:

```
/usr/bin/install -m 644 -o root -g root \
  /home/baba/AI/infrastructure/ollama/override.conf \
  /etc/systemd/system/ollama.service.d/override.conf
```

**It is not on the list.** That source file lives in `/home/baba/AI`, which `baba`
can edit. "Copy that file to `/etc` as root" plus "`daemon-reload`" plus "`restart`"
is **arbitrary code execution as root** — write any `ExecStart=` you like into the
source file first, then install it. It reads as a narrow, specific grant and is not
one.

So the script performs that install **once, itself, under your sudo**, from a file
you can read first — and does not hand the capability over.

`dmidecode` is pinned to no-args and three read-only `-t` selectors for the same
reason: `dmidecode --dump-bin FILE` writes a file as root, which is the same
escalation through a different door.

This is the general shape to watch for in any future grant: a rule is only as narrow
as the *least* trusted input it touches.

---

## Revoke

```bash
sudo rm /etc/sudoers.d/60-paperclip-agent
```

Immediate, no reload needed. The Ollama change is independent and survives; roll
that back separately via `infrastructure/ollama/README.md`.

---

## Unrelated finding, worth a minute

`baba` is in the **`lxd`** group. That is a root-equivalent path on its own — an
LXD container can mount the host filesystem. It predates this work and nothing here
relies on it, but it means the careful scoping above is not the weakest link if the
membership is not deliberate.

```bash
sudo gpasswd -d baba lxd    # if you do not use LXD
```
