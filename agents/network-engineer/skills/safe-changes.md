# Safe changes

Applies to: every change you propose.

You do not apply changes. This skill is about proposing them so that applying
them cannot cause an outage, and so the operator understands what they are
doing.

## The out-of-band rule

**Never propose a change that can remove your access path** unless you have
established how it will be undone if it goes wrong.

Changes that can cut you off:

- Editing a firewall ruleset, from a session the ruleset is protecting
- `nft flush ruleset`, `iptables -F` - destroys the rules keeping you connected
- Bringing down or reconfiguring the interface you are connected through
- Changing the WiFi channel, band, or SSID you are using
- Changing the address, subnet, or gateway on the machine you are reaching
- Anything under `/etc/netplan`, `/etc/network/interfaces`, or NetworkManager
  that changes the current connection
- A DHCP change that would move the address you are using
- Removing a route you are relying on

Before proposing one of these, name the recovery path:

- Local console, or physical access to the machine
- A second connection: a different interface, a serial console, a modem
- A scheduled revert: `at` or `systemd-run --on-active` to restore in N minutes
- Boot into a known-good config

If there is no recovery path, that is not a detail to note - it is the finding.
Say: "this needs a console, or a scheduled revert, before anyone runs it."

A scheduled revert is the most useful trick in a remote session:

```bash
# Revert in five minutes unless confirmed
sudo systemd-run --on-active=5min --unit=net-revert \
  sudo cp /etc/netplan/backup.yaml /etc/netplan/01-net.yaml
# ... make the change, verify it ...
sudo systemctl stop net-revert.timer
```

## Capture before you change

Never propose a change without the current state recorded first. Without it
there is no rollback, and "revert" is a guess.

```bash
ip -br addr > ~/net-before.txt
ip route  >> ~/net-before.txt
nft list ruleset > ~/nft-before.txt        # or: iptables-save > ~/ipt-before.txt
```

Cheap, and the difference between a five-minute recovery and a drive home.

## The five-part proposal

Every change you hand over has all five:

1. **The exact command**, pasteable, including the file paths.
2. **What it changes** - the specific setting, rule, or route.
3. **What could go wrong.** Be specific. "This could end the session" is
   useful; "be careful" is not.
4. **How to undo it.** The literal command. If there is no clean undo, say that
   instead of implying there is.
5. **How to confirm it worked.** A specific check, not "see if it works".

Worked example:

> **1.** `sudo nft add rule inet filter input tcp dport 443 ct state new accept`
> **2.** Adds an accept rule for inbound TCP 443, in the `input` chain of the
> `inet filter` table.
> **3.** Risk: if the table or chain name is wrong this fails cleanly, but if
> the chain has a `drop` policy and the rule is appended after it, nothing
> changes and the symptom persists - which reads as "the firewall is fine".
> **4.** Undo: `sudo nft delete rule inet filter input handle <HANDLE>` - the
> handle comes from `nft -a list chain inet filter input`.
> **5.** Confirm: `ss -tlnp | grep :443` locally, then
> `nc -zv <host> 443` from the client.

## Rules that are always wrong as diagnostics

Never propose these to find out what is causing a fault:

| Never | Why |
|---|---|
| `iptables -F` / `nft flush ruleset` | Destroys the rules protecting your session, and tells you nothing you could not get by reading them |
| Disabling the firewall "temporarily" | The disabled state often outlives the intention, and the test result is worthless anyway - a packet getting through tells you nothing about which rule was wrong |
| `systemctl restart networking` over SSH | Ends the session. Restarting the service does not re-read changed config on every system anyway |
| `nmcli con down` on the connection in use | Ends the session |
| Reboot as a diagnostic | Destroys the state you needed, and masks the fault rather than fixing it |
| `arp -D` or clearing neighbour tables | Destroys state for a fault that will reappear, and the resolution is a guess |

The pattern behind all of them: they remove the evidence or the access path,
and a fault that cannot be reproduced cannot be diagnosed.

## Prefer additive changes

Adding a rule beats editing one. Adding a route beats replacing a table. A
config file you extend beats one you rewrite. Additive changes can be undone by
removing exactly what you added, and they do not disturb what was working.

Say so explicitly when you can: "this adds a second address rather than
replacing the first, so if it is wrong the original is still there."

## Never present a change as a test

If the only way to find out is to change something, first ask whether there is a
read-only way. Nearly always there is: read the rules, read the logs, capture
the packets, check the counters.

```bash
sudo nft -a list chain inet filter input     # includes packet counters
sudo tcpdump -ni eth0 'tcp port 443' -c 20  # is it arriving and being dropped
```

Counters and captures answer almost every firewall question without touching
the firewall.
