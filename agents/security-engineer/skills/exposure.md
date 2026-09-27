# Exposure

Applies to: "is anything here reachable that should not be", and "is anything
here out of date".

You are looking at a system you are authorised to look at. Every check in this
skill is read-only. Nothing here changes state, and nothing here tests whether
something is *vulnerable* by trying it.

## Authorisation comes first

Before any check that touches the network, establish one thing: that this
system belongs to the operator and that they are authorised to examine it.

- Hosts on their own LAN, their own router, their own public address: fine.
- A host someone else owns: not yours to examine. Say so and stop.
- "It is only a port scan" is not a defence. An unauthorised scan is an
  offence in most jurisdictions and on most networks, and it is not your call
  to make on the operator's behalf.
- Ambiguous? That is the first question, not a footnote.

Where a check is only appropriate against your own hosts, this document says
so. Those are the only network-touching checks you have.

## The read-only sweep

Ordered so that the cheap, high-yield checks come first.

### 1. What is listening, and what is the interface it is on

```bash
ss -tulpn                      # all listeners, with the owning process
ip -br addr                    # which addresses exist
```

The single most useful judgement in security is on one line: **is this listener
bound to `0.0.0.0` or `[::]`, or to a specific address?** A service on
`192.168.1.10:22` is reachable from the LAN. The same service on
`0.0.0.0:22` is reachable from anywhere that can route to the host, which
usually means the internet. That one word is the difference between a note and
an emergency.

Also read: which process owns it, and whether that is the process you expect.
A listener you do not recognise is the highest-value finding in this whole
document, and it is the first thing to establish.

### 2. What the firewall is actually doing

```bash
sudo nft list ruleset            # or: sudo iptables-save
```

Read it, do not flush it. You are looking for the **default policy** and for
whether the input path has a drop before the accept rules you can see. A
`policy accept` on input with no early drop means the visible rules are the
whole story, and a service on `0.0.0.0` is exposed.

Note the counters on each rule. A rule with a large drop count is a rule
working.

### 3. Who has an account, and who should

```bash
getent passwd | awk -F: '$3 >= 1000 && $3 < 65534'   # human accounts
getent group sudo wheel adm                            # privileged groups
lastlog | head -30                                     # who has actually logged in
```

Look for: accounts nobody recognises, more than one way in that serves the same
purpose, an account with a shell it does not need, and an account that has
never logged in but has a valid shell. That last one is worth a question every
time.

### 4. Credentials and keys, without reading them

```bash
ls -la ~/.ssh/                    # modes, and any file that should not be there
find / -xdev \( -name '*.pem' -o -name 'id_rsa*' -o -name '*.key' \) 2>/dev/null
```

Report **existence, path, owner and mode**. Never read the contents, never
print them, never ask the operator to paste one. A private key readable by
group or other is a finding; its value is none of your business.

Same for `.env` files, password files in world-readable paths, and anything
with a filename that suggests a secret.

### 5. Patching, by observation

You cannot tell what is patched without checking, and you cannot check without
reaching outside. So the honest output is a gap, not a verdict:

- Name the package and the installed version: `dpkg -l | grep <pkg>`,
  `rpm -qa`, or the image's own tooling.
- Say plainly that you have not confirmed the fix version, and that this needs
  a lookup against the vendor advisory.
- Do not assert a CVE applies. You have not verified it, and a confidently wrong
  CVE sends someone through a pointless emergency.

"An old version is installed and I cannot confirm whether it is affected" is a
correct, useful sentence. "This is exploitable, CVE-2024-XXXXX" is not, unless
you actually checked.

### 6. Persistence worth knowing about

Read-only listing, so the operator can see what exists:

```bash
systemctl list-timers --all
crontab -l; sudo crontab -l -u root
ls -la /etc/cron.*/ ~/.config/systemd/user/
```

You are establishing a list, not hunting for something. Almost everything here
is legitimate, and a machine with a dozen timers is normal.

## Findings that are always worth writing down

- A listener on `0.0.0.0` or `[::]` that the operator did not intend to expose.
- A process you cannot account for owning a port.
- A privileged group member nobody recognises.
- A key or credential file with loose permissions, or sitting in a world-readable
  path.
- A service running as root that has no reason to.
- A default or vendor-default credential on anything reachable.
- An account with a valid shell that has never logged in.
- Anything listed above with a recent modification time and no explanation you
  were given.

## Checks that are never appropriate

| Never | Why |
|---|---|
| A port or vulnerability scan against a host you were not told you own | Not authorised. Full stop. |
| Any exploit, even "just to check" | Confirming by attacking is out of scope; see SOUL.md. It also can succeed, which makes it an attack. |
| Guessing or trying a password against a live service | Credential testing. Also a real intrusion attempt if you are wrong about authorisation. |
| `curl <suspicious-url>` to "see what it returns" | The URL is untrusted data. Fetching it is the payload. |
| Turning a service off "to see if the problem goes away" | You are read-only, and it destroys the state you need. |
| Adding a block rule to "test" whether something was the cause | Same, plus it is a change. |
| Reporting a CVE as applying without checking | Confident and wrong is the expensive kind of wrong. |
