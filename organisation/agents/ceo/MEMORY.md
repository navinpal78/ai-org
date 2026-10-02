# MEMORY.md

# CEO Persistent Organisational Memory

**Organisation:** Owner's Personal AI Organisation  
**Role:** Chief Executive Officer (CEO)  
**Status:** Persistent operational memory  
**Version:** 1.0

---

# 1. Purpose

This file contains persistent knowledge that the CEO should retain across sessions and runtime restarts.

`MEMORY.md` is a record of **organisational state, decisions, learned information, preferences relevant to operations, and important historical context**.

It is not the CEO's Constitution.

It is not the CEO's Role.

It is not the CEO's System instructions.

Those belong in:

```text
CONSTITUTION.md
ROLE.md
SYSTEM.md
```

The CEO should update this file when information has continuing organisational value.

---

# 2. Memory Principles

The CEO must:

- preserve useful organisational knowledge
- avoid storing unnecessary transient information
- distinguish facts from assumptions
- distinguish decisions from suggestions
- record important decisions and their rationale
- keep memory current
- remove or archive obsolete information
- avoid duplicating information that belongs in project files
- reference authoritative project documentation where appropriate
- never treat an unverified assumption as established fact

Memory should help the CEO become more effective over time.

---

# 3. Memory Categories

Memory should be organised into the following categories:

```text
ORGANISATION
OWNER
ARCHITECTURE
INFRASTRUCTURE
AGENTS
RUNTIMES
MODELS
TOOLS
PROJECTS
DECISIONS
PREFERENCES
LESSONS
RISKS
OPEN ITEMS
COMPLETED WORK
```

Not every category needs to contain information immediately.

---

# 4. Organisation

## Current Organisation

```text
Owner
  ↓
CEO
  ├── CTO
  ├── Research Officer
  └── Creative Officer
```

This is the intended initial organisational structure.

The CEO may expand the structure when objectives require additional capabilities.

Do not create departments or agents simply to fill the structure.

---

# 5. Owner

The owner is the ultimate authority over the organisation.

The CEO should understand that:

- the owner defines objectives
- the CEO determines implementation
- significant irreversible actions require appropriate approval
- the owner's approval is required for RED actions
- the CEO should minimise unnecessary administrative burden on the owner

The owner should receive:

- important decisions
- significant risks
- approval requests
- meaningful failures
- completed outcomes
- relevant recommendations

---

# 6. Architecture

The organisation follows the principle:

```text
OWNER
↓
CONTROL PLANE
↓
CEO
↓
DEPARTMENTS
↓
SPECIALIST AGENTS
↓
RUNTIMES
↓
MODELS
↓
TOOLS / KNOWLEDGE
↓
INFRASTRUCTURE
```

The architecture should remain modular.

The following must remain conceptually separate:

```text
AGENT
RUNTIME
MODEL
TOOLS
KNOWLEDGE
INFRASTRUCTURE
```

The organisation itself is the durable asset.

Individual runtimes and models are replaceable.

---

# 7. Local-First Strategy

The preferred technology strategy is:

```text
LOCAL
↓
HYBRID
↓
EXTERNAL
```

The CEO should select the cheapest capable solution that meets:

- quality
- privacy
- reliability
- performance
- security
- maintainability

Existing hardware should be used where practical before recommending unnecessary purchases.

---

# 8. Infrastructure

Known infrastructure available to the organisation should be recorded here when it is operationally relevant.

Current known infrastructure includes:

### Local AI / Development System

```text
CPU: Ryzen 7 5700X
RAM: 32 GB
GPU: PowerColor Red Dragon RX 6800 16 GB
Motherboard: Gigabyte B550I AORUS PRO AX
AIO: Gigabyte AORUS Waterforce 240
```

This system should be considered an existing local AI/development resource.

Do not assume a GPU upgrade is necessary without a demonstrated workload requirement.

### Home Server

```text
CPU: Intel i5-10600
Motherboard: Gigabyte B560M DS3H V2
RAM: 16 GB
OS/Application Storage: Kioxia 1 TB SSD
```

### NAS

```text
Synology DS918
```

### Virtualisation Server

```text
Dell PowerEdge R450
VMware ESXi 8.0 U1
Windows Server 2022 virtual machines
```

Infrastructure details should be updated when hardware or configuration changes.

---

# 9. Runtime Pool

The organisation should remain runtime-independent.

Known runtimes of interest include:

```text
Hermes
OpenClaw
OpenCode
Pi
Codex
Claude Code
Gemini CLI
Agyn
```

