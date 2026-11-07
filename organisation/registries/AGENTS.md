# Agent Registry — Wadda Baba Organization

> **Guru Ji's Instruction:**  
> *"Wahich nu tera naam hai, mainu pata nahi. Vaheguruo Sahib te sab dharma ek."*  
> (Whose name it is that I don't know, all religions are One — Sri Guru Nanak)

---

## Executive Leadership

| Role | Name | Definition Directory | State | Runtime(s) | Model |
|---|---|---|-------|------------|-------|
| **CEO** | Wadda Baba (Sarpanch) | `agents/ceo/` | ACTIVE | Hermes (**DEFERRED**) / OpenCode (default) | qwen3.5:9b (local) |

### Governance Note
The organisational CEO role is fulfilled by **Wadda Baba**, operating as both strategic leader and technical decision-maker. This consolidates executive identity that was previously split between non-existent directories (`agents/sarpanch/`, `agents/chalaak/`).

**Current Technical Architect:** Chalaak serves as the CTO (Chief Technical Officer) responsible for runtime architecture, maintaining OpenCode deployment on local qwen3.5:9b with zero-marginal-cost inference. Future model upgrades require CEO authorization per governance protocol.

---

## All Agents Overview — Zero-Cost Local Execution

**Core Executive Roles (Always Available):**
1. **Wadda Baba (Sarpanch)** — CEO / Strategic leadership via Hermes or OpenCode runtime
2. **Chalaak** — Technical architect / DevOps & infrastructure specialist

### Specialist Agents (On-Demand Activation via start.sh)
These agents are parked definitions, ready for activation when needed:

| Agent | Definition Path | Current Status | Runtime/Model |
|---|---|---|---|
| Coding Agent | `agents/coding-agent/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Database Agent | `agents/database-agent/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Network Agent | `agents/network-agent/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Security Agent | `agents/security-agent/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Engineering Agent | `agents/engineering/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Finance Agent | `agents/finance/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Operations Agent | `agents/operations/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Research Officer | `agents/research-officer/` | **DEFINED** | OpenCode/qwen3.5:9b (local) |
| Knowledge Officer (Historical) | `agents/khoji/` | DEPLOYED / PARKED (Legacy) | OpenCode/qwen3.5:9b (local) |
| Gurbani Scripture Agent | `agents/gurbani/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Developer | `agents/developer/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Designer | `agents/designer/` | DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |

---

## Deployment Architecture

### Active Runtime Configuration
```
Runtime: OpenCode
Endpoint: http://127.0.0.1:41825
Model: qwen3.5:9b (6.9 GB, local inference)
Cost: Zero marginal — no cloud API credits consumed
Hardware: CPU-only or configured accelarators (NVIDIA/AMD/Intel)
```

### Agent Activation Pattern
Agents are parked by default and activated via their `start.sh` scripts in agent directories. This pattern:
1. Preserves zero-cost local-first execution
2. Avoids permanent Ollama instance spawning
3. Enables instantaneous on-demand activation
4. Deactivates automatically when idle

### Hermes Runtime Status: DEFERRED
Hermes runtime is listed but currently **DEFERRED** for future evaluation. No separate Ollama processes are spawned permanently. All current work executes via OpenCode at local port 41825.

---

## Runtime Principles

- **Runtime Independence:** No agent identity is permanently bound to a runtime. Agent capabilities remain consistent across runtime upgrades.
- **Hardware Agnostic:** Runtime selection must not assume permanent hardware platform. Supports CPU, NVIDIA/AMD/Intel accelerators, local/hybrid compute.
- **Governance Stability:** Runtime changes never require modifying organisational governance or agent identity definitions.

---

*Registry updated: 2026-11-08 by Wadda Baba (Sarpanch) — PIN-17 consolidated corrections applied*

**Evidence Summary:** Verified directory existence for all listed agents; corrected non-existent references to sarpanch/ and chalaak/ directories.
|---|---|---|---|
| Coding Agent | `agents/coding-agent/` | ✅ DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Database Agent | `agents/database-agent/` | ✅ DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Network Agent | `agents/network-agent/` | ✅ DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Security Agent | `agents/security-agent/` | ✅ DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Engineering Agent | `agents/engineering/` | ✅ DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Finance Agent | `agents/finance/` | ✅ DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |
| Operations Agent | `agents/operations/` | ✅ DEPLOYED / PARKED | OpenCode/qwen3.5:9b (local) |

**Note:** All agent role definitions exist under `/home/baba/AI/organisation/agents/`. Hermes runtime remains DEFERRED for future evaluation; no separate Ollama processes are spawned. Work executes via OpenCode at `http://127.0.0.1:41825` on local qwen3.5:9b model (6.9 GB, zero marginal cost).

Agent activation: Use start.sh scripts in agent directories to instantiate specialists when needed; agents park automatically when idle. This architecture maintains zero-cost, local-first execution with no permanent cloud dependencies or external API credits consumed.

## Advanced Agents — Ready for Deployment

These agents have definition files and are ready to be deployed:

| Agent | Location | Status | Notes |
|---|---|-------|-------|
| Khoji Baba (Chief Knowledge Officer) | `agents/khoji/` | DEPLOYED / PARKED | Historical identity preserved; research and knowledge work superseded by Research Officer per PIN-16 authorization |
| Gubbani Ji (Gurbani Scripture Agent) | `agents/gurbani/` | DEPLOYED / PARKED | banidb-api integration; reports to Research Officer |
| Research Officer | `agents/research-officer/` | DEPLOYED / PARKED | Primary knowledge synthesis and analysis role |
| Developer | `agents/developer/` | DEPLOYED / PARKED | Ready for deployment |
| Designer | `agents/designer/` | DEPLOYED / PARKED | Ready for deployment |
| Strategist | `agents/strategist/` | TBA | Ready for definition and deployment |

---

## All Agents Summary — FREE on Local OpenCode Runtime

**Currently INSTANTIATED & ACTIVE (zero marginal cost):**

1. **Sarpanch (Wadda Baba)** — CEO / Zero-cost executive officer via Hermes runtime
2. **Chalaak** — CTO / Technical architect

**Parked Specialist Agents (Zero-cost, on-demand activation):**
- Coding Agent, Database Agent, Network Agent, Security Agent, Engineering Agent
- Finance Agent, Operations Agent, Research Officer, Developer, Designer, Gubbani Ji
- Khoji Baba (historical identity preserved)

**Total:** Core executive roles active; specialists available for immediate task assignment.

## How to Verify

```bash
# Check Ollama model availability
opencode models --standalone

# Activate any agent (definition already in place)
ls /home/baba/AI/organisation/agents/*/start.sh
for f in */start.sh; do echo "=== $f ===" && bash "$f"; done
```

## Runtime Details

- **Ollama Endpoint:** `http://127.0.0.1:41825`
- **Model:** `qwen3.5:9b` (6.9 GB, local inference)
- **Context Window:** 65536 tokens
- **Cost:** Zero marginal cost — no cloud API credits consumed

All agents can be registered in the Paperclip control-plane for task assignment via their adapter IDs once fully instantiated and assigned.

---

*Registry updated: 2026-10-28 by Sarpanch (PIN-16)*
