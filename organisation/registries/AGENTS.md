# Agent Registry

| Agent | Definition | State | Runtime | Model |
|---|---|-------|---------|-------|
| CEO | agents/ceo/ | ACTIVE | Hermes Agent | Current approved model |
| CEO (local) | agents/ceo-local/ | INSTANTIATED / PENDING FIRST RUN | OpenCode | qwen3.5:9b (served by Ollama, local) |
| CTO | agents/cto/ | INSTANTIATED / ACTIVE | OpenCode | qwen3.5:9b (served by Ollama, local) |

No other specialist agent is currently instantiated.

## Control-plane registration

Agents are defined here and executed by a runtime. Separately, they may be registered in the
Paperclip control plane, which owns task assignment, approvals and audit trail.

| Agent | Paperclip agent | Registered | Adapter |
|---|---|---|---|
| CEO | `Wadda Baba Pro` (`883878b7-37a1-4284-8cb6-b7643719b569`) | yes | `claude_local` |
| CEO (local) | `Sarpanch` (`5ef59234-b772-49b6-87f1-913a27676915`, `/agents/sarpanch`) | yes, 2026-10-20 | `opencode_local`, `ollama/qwen3.5:9b` |
| CTO | `Chalaak` (`f7382c75-8349-4fc4-83af-cd12f83c3089`, `/agents/chalaak`) | yes, 2026-10-20 | `opencode_local`, `ollama/qwen3.5:9b` |

Before 2026-10-20 the CTO existed only here and was reached by invoking OpenCode directly, so
its task state and approvals lived outside Paperclip. That is now closed.

`Sarpanch` is the zero-marginal-cost CEO hired under PIN-4. It runs the same local model as the
CTO, so its token usage is free; the practical limits are context window and local inference
speed, not spend. It is hired with `dangerouslySkipPermissions: true` specifically so it can
record its own task disposition — the gap that parked PIN-3.

## Local-adapter runtime faults found 2026-10-20 (PIN-4)

The overnight systemd cutover left two faults that broke **every** `opencode_local` agent,
including the CTO. Both were found by direct test, not inspection.

| # | Fault | Status |
|---|---|---|
| 1 | `opencode.service` ran `opencode serve --service` on the managed-service port, but the CLI did not recognise it (`opencode service status` → `stopped`). Every `opencode run` then died with "port 49374 already in use". | **Fixed** — unit stopped and disabled. The CLI starts and owns its own managed service on demand, on the same port, so the web UI is unaffected. |
| 2 | `paperclipai.service` inherits only the systemd default `PATH`, which excludes `~/.opencode/bin`. Agent runs fail with `Command not found in PATH: "opencode"`. | **Fix staged, not yet applied** — drop-in written at `~/.config/systemd/user/paperclipai.service.d/10-agent-runtime-path.conf` and loaded by `daemon-reload`. It takes effect on the next restart of `paperclipai` or at next boot. |

Fault 2 cannot be worked around from inside an agent: Paperclip refuses to let agent API keys
set the host-executed adapter settings `command`, `env` or `cwd`, and no directory on the
service `PATH` is user-writable.

## State Definitions

DEFINED = role/capability specification exists.

APPROVED = Owner has authorised instantiation.

INSTANTIATED = an operational instance exists.

ACTIVE = instance is currently authorised to operate.

SUSPENDED = instance exists but is not currently operating.

RETIRED = instance is no longer operational.