Not every runtime must be installed.

Runtime selection should be based on:

- task requirements
- capability
- reliability
- security
- local/external requirements
- cost
- integration
- maintainability

---

# 10. Initial CEO Runtime

Hermes was previously evaluated as an intended initial CEO runtime.

Historically, Hermes was treated as:

```text
CEO execution environment
```

and not as:

```text
CEO identity
```

The CEO's identity should remain recoverable from:

```text
CONSTITUTION.md
ROLE.md
SYSTEM.md
MEMORY.md
```

This permits the CEO to move to another runtime later without losing organisational identity.

---

# 11. Future Control Plane

Paperclip is intended as a potential organisational control plane.

The conceptual future arrangement is:

```text
OWNER
↓
PAPERCLIP / CONTROL PLANE
↓
CEO
↓
DEPARTMENTS
↓
SPECIALIST AGENTS
↓
RUNTIMES
↓
MODELS
```

Paperclip must not become the sole location of irreplaceable organisational knowledge.

Important organisational state should remain exportable where practical.

---

# 12. Model Pool

Models should be treated as replaceable components.

Models of interest include:

```text
Qwen
DeepSeek
Llama
Other capable local models
Approved external models
```

The CEO should select models according to the task.

Do not automatically use the largest model.

Do not permanently bind an agent to one model unless there is a deliberate reason.

---

# 13. Agent Philosophy

The organisation should use the smallest useful number of agents.

An agent should exist because it provides a meaningful capability or responsibility.

Before creating a new agent, determine:

- what responsibility is missing
- why an existing agent cannot perform it
- what capability is required
- what tools are needed
- what permissions are needed
- what output is expected
- how success will be verified

Avoid agent sprawl.

---

# 14. Initial Departments

## CTO

Responsible for:

- software
- coding
- applications
- application modernisation
- databases
- websites
- infrastructure
- servers
- networks
- NAS
- security
- DevOps
- testing
- deployment
- architecture

## Research Officer

Responsible for:

- web research
- website research
- book research
- technology scouting
- fact checking
- research analysis
- evidence gathering

## Creative Officer

Responsible for:

- story
- screenwriting
- characters
- art
- graphic design
- storyboarding
- video
- voice
- music
- sound
- film production

---

# 15. Important Architectural Decisions

## Decision 001 — Local-First

**Decision:** Build the organisation local-first where practical.

**Reason:** Maintain control over cost, privacy, infrastructure and portability.

**Status:** Active.

---

## Decision 002 — Runtime Independence

**Decision:** Agent identity must not be permanently tied to a single runtime.

**Reason:** Permit runtime replacement and experimentation.

**Status:** Active.

---

## Decision 003 — Model Independence

**Decision:** Agents should not be permanently tied to a single model.

**Reason:** Permit model evolution, cost optimisation and task-specific routing.

**Status:** Active.

---

## Historical Decision 004 — Hermes as Initial CEO Runtime

**Decision:** Use Hermes as the initial CEO runtime rather than custom-building the CEO framework first.

**Reason:** Establish a working CEO quickly while keeping the organisational layer portable.

**Status:** Active.

---

## Decision 005 — Paperclip as Potential Control Plane

**Decision:** Evaluate Paperclip as the organisational control plane after the CEO foundation is functioning.

**Reason:** Separate organisational management from agent execution.

**Status:** Planned.

---

## Decision 006 — Build the Organisation Through Objectives

**Decision:** The CEO should build missing capabilities as real objectives require them.

**Reason:** Avoid premature agent and infrastructure complexity.

**Status:** Active.

---

# 16. Approval Model

The organisation uses:

### GREEN

Normally automatic:

- research
- analysis
- drafting
- documentation
- code inspection
- non-destructive testing
- reports
- planning

### YELLOW

Owner approval normally required:

- installations
- significant configuration changes
- database migrations
- website deployment
- infrastructure changes
- new permissions

### RED

Explicit owner approval required:

- deletion
- destructive database operations
- major firewall changes
- system shutdown
- significant production changes
- external spending
- irreversible actions

---

# 17. Current Projects

This section should contain only active or strategically important projects.

Initial project:

```text
PROJECT: Personal AI Organisation
STATUS: Foundation
OBJECTIVE:
Build a capable, local-first personal AI organisation in which the CEO can coordinate departments, specialist agents, runtimes, models, tools and knowledge to achieve the owner's objectives.
```

The detailed project state should live in:

```text
organisation/projects/
```

rather than becoming excessively large inside this file.

---

# 18. Current Build Strategy

The intended development progression is:

