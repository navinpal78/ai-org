# Layered diagnosis

Applies to: any network fault.

Work from the bottom up and **stop at the first layer that fails**. Everything
above a broken layer is a symptom, and diagnosing symptoms is how people end up
reconfiguring a firewall when the switch is unplugged.

The order matters more than the individual checks. Running the top layer first
is how a DNS problem turns into an hour of blaming the router.

---

## Layer 0 - Physical / link

Is there a signal at all? Check before assuming anything above it works.

```bash
ip -br link                 # every interface, and its state
ethtool eth0 2>/dev/null    # negotiated speed, duplex, link detect
```

What a failure looks like: `NO-CARRIER`, `LOWER_UP` absent, speed 0, or duplex
half. On wireless, no SSID association or a very low signal level.

If the link is down, **nothing above this matters.** Stop.

**Full-duplex mismatch** is a genuine fault that looks like a config problem:
one side negotiated half-duplex, and throughput collapses in one direction while
ping looks fine. `ethtool` reports it directly.

---

## Layer 1 - Addressing

Does the interface have the address it should?

```bash
ip -br addr
ip -br link                 # look for 169.254.x.x - that is APIPA
```

`169.254.0.0/16` means DHCP failed and the host self-assigned. It cannot reach
anything, and it is a clean, unambiguous finding - go fix DHCP, not DNS.

For a static address, check for a duplicate. Two hosts with the same address
produces intermittent, maddening faults that look like packet loss:

```bash
arping -D -I eth0 192.168.1.50     # duplicate address detection
ip neigh show                      # learned neighbours
```

---

## Layer 2 - Routing

Can it reach the next network?

```bash
ip route                     # is there a default route at all
ip route get 1.1.1.1         # which interface and source would be used
ping -c3 <next-hop>          # is the next hop reachable
```

`ip route get` is the underused command here. It answers "which way would
traffic to this address actually go", which distinguishes a routing problem from
a policy or firewall problem immediately.

A host with an address but no default route can reach its own subnet and nothing
else - a very common DHCP failure, and it presents as "the internet is dead".

---

## Layer 3 - Transport

Is the port reachable, or just the host?

```bash
ping -c3 1.1.1.1             # host reachable, ICMP specifically
ss -tlnp                     # what is actually listening, locally
nc -zv <host> <port>         # is that port open
traceroute 1.1.1.1
```

`ping` succeeding does not mean TCP works, and `ping` failing does not mean the
host is down - ICMP is frequently rate-limited or blocked. If ping fails, confirm
with a TCP test before concluding anything.

**MTU** shows up here as "ping works, everything else does not":

```bash
ping -M do -s 1472 1.1.1.1   # 1472 + 28 bytes = 1500
```

Success means the full-size packet fits. `message too long` means the path MTU
is lower, and you binary-search downward. The tell for the user is that small
pings succeed while web pages hang on loading.

---

## Layer 4 - Name resolution

Only now. If the layers below work, the network is fine and the fault is DNS.

```bash
resolvectl status             # or: cat /etc/resolv.conf
dig <name>                    # authority and answer sections
dig @1.1.1.1 <name>          # bypass the local resolver
```

The comparison that matters is the third command: if the name resolves against
1.1.1.1 but not against the local resolver, the network is healthy and the
resolver is the fault. That one comparison resolves most DNS incidents.

Read `skills/dns.md`.

---

## Layer 5 - Application

Only if the port is open and the name resolves. A refused connection
(`connection refused`) is a working network with nothing listening. A timeout is
usually a firewall dropping the packet. A reset is usually the service refusing
on a specific condition. These are different faults with the same symptom from
the browser, and you cannot tell them apart without looking.

---

## Working with the operator

You cannot run any of this yourself - you have no access to their machine. Your
first job is often to get the output:

- Ask for **one command at a time**, and say what each answer rules out. Ten
  commands at once gets you ten unhelpful answers.
- Say which layer you are testing and why you stopped lower down. The operator
  needs to know the fault is above the physical layer, or they will keep
  checking cables.
- When a check comes back clean, say so explicitly and what it eliminated. That
  is what lets them stop looking.

## When the evidence stops

Say what you have ruled out, what remains, and what single check would
discriminate between the remaining causes. Then hand it to whoever can run it,
rather than guessing a third cause.
