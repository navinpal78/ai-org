# Agent Registry

| Agent | Definition | State | Runtime | Model |
|---|---|-------|---------|-------|
| CEO | agents/ceo/ | ACTIVE | Hermes Agent | Current approved model |
| CEO (local) | agents/ceo-local/ | INSTANTIATED / ACTIVE | OpenCode | qwen3.5:9b (served by Ollama, local) |
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
| 2 | `paperclipai.service` inherits only the systemd default `PATH`, which excludes `~/.opencode/bin`. Agent runs fail with `Command not found in PATH: "opencode"`. | **Fixed 2026-10-20 02:46 UTC** — drop-in at `~/.config/systemd/user/paperclipai.service.d/10-agent-runtime-path.conf`, applied when the owner restarted `paperclipai`. Verified: the live unit `PATH` now begins with `/home/baba/.opencode/bin`. |
| 3 | A run attempt that dies leaves its `opencode serve --service` process orphaned (reparented to `systemd`, still holding port 49374). The CLI does not track adapter-spawned servers, so `opencode service status` reports `stopped` and `opencode service stop` is a no-op. Every later attempt spawns a fresh server, collides, and leaks another orphan — a self-sustaining cascade. | **Cleared, but can recur.** Remedy is `pkill -f 'opencode serve'`, then re-queue the task. Note this is the true cause of fault 1; the `opencode.service` unit was only one way of triggering it. Starting a server manually triggers it too. |
| 4 | `qwen3.5:9b` could not close its own task loop even though it had a working `shell` tool. It used `shell` once (`ollama ps`), then hallucinated a `tools.paperclip.comment_issue(...)` namespace inside the `execute` JS evaluator, called it with Python kwarg syntax, and concluded *"Cannot execute shell commands directly"* — which was false. It asked for manual intervention instead. | **Fixed by prompt.** Sarpanch's instructions now name `shell` explicitly, state that `execute` is a JS evaluator with no `fetch`/`process`/`tools.paperclip`, and give the literal `curl` commands for posting a comment and PATCHing status with `statusVersion`. PIN-5 then self-closed on the next run. |

Fault 2 could not be worked around from inside an agent: Paperclip refuses to let agent API keys
set the host-executed adapter settings `command`, `env` or `cwd`, and no directory on the
service `PATH` is user-writable. It needed the owner to restart the host service.

Fault 4 is the important one for anyone adding local agents. A small local model will not
discover its own capabilities by reasoning about them; stating a principle like "close your own
loop" is not enough. Give it the exact command. The runtime was never the limitation here.

### Fault 4 fix applied to the CTO, 2026-10-20

The same prompt fix was applied to Chalaak, and a **second, independent cause** was found while
applying it: Chalaak's adapter config carried `dangerouslySkipPermissions: false`. For
`opencode_local` this field defaults to `true` for unattended runs; set to `false` it leaves the
run waiting on approval prompts that nobody can answer headlessly. So the CTO had both no
mechanism *and* no permission. Instructions alone would not have fixed it.

Both were changed: the instructions now carry the `shell`/`execute` section and the literal
`curl` commands, and `dangerouslySkipPermissions` is `true`. This widens the CTO's filesystem
and shell reach to match the CEO's; revert with a PATCH to `/api/agents/<id>` setting it back to
`false`, at the cost of the CTO again being unable to record its own work.

Verified by PIN-6, not assumed: Chalaak posted its own findings (`qwen3.5:9b`, `hostname` =
`aipind`) and set the issue to `done` itself, 2026-10-20 03:31 UTC. It omitted the memory figure
the task asked for — the same over-literal template-following seen in Sarpanch's
`$PAPERCLIP_RUN_ID` slip. Expect small local models to drop details, not to invent them.

## Hermes — second free runtime (PIN-4, 2026-10-20)

`~/.hermes/config.yaml` points at local Ollama: `model.provider: custom`, `model.base_url:
http://127.0.0.1:11434/v1`, `model.default: qwen3.5:9b`, plus a named `providers.ollama-local`
entry. No paid credentials are configured in it; `auth.json` has no providers.

`hermes-gateway.service` was restarted onto the repaired environment 2026-10-20 11:22 +08 at the
owner's instruction. Nothing was lost: the gateway logged "No messaging platforms enabled" both
before and after, so no messaging connections existed to drop.

**Verified working, 2026-10-20.** With `HERMES_HOME=/home/baba/.hermes` set, `hermes status`
reports `Model: qwen3.5:9b`, `Provider: custom`, `Providers: ollama-local`, and a one-shot
`hermes -z "..." --yolo chat` completed a real tool call. Its terminal tool runs **locally** —
it returned `hostname` = `aipind` and reached the Paperclip API on `127.0.0.1:3100` (HTTP 401
without a key, which is the correct response). So a Hermes-backed Paperclip agent could close
its own loop the same way Sarpanch and Chalaak now do.

**The trap, and it is a costly one.** Paperclip agent runs execute with `HOME` set to a
per-run sandbox (`/tmp/paperclip-ai-.../`), so `~/.hermes` does not resolve to the real config.
`hermes doctor` then reports *"config.yaml not found (using defaults)"* and *"~/.hermes/.env
file missing"*, and Hermes auto-detects a provider from the environment instead. In a Paperclip
run that environment contains `ANTHROPIC_API_KEY`, so Hermes silently routed to **Anthropic** —
an agent configured as "free" would have billed a paid key. Observed directly: `hermes status`
showed `Provider: Anthropic`, `Model: (not set)`.

This also explains an earlier wrong conclusion recorded against this install. `hermes pm repair`
appearing not to "hold" between runs was not a Hermes fault — each sandboxed run gets a fresh
`HOME` and restages its runtime venv there. The repair did hold for the real home.

Wiring Hermes to a Paperclip agent therefore needs, at minimum:

- `adapterConfig.env = {"HERMES_HOME": "/home/baba/.hermes"}` — **mandatory**, not optional;
  without it the agent is neither local nor free.
- `model` and `provider` left blank so Hermes uses its own configured default. The adapter's
  documented `provider` list (auto, openrouter, nous, openai-codex, zai, kimi-coding, minimax,
  minimax-cn) has no `custom`/local value, so naming one is not possible — omission is the route.
- a `--yolo` equivalent via `extraArgs`, and `toolsets` including `terminal`, for headless runs.

**Open blocker:** `env` is one of the host-executed adapter settings (`command`, `env`, `cwd`)
that Paperclip refuses to let an agent API key set — the same restriction that blocked fault 2.
Creating a Hermes-backed agent needs the owner or board to set `env`, or it will run against
Anthropic. Until then Hermes is a proven free runtime but not a wired one.

## State Definitions

DEFINED = role/capability specification exists.

APPROVED = Owner has authorised instantiation.

INSTANTIATED = an operational instance exists.

ACTIVE = instance is currently authorised to operate.

SUSPENDED = instance exists but is not currently operating.

RETIRED = instance is no longer operational.