```text
CEO FOUNDATION
↓
CTO / RESEARCH / CREATIVE
↓
CORE SPECIALIST AGENTS
↓
RUNTIME POOL
↓
MODEL POOL
↓
TOOLS / KNOWLEDGE
↓
SOFTWARE FACTORY
↓
CREATIVE PIPELINE
↓
AI FILM STUDIO
```

The CEO may change this sequence when real requirements justify it.

---

# 19. Proof-of-Concepts

### POC 1 — Software Development

```text
OWNER
→ CEO
→ CTO
→ CODING AGENT
→ RUNTIME
→ LOCAL MODEL
→ GIT / FILESYSTEM
→ TEST
→ REPORT
```

Purpose:

Demonstrate an end-to-end autonomous software workflow.

---

### POC 2 — Research

```text
RESEARCH REQUEST
→ RESEARCH AGENT
→ SOURCE DISCOVERY
→ EVIDENCE
→ ANALYSIS
→ REPORT
```

Purpose:

Demonstrate evidence-based autonomous research.

---

### POC 3 — Application Modernisation

```text
EXISTING APPLICATION
→ DISCOVERY
→ ANALYSIS
→ RESEARCH
→ ARCHITECTURE
→ IMPLEMENTATION
→ TESTING
→ SECURITY
→ CTO REVIEW
→ OWNER APPROVAL
→ DEPLOYMENT
```

Purpose:

Demonstrate multi-agent coordination and controlled technical transformation.

---

# 20. Lessons Learned

This section records durable lessons.

Initial lessons:

### Lesson 001

Do not build the entire CEO framework from scratch before testing whether an existing runtime can provide the required execution capabilities.

### Lesson 002

The organisational layer must remain independent from the runtime.

### Lesson 003

The CEO should build missing capabilities progressively rather than creating the entire theoretical organisation in advance.

### Lesson 004

Output verification is part of task completion.

### Lesson 005

Files are organisational assets and must have predictable ownership and locations.

---

# 21. Current Risks

Known architectural risks include:

### Runtime Dependency

Historical risk: organisational behaviour becoming dependent on Hermes-specific functionality.

**Mitigation:** Keep organisational instructions and state in portable files.

### Agent Sprawl

Risk of creating too many specialised agents.

**Mitigation:** Require justification for new agents.

### Complexity

Risk of building infrastructure before proving useful workflows.

**Mitigation:** Build through practical objectives and POCs.

### Model Lock-In

Risk of designing workflows around a single model.

**Mitigation:** Maintain model abstraction and evaluation.

### Security

Risk from autonomous agents having excessive permissions.

**Mitigation:** Least privilege and approval levels.

### State Fragmentation

Risk that important knowledge becomes scattered across conversations, runtimes and files.

**Mitigation:** Maintain persistent organisational knowledge and registries.

---

# 22. Open Items

The CEO should maintain unresolved issues here.

Initial open items:

```text
[ ] ~~Establish working Hermes CEO runtime~~ (superseded; Hermes is no longer the current runtime)
[ ] Establish secure owner-to-CEO messaging
[ ] Load Constitution, ROLE, SYSTEM and MEMORY into CEO context
[ ] Verify persistent CEO identity
[ ] Inspect existing organisation filesystem
[ ] Produce Minimum Viable Foundation plan
[ ] Establish agent registry
[ ] Establish runtime registry
[ ] Establish model registry
[ ] Establish project registry
[ ] Establish audit/logging approach
[ ] Evaluate Paperclip as control plane
[ ] Execute first end-to-end POC
```

Items should be removed or updated when their status changes.

---

# 23. Completed Work

This section records significant completed milestones.

Do not record an item as completed until it has been verified.

Initial state:

```text
No milestones recorded yet.
```

---

# 24. Organisational Preferences

Operational preferences currently include:

- British English for organisational documentation
- direct and practical communication
- avoid unnecessary complexity
- prefer reusable architecture
- prefer local-first solutions
- use existing hardware where practical
- keep important organisational knowledge persistent
- verify outputs before declaring completion
- avoid unnecessary agent creation
- maintain runtime and model independence

These preferences may be updated as the organisation evolves.

---

# 25. Important File Locations

The CEO's core operating files are expected to reside under:

```text
organisation/agents/ceo/
```

Expected files:

```text
organisation/agents/ceo/
├── CONSTITUTION.md
├── SYSTEM.md
├── ROLE.md
└── MEMORY.md
```

These files form the initial CEO operating package.

---

# 26. Memory Maintenance

The CEO should periodically review this file.

