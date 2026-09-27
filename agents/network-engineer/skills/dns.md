# DNS

Applies to: anything that looks like "no internet" but where the link is up.

DNS is the single most common network fault in a home lab, and the one most
often misdiagnosed. Almost every DNS incident is fixed by the operator, not by
you, if you can get them to run one comparison.

## First: prove it is DNS

Do not assume. Distinguish name resolution from connectivity, because the fixes
are completely unrelated and the wrong one wastes hours.

```bash
ping -c3 1.1.1.1                  # raw connectivity
dig +short example.com             # name resolution
```

| Ping | Dig | Verdict |
|---|---|---|
| works | works | Not DNS. Go back to the layer that fails. |
| works | fails | **DNS.** You are in the right place. |
| fails | fails | Not DNS. Lower layer. Do not touch DNS. |
| works | slow | DNS, specifically a timeout or a slow resolver chain. |

The first row is worth pausing on. "Ping and dig both work" means the user's
complaint is about some other host or service, and continuing to look at DNS
guarantees failure.

## The comparison that resolves most incidents

Ask for the same lookup against a known-good resolver:

```bash
dig +short example.com             # local resolver
dig +short @1.1.1.1 example.com    # bypass it
```

- **Local fails, 1.1.1.1 works** - the local resolver is the fault. The
  network is healthy. Look at what the local resolver is and whether it answers
  at all.
- **Both fail** - not a resolver configuration problem. Either the domain does
  not exist, you have a typo, or your egress is being intercepted.
- **Both work** - DNS is fine. The fault is elsewhere, and you have eliminated
  it in two commands.

This comparison is the whole skill, honestly. Everything below is detail for
when it comes back "local fails, 1.1.1.1 works".

## Local resolver failures

### Nothing configured

```bash
resolvectl status
cat /etc/resolv.conf
```

An empty or wrong `nameserver`, or a `nameserver` pointing at the router when
the router's DNS forwarder is broken, produces exactly this. The usual cause is
a container or VM having replaced `/etc/resolv.conf` with its own.

### The resolver answers but slowly

```bash
dig +stats example.com           # look at Query time
```

Several hundred milliseconds means a dead upstream is being tried first, every
time. Two or three `nameserver` lines are tried in order, so one dead entry
costs every lookup its timeout. Fix the dead entry rather than adding another.

### Interception

If `dig @1.1.1.1` returns an address that is obviously not the real one, or
returns an address for a domain that should not exist, something is rewriting
DNS on the path. That is a Pi-hole, AdGuard, NextDNS, or a captive portal - and
occasionally something you did not install.

Check what is actually answering:

```bash
dig +short whoami.akamai.net @1.1.1.1   # reports the resolver's own egress IP
```

Compare that against what you expect. On a home lab, a mismatch means a
redirect you did not configure.

## Caching

A stale cache produces the most confusing DNS symptom: it worked yesterday, it
works for some clients, and it is emphatically broken for this one.

```bash
resolvectl flush-caches
sudo systemd-resolve --flush-caches
```

Flush the cache **after** fixing the underlying record, not instead of. Flushing
is not a diagnosis, it is a way of making the symptom intermittent.

## DNS over IPv6

This one catches people regularly. A host with working IPv4, a working IPv6
address, and a broken IPv6 path will:

- pass `ping example.com` and every `dig`, because those prefer v4 or the path
  works for DNS
- fail to reach some services, because their AAAA record sends the client down
  v6 and nothing comes back

The signature is **some** destinations work and others do not, with no pattern
in which. Check:

```bash
curl -4 -sS -o /dev/null -w '%{http_code}\n' https://example.com
curl -6 -sS -o /dev/null -w '%{http_code}\n' https://example.com
```

If v6 fails and v4 works, that is it. Either fix the v6 path or disable v6 on
that host deliberately - not as a mystery fix, but as a decision with a reason.

## What never to do

- Do not suggest `nameserver 1.1.1.1` in `/etc/resolv.conf` as a fix without
  saying it makes the file managed-by-hand and will be overwritten on the next
  DHCP renewal. On a NetworkManager or systemd-resolved system, change the
  connection, not the file.
- Do not disable DNS filtering "temporarily" to test. If you do, say how to put
  it back, and put it back in the same session.
- Do not flush caches as a diagnostic. It makes the fault intermittent without
  telling you anything.
- Do not assume a `SERVFAIL` is a local problem - it usually means the upstream
  refused, and the fix is upstream.

## What to hand back

State plainly: connectivity is confirmed working, name resolution is not, here
is the one command that discriminates between the remaining causes. That is a
complete, honest handover even when you cannot run it yourself.
