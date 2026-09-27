# Firewall and network exposure

`scripts/10-ollama.sh` configures the model server to listen on `0.0.0.0`, so
other machines in your house can reach it. That is the point of the design -
one graphics card, several agent machines - but it also means anything else on
your network can reach it, including a phone on guest WiFi.

Read this once, then pick a level.

---

## Level 1: leave it open (home network, low risk)

Do nothing. The default is already reachable by every device on your LAN.

Acceptable when: you have a home network you control, no guests on WiFi, and
nothing on that network is compromised.

Not acceptable when: you share a building, run guest WiFi, or have IoT devices
you do not trust. Guest devices on the same network can reach a service on the
main LAN subnet, because guest networks usually still route to the router.

---

## Level 2: restrict to your LAN subnet (recommended)

Allow the port, but only from addresses on your own network. This is the setting
for almost everyone.

```bash
# Replace 192.168.1.0/24 with your own subnet. Check with: ip route
sudo ufw allow from 192.168.1.0/24 to any port 11434 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 3000  proto tcp

sudo ufw enable
sudo ufw status numbered
```

To find your subnet:

```bash
ip route | grep default
```

`192.168.1.5 dev wlan0` means you are on `192.168.1.0/24`.

---

## Level 3: bind to a specific interface

If the machine has more than one network connection - for example Ethernet on
the LAN and WiFi on something else - bind the server to only the one you want
it reachable on.

```bash
sudo systemctl edit ollama
```

```ini
[Service]
Environment="OLLAMA_HOST=192.168.1.50:11434"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

Replace `192.168.1.50` with the static IP of that machine. This is worth doing
anyway: assign a static address in your router so it does not change.

---

## Level 4: do not expose it at all

If you only have one machine and never connect from elsewhere, bind to
localhost and skip every firewall rule.

```bash
sudo systemctl edit ollama
```

```ini
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

---

## What is actually at risk if it is open

Nothing dramatic, but worth being accurate about:

- **No authentication by default.** Anyone who can reach the port can run any
  model you have downloaded, and use your GPU. If someone pointed a script at
  it, you would be paying for it in electricity and wearing out the card.
- **Models are readable.** The files Ollama has downloaded can be fetched
  through the API. If you have fine-tuned anything proprietary on that
  machine, this is the relevant risk.
- **It is not remote-accessible.** `0.0.0.0` means every interface, but your
  home router's NAT still means the internet cannot reach it unless you have
  port-forwarded, which you have not. Do not port-forward 11434.
- **Compute, not code execution.** The model server does not run what the model
  writes. An agent with a shell tool can, but that is the agent's
  `AGENT_SAFETY`, not this port.

---

## The web interface

`scripts/30-openwebui.sh` serves the browser UI on port 3000. It has its own
login, and the first account you create is the administrator - so create it
immediately, before anyone else reaches the port.

It also writes to the Ollama API, so it needs the model server to be
reachable. Same firewall considerations apply, and it is the port worth
protecting more carefully, because it is a full web application rather than
one endpoint.

---

## Checking what you ended up with

```bash
ss -tlnp | grep -E '11434|3000'          # which addresses are listening
sudo ufw status                          # which rules are active
curl -s http://127.0.0.1:11434/api/tags > /dev/null && echo "local OK"
```

From another machine on the LAN:

```bash
curl -s http://192.168.1.50:11434/api/tags > /dev/null && echo "LAN OK"
```

And from a machine that should *not* have access:

```bash
curl -s --max-time 3 http://192.168.1.50:11434/api/tags || echo "correctly blocked"
```

That last one is the test that matters. A rule you have not verified is a rule
you are assuming.
