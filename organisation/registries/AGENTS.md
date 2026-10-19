# Agent Registry

| Agent | Definition | State | Runtime | Model |
|---|---|-------|---------|-------|
| CEO | agents/ceo/ | ACTIVE | Hermes Agent | Current approved model |
| CTO | agents/cto/ | INSTANTIATED / ACTIVE | OpenCode | qwen3.5:9b (served by Ollama, local) |

No other specialist agent is currently instantiated.

## Control-plane registration

Agents are defined here and executed by a runtime. Separately, they may be registered in the
Paperclip control plane, which owns task assignment, approvals and audit trail.

| Agent | Paperclip agent | Registered | Adapter |
|---|---|---|---|
| CEO | `Wadda Baba Pro` (`883878b7-37a1-4284-8cb6-b7643719b569`) | yes | `claude_local` |
| CTO | `Chalaak` (`f7382c75-8349-4fc4-83af-cd12f83c3089`, `/agents/chalaak`) | yes, 2026-10-20 | `opencode_local`, `ollama/qwen3.5:9b` |

Before 2026-10-20 the CTO existed only here and was reached by invoking OpenCode directly, so
its task state and approvals lived outside Paperclip. That is now closed.

**Known limitation.** Chalaak is hired with `dangerouslySkipPermissions: false`, giving it
read-only defaults per §12.4 of the approved specification. Shell access auto-rejects, so it
can perform and report work but **cannot record its own Paperclip task disposition** — the
lifecycle is driven through API calls that need a shell. Until that is decided, the CEO closes
out Chalaak's tasks. Verified by smoke test PIN-3 on 2026-10-20.

## State Definitions

DEFINED = role/capability specification exists.

APPROVED = Owner has authorised instantiation.

INSTANTIATED = an operational instance exists.

ACTIVE = instance is currently authorised to operate.

SUSPENDED = instance exists but is not currently operating.

RETIRED = instance is no longer operational.
