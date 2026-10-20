# Ollama service configuration

## Why this exists

Five `OLLAMA_*` variables on this machine are deliberately tuned. One that
matters was never set: `OLLAMA_KEEP_ALIVE`. Without it Ollama applies its
5-minute idle default and fully evicts the model from VRAM between tasks, so
the next request pays a cold 6.9 GB reload before it can start thinking.

Measured on 2026-10-20, same prompt, same agent, local model:

| Condition | Wall time |
|-----------|-----------|
| Model evicted (cold) | **98 s** |
| Model resident (warm) | **38 s** |

About **60 seconds of every task** was reload, not work. This is the most
likely explanation for the "historical CEO runtime performance issues" lead
recorded in the approved workflow specification.

## Current state

`override.conf` in this directory is the intended file. It is the live
configuration as of 2026-10-20 **plus** the `OLLAMA_KEEP_ALIVE=30m` line.

**It is not installed.** Writing to `/etc/systemd/system/` requires root, and
the CEO runs without passwordless sudo. The Founder must apply it.

An equivalent effect was being held in place at runtime by loading the model
with an explicit `keep_alive`. **That has already lapsed** — checked
2026-10-20 08:00, `ollama ps` is empty and the live unit environment still has
no `OLLAMA_KEEP_ALIVE`, so every task is paying the cold reload again. This is
exactly why the runtime hack was never the answer: it does not survive, and it
expires quietly. The systemd change is the durable fix.

## Install (requires root)

**Preferred, as of 2026-10-20:** this is now step 1 of
[`../root-access/grant-scoped-root.sh`](../root-access/grant-scoped-root.sh),
which applies it with a backup and a verification step, and also installs the
scoped sudo list the Founder approved:

```bash
sudo bash /home/baba/AI/infrastructure/root-access/grant-scoped-root.sh
```

The equivalent by hand:

```bash
sudo install -m 644 -o root -g root \
  /home/baba/AI/infrastructure/ollama/override.conf \
  /etc/systemd/system/ollama.service.d/override.conf

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

## Verify

```bash
systemctl show ollama --property=Environment | tr ' ' '\n' | grep KEEP_ALIVE
```

Expected: `OLLAMA_KEEP_ALIVE=30m`.

Then send any request and check the eviction deadline moves out to 30 minutes:

```bash
ollama ps
```

## Roll back

A copy of the previous file is at
`/etc/systemd/system/ollama.service.d/override.conf.backup`. Restore it and
run `sudo systemctl daemon-reload && sudo systemctl restart ollama`.

## Choosing the value

`30m` keeps the model resident across a working session without holding VRAM
overnight. Use `-1` to keep it loaded indefinitely — only if nothing else on
this machine needs the 12 GB card, which is not currently true: roughly
8 GB of GPU memory was already in use by other workloads when measured.

Restarting Ollama evicts the model, so the first task after the restart will
pay the cold cost once. That is expected.
