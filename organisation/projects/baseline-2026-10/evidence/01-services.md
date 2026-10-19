# Evidence 01 — Services and listening ports
Captured 2026-10-20T01:43:58+08:00 on aipind by CEO (read-only). Supersedes the 01:38 capture.
Long command lines are truncated to 160 characters for readability.

## systemd units matching ai/ollama/opencode/hermes/ceo/gateway
  ollama.service                                                                            loaded    active   running Ollama Service

## systemd unit files (enabled state)
ollama.service                               enabled         enabled

## ollama service environment
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin
OLLAMA_CONTEXT_LENGTH=65536
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1

## listening TCP sockets
ADDRESS:PORT | PROCESS | SCOPE
127.0.0.54:53 | (not shown) | localhost
0.0.0.0:22 | (not shown) | NON-LOCAL
127.0.0.53%lo:53 | (not shown) | localhost
127.0.0.1:54329 | users:(("postgres",pid=55489,fd=8)) | localhost
127.0.0.1:3100 | users:(("MainThread",pid=55438,fd=32)) | localhost
127.0.0.1:11434 | (not shown) | localhost
127.0.0.1:35287 | (not shown) | localhost
100.100.168.107:46303 | (not shown) | NON-LOCAL
127.0.0.1:49374 | users:(("opencode",pid=64465,fd=10)) | localhost
[::]:22 | (not shown) | NON-LOCAL
[fd7a:115c:a1e0::d335:a86c]:58875 | (not shown) | NON-LOCAL

## AI-related processes (PID / PPID / UPTIME / RSS-KB / COMMAND, truncated)
   7399    1669    10:59:09 235068 /home/baba/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3 -I -c import os, re, sys import contextlib, hashlib, io
  47603   42189    02:37:07 30364 ollama run qwen3:8b
  52822       1    01:49:01 35628 /usr/local/bin/ollama serve
  62648   52822       17:43 2546988 /usr/local/lib/ollama/llama-server --model /usr/share/ollama/.ollama/models/blobs/sha256-02d45dc1cf451ba2475ac33b301c2dd8f98
  64465       1       08:16 268884 /home/baba/.opencode/bin/opencode serve --service
  66110   65582       01:06  7872 timeout 420 opencode run --agent cto Carry out the sub-task defined in organisation/projects/baseline-2026-10/tasks/02-agents.
  66111   66110       01:06 106304 opencode run --agent cto Carry out the sub-task defined in organisation/projects/baseline-2026-10/tasks/02-agents.md. Read th

## services/ directory
services/:
total 16
drwxr-xr-x  4 baba baba 4096 Oct  1 23:57 .
drwxr-xr-x 18 baba baba 4096 Oct 19 15:15 ..
drwxr-xr-x  2 baba baba 4096 Oct  1 23:10 ceo
drwxr-xr-x  3 baba baba 4096 Oct  2 23:03 ceo-gateway

services/ceo:
total 12
drwxr-xr-x 2 baba baba 4096 Oct  1 23:10 .
drwxr-xr-x 4 baba baba 4096 Oct  1 23:57 ..
-rwxr-x--- 1 baba baba 3599 Oct 19 14:39 bootstrap.sh

services/ceo-gateway:
total 40
drwxr-xr-x 3 baba baba 4096 Oct  2 23:03 .
drwxr-xr-x 4 baba baba 4096 Oct  1 23:57 ..
drwxr-xr-x 2 baba baba 4096 Oct  2 14:48 __pycache__
-rwxr-x--- 1 baba baba 7121 Oct  2 23:03 gateway.py
-rwxr-x--- 1 baba baba 4689 Oct  2 14:30 gateway.py.backup-20261002-143043
-rwxr-x--- 1 baba baba 7641 Oct  2 14:42 gateway.py.backup-before-prompt-20261002-144211
-rwxr-x--- 1 baba baba 2650 Oct  1 23:58 setup-telegram.sh

services/ceo-gateway/__pycache__:
total 20
drwxr-xr-x 2 baba baba 4096 Oct  2 14:48 .
drwxr-xr-x 3 baba baba 4096 Oct  2 23:03 ..
-rw-r----- 1 baba baba 9987 Oct  2 14:48 gateway.cpython-314.pyc

## Process identification notes (CEO annotation)

| PID | PPID | Uptime | Program | Final arguments |
|---|---|---|---|---|
| 7399 | 1669 | 10:59:22 | `python3` | `sys.exit(main()) gateway run` |
| 47603 | 42189 | 02:37:20 | `ollama` | `run qwen3:8b` |
| 52822 | 1 | 01:49:14 | `ollama` | `serve` |
| 62648 | 52822 | 17:56 | `llama-server` | `--context-shift --keep 4` |
| 64465 | 1 | 08:29 | `opencode` | `serve --service` |
| 66110 | 65582 | 01:19 | `timeout` | `its rules strictly.` |
| 66111 | 66110 | 01:19 | `opencode` | `its rules strictly.` |

Notes:
- The long `python3 -I -c ...` process is the **Hermes agent**; its final argument is `gateway run`, i.e. the CEO Telegram gateway. Its inlined source is omitted here for readability.
- `opencode run --agent cto ...` processes are the CEO's own baseline sub-task invocations running at capture time. They are transient and not part of the standing service set.
