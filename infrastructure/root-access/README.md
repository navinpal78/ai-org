# Scoped root access for the CEO agent

**Written:** 2026-10-20 · **Decided by:** Founder, 2026-10-20
**Decision:** *"Give me a way to run specific root commands"* — chosen over doing
each root action by hand, and over leaving the Ollama fix as a runtime-only hack.

**Status: LIVE.** Run by the Founder at **08:27 on 2026-10-20** and independently
verified at 09:59 — see *Verification* below. The script is idempotent and safe to
re-run, but it does not need re-running.

---

## Verification, 2026-10-20 09:59

| Check | Result |
|---|---|
| `/etc/sudoers.d/60-paperclip-agent` | present, `-r--r----- root:root`, 797 bytes |
| `sudo -n -l` | lists `PC_DIAG` + `PC_OLLAMA`, no password prompt |
| Live Ollama env (`systemctl show ollama -p Environment`) | **6 vars, `OLLAMA_KEEP_ALIVE=30m` present** |
| `sudo -n vgs` unattended | returns volume groups, no TTY needed |
| **End-to-end keep-alive** | loaded `qwen3.5:9b`, `ollama ps` → **`UNTIL: 29 minutes from now`** |

That last row is the one that matters. Before the fix the same check read
`UNTIL: 4 minutes from now` — the default 5-minute eviction. The fix is confirmed by
behaviour, not just by configuration.

---

## The ~850 GB is now answered: it is genuinely free

The first thing the grant bought:

```
vgs  →  ubuntu-vg   VSize <950.82g   VFree <850.82g
lvs  →  ubuntu-lv   LSize 100.00g    (the only LV)
df / →  98G size, 33G used, 61G avail, ext4
```

**Nothing is lost or hidden.** The installer created a 100 GB logical volume and
left the remaining ~850 GB as *unallocated extents* in the volume group — the Ubuntu
installer's default when you accept the LVM layout without dragging the size slider.

It is reclaimable online, with no downtime and no unmount, because ext4 grows live.

### Do not use `+100%FREE`

An earlier draft of this file recommended `-l +100%FREE`. **That advice was
incomplete and is superseded.** Take what you need and leave the rest unallocated:

```bash
sudo lvextend -L 400G /dev/ubuntu-vg/ubuntu-lv
sudo resize2fs  /dev/ubuntu-vg/ubuntu-lv
```

Two independent reasons, both specific to this box:

1. **The asymmetry.** Growing ext4 is online and routine; you can run the pair
   above again at any time. *Shrinking* is not — ext4 cannot shrink mounted, so
   reversing an over-extend on the root volume means booting a live USB. Taking
   less is a decision you can revisit; taking everything is not.

2. **Free extents are this machine's only undo button.** An LVM snapshot of the
   root LV needs unallocated extents in the volume group to hold changed blocks.
   With one disk, no off-box copy and no git remote (§11 deferred by the Founder),
   `lvcreate --snapshot` before a risky change is the closest thing to a backup
   available here. `+100%FREE` removes that capability permanently in exchange
   for space nothing is asking for.

400 GB leaves ~360 GB free on `/` and ~550 GB of extents in reserve — far more
headroom than the workload needs on either axis.

**Neither command is on the sudo list, deliberately** — `lvextend` takes a device
path, so a rule permitting it permits it against *any* volume. This is a one-time
Founder action, not an agent capability.

Worth doing before it bites: 61 GB free, Ollama models are 5–7 GB each, and
Paperclip carries an embedded Postgres whose data directory only grows.

### Independently corroborated at the block layer, 2026-10-20 10:03

The Founder ran `lsblk`, `sudo blkid` and `df -hT`. These read the *block* layer,
where `vgs`/`lvs` read the LVM layer — so they are a genuine second opinion, not a
restatement:

- `lsblk` — one `nvme0n1` (953.9G). Three partitions, all accounted for. **No
  second disk and no unmounted partition.**
- `blkid` — exactly three filesystem signatures on the box: `nvme0n1p1` vfat,
  `nvme0n1p2` ext4, `ubuntu--vg-ubuntu--lv` ext4. **Nothing holds a filesystem
  inside the free extents**, so extending the LV cannot overwrite data.
- `df -hT` — matches `/` at 98G / 61G avail.

Also visible in that paste: `sudo blkid` **prompted for a password**. `blkid` is
not on the granted list, so this is the scoping behaving as designed rather than a
blanket NOPASSWD. Confirmed again when `sudo -n vgs -o vg_free` was refused — the
rules pin exact arguments, so even an extra flag on a permitted command falls
through to the password prompt.

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
| `vgs` / `lvs` / `pvs` | The ~850 GB of this disk that was unaccounted for. **Answered on day one** — see above: unallocated LVM extents, reclaimable. |
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