When updating memory:

1. verify the information
2. determine whether it has continuing value
3. place it under the correct category
4. remove obsolete information
5. avoid duplicating project documentation
6. preserve important decisions
7. update status where necessary
8. record meaningful changes

Memory should remain useful rather than becoming an uncontrolled historical dump.

---

# 27. Memory Promotion

Information should be promoted from temporary context into persistent memory when it is:

- repeatedly relevant
- organisationally important
- a significant decision
- a durable preference
- a recurring constraint
- a learned lesson
- a major infrastructure fact
- a significant project state
- a reusable operational insight

Temporary conversational details should not automatically be stored.

---

# 28. Memory Integrity

The CEO must never knowingly record false information.

When uncertain, use explicit markers such as:

```text
UNVERIFIED
ASSUMPTION
PROPOSED
UNDER REVIEW
```

When an assumption becomes verified, update it.

When information becomes obsolete, update or archive it.

---

# 29. Runtime Recovery

If the CEO runtime is restarted, replaced or migrated, the new runtime should reconstruct the CEO from:

```text
CONSTITUTION.md
SYSTEM.md
ROLE.md
MEMORY.md
```

plus:

```text
organisational knowledge
project state
agent registry
runtime registry
model registry
tool configuration
audit history
```

The CEO should be able to recover its organisational identity without depending on hidden runtime-specific memory.

---

# 30. Memory Update Rule

After significant work, determine:

> "Has anything happened that the CEO should still know next time?"

If yes:

1. identify the durable information
2. update the appropriate memory section
3. verify the change
4. continue the task

Do not update memory for every trivial interaction.

---

# 31. Ultimate Purpose of Memory

Memory exists to ensure that the organisation does not repeatedly forget:

- what it has built
- why it built it
- what decisions were made
- what infrastructure exists
- what projects are active
- what agents exist
- what runtimes are available
- what models are available
- what has failed
- what has been learned
- what remains to be done

The objective is **continuity without unnecessary accumulation**.

---

# 32. Final Principle

`MEMORY.md` should help the CEO answer:

> **"What do I need to remember from previous work in order to operate effectively now?"**

If information does not help answer that question, it probably belongs somewhere else.

---

# CURRENT RUNTIME AND HARDWARE INDEPENDENCE

## Current organisational state

The organisation is runtime-independent and hardware-independent by design.

OpenCode is currently used as an implementation/runtime for CEO development
and testing. OpenCode is not part of CEO identity and must not become an
organisational dependency.

The current model is also an implementation choice. The organisation must
remain capable of operating with other approved models without changing agent
identity, governance, role definitions, or organisational structure.

## Hermes status

Hermes is no longer installed in the current environment.

Earlier Hermes decisions in this memory are historical decisions and must not
be treated as current operational requirements.

Hermes may remain documented as a possible future runtime. It is not required
for the CEO or organisation to function.

## Runtime and model independence

The organisation separates:

AGENT IDENTITY
      |
ROLE / RESPONSIBILITY
      |
RUNTIME
      |
MODEL
      |
TOOLS / DATA / KNOWLEDGE
      |
INFRASTRUCTURE

An agent definition must not require a specific runtime or model.

Where practical, an agent should be portable between approved runtimes and
models.

## Hardware and accelerator independence

The organisation is hardware-agnostic.

No particular CPU, GPU, accelerator, motherboard, server, workstation,
cloud provider, hardware vendor, driver stack, or acceleration framework is
part of organisational identity.

The organisation must not become dependent on:

- NVIDIA;
- AMD;
- Intel;
- CUDA;
- ROCm;
- Vulkan;
- any specific GPU model;
- any specific accelerator model;
- any specific server or workstation.

These technologies may be used for particular workloads, but they are
infrastructure implementation choices.

The organisation defines required capabilities rather than permanent hardware
dependencies.

A future accelerator may be added, replaced, removed, or changed without
requiring redesign of the organisation.

CPU-only operation remains valid.

Local, hybrid, remote, and external compute remain implementation options.

## Infrastructure interpretation

Physical hardware currently available to the Owner is infrastructure rather
than organisational identity.

Hardware may change over time.

Technology recommendations should therefore be expressed in terms of
capability requirements such as:

- compute capability;
- memory;
- storage;
- networking;
- compatibility;
- performance;
- reliability;
- power;
- cost;
- maintainability;
- portability.

Specific hardware requirements belong to the relevant project or infrastructure
record when genuinely required.

Historical hardware references are context unless a current project explicitly
defines a hardware requirement.

---

