# Evidence 02 — Runtimes, models, dependencies and configuration
Captured 2026-10-20T01:39:02+08:00 on aipind by CEO (read-only). Corrected 01:57.

**Correction notice.** The original capture recorded Hermes as `no dependency environment is
committed for this install; run hermes pm repair`. That is wrong. Re-run from a clean login
shell, Hermes reports **v0.22.2, stable, up to date**. The failure was an artefact of the
environment the capture was taken in, not of the Hermes install. The line below has been
replaced with the clean-shell result.

**Caveat that follows from this:** these captures were taken from a shell that overrides
configuration for locally installed tools. Any statement here about the *health* of a local
runtime must be re-checked from an ordinary login shell before it is trusted. Statements about
hardware, file contents and process lists are unaffected.

## Versions
opencode: opencode v2.0.32
ollama:   ollama version is 0.40.5
hermes:   Hermes Agent v0.22.2 (2026.9.24) · stable · local d923a5eb487a · Python 3.14.7 · OpenAI SDK 2.24.0 · Up to date
python3:  Python 3.14.4
git:      git version 2.53.0
node:     v24.22.0

## Ollama models installed
NAME          ID              SIZE      MODIFIED    
qwen3:8b      500a1f067a9f    5.2 GB    3 hours ago    
qwen3.5:9b    56671c2ab938    6.6 GB    3 days ago     

## Ollama models currently resident
NAME          ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL               
qwen3.5:9b    56671c2ab938    6.9 GB    100% GPU     65536      llamacpp    27 minutes from now    

## Ollama model store size
11G	/usr/share/ollama/.ollama/models

## GPU
name, memory.total [MiB], memory.used [MiB], driver_version
NVIDIA GeForce RTX 3060, 12288 MiB, 7613 MiB, 595.99.02

## Memory
               total        used        free      shared  buff/cache   available
Mem:            15Gi       3.9Gi       514Mi       186Mi        11Gi        11Gi
Swap:          4.0Gi       117Mi       3.9Gi

## Disks
NAME                        SIZE TYPE MOUNTPOINT
loop0                       1.5M loop /snap/hwctl/123
loop1                      66.8M loop /snap/core24/1643
loop2                       1.5M loop /snap/hwctl/131
loop3                      50.1M loop /snap/snapd/27710
loop4                      44.7M loop /snap/snapd/28254
loop5                      66.8M loop /snap/core24/2124
loop6                      33.5M loop /snap/tailscale/169
nvme0n1                   953.9G disk 
├─nvme0n1p1                   1G part /boot/efi
├─nvme0n1p2                   2G part /boot
└─nvme0n1p3               950.8G part 
  └─ubuntu--vg-ubuntu--lv   100G lvm  /
Filesystem                         Size  Used Avail Use% Mounted on
/dev/mapper/ubuntu--vg-ubuntu--lv   98G   33G   61G  35% /
/dev/mapper/ubuntu--vg-ubuntu--lv   98G   33G   61G  35% /

## OpenCode config (~/.config/opencode/opencode.json)
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama Local",
      "options": {
        "baseURL": "http://127.0.0.1:11434/v1"
      },
      "models": {
        "qwen3.5:9b": {
          "name": "Qwen 3.5 9B (Local)",
          "limit": {
            "context": 65536,
            "output": 8192
          }
        }
      }
    }
  },
  "model": "ollama/qwen3.5:9b"
}

## OpenCode service status (clean login environment)
http://127.0.0.1:49374

## Disk allocation note (CEO annotation)

`lsblk` above shows `nvme0n1p3` is a **950.8 G** partition, but the logical volume mounted at
`/` is only **100 G** (98 G filesystem, 33 G used, 61 G available, 35%). The remaining ~850 G
of that partition is not mounted anywhere.

`vgs`, `lvs` and `pvs` require root and returned nothing, so whether that space is free volume
group capacity or unallocated cannot be confirmed from here. **OPEN QUESTION for the Founder.**

Practical consequence: usable space today is **61 G**, not 954 G. The Ollama model store
already occupies 11 G of it.
