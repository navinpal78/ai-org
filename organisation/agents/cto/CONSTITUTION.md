# CTO — INSTANTIATION RECORD

## Status
- **Definition:** DEFINED (role specification exists)
- **Approval:** APPROVED (Owner approved YELLOW-level instantiation)
- **Instance:** INSTANTIATED
- **Runtime:** OpenCode
- **Model:** qwen3.5:9b (served by Ollama, local)
- **Active:** YES

## Instantiated Date
2026-10-03

## Authorised Authority
CEO acting within delegated authority per CEO Constitution and Owner approval.

## Scope of Authority
As defined in `organisation/agents/cto/ROLE.md`:
- GREEN: research, analysis, planning, documentation, code inspection, testing
- YELLOW: infrastructure changes, permission changes (requires Owner approval)
- RED: destructive operations, significant external spending (requires explicit Owner authority)

## Runtime Configuration
| Attribute | Value |
|-----------|-------|
| Runtime | OpenCode |
| Working Directory | /home/baba/AI (host `aipind`) |
| File Access | organisation/ root and subdirectories |
| Shell Execution | Yes (GREEN tasks) |

## Model Configuration
| Attribute | Value |
|-----------|-------|
| Model | qwen3.5:9b (`ollama/qwen3.5:9b`, served locally by Ollama on 127.0.0.1:41825) |
| Strategy | LOCAL → HYBRID → EXTERNAL |
| Selected by | `~/.config/opencode/opencode.json` (`"model": "ollama/qwen3.5:9b"`), reinforced by a `model:` pin in `.opencode/agents/cto.md` |
| Known failure mode | If that config is not loaded, OpenCode silently falls back to a hosted free model and work leaves the machine. Verify the model name printed in the run header. |

## Tools Granted
- File read/write (organisation/ directory)
- Shell command execution (GREEN tasks only)
- Registry updates (AGENTS.md, CAPABILITIES.md)
- Knowledge file access/creation

## Dependencies
None beyond CEO operational state.

## Testing Requirements
1. Can read organisational files
2. Can write to designated output locations
3. Adheres to governance boundaries
4. Produces outputs in correct format

## Retirement Conditions
CTO may be retired or modified when:
- Organisational objectives change significantly
- CTO capability is consolidated elsewhere (e.g., CEO)
- Runtime changes make current configuration unsuitable

## Review Requirements
- Periodic review of workload justification
- Verification that CTO tasks warrant separation from CEO

---

**This record confirms the CTO agent instance is now authorised to operate within the defined governance framework.**
