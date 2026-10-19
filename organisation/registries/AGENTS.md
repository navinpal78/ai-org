# Agent Registry

| Agent | Definition | State | Runtime | Model |
|---|---|-------|---------|-------|
| CEO | agents/ceo/ | ACTIVE | Hermes Agent | Current approved model |
| CTO | agents/cto/ | INSTANTIATED / ACTIVE | OpenCode | qwen3.5:9b (served by Ollama, local) |

No other specialist agent is currently instantiated.

## State Definitions

DEFINED = role/capability specification exists.

APPROVED = Owner has authorised instantiation.

INSTANTIATED = an operational instance exists.

ACTIVE = instance is currently authorised to operate.

SUSPENDED = instance exists but is not currently operating.

RETIRED = instance is no longer operational.
