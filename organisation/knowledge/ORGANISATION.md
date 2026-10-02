# Organisation

## Overview

Personal AI Organisation — a local-first AI orchestration framework operating across multiple runtime environments (Hermes, OpenClaw, Pi, Codex, Gemini CLI, etc.).

## Structure

- **CEO package** at `agents/ceo/` — 5 authoritative files (CEO.md, CONSTITUTION.md, SYSTEM.md, ROLE.md, MEMORY.md) defining governance, operations, and infrastructure
- **Agents** — specialised agents under `agents/` for engineering, finance, operations, research departments
- **Constitution** — `constitution/CEO_CONSTITUTION.md` aligning with CEO CONSTITUTION.md
- **Knowledge** — organisational knowledge captured in `knowledge/*.md` files
- **Policies** — approval, delegation, and security frameworks in `policies/*.md` files
- **Projects** — project registries under `projects/`

## Infrastructure

- Local: Ryzen 7 5700X, 32GB RAM, RX 6800
- Home server: i5-10600, 16GB RAM, DS918 NAS
- ESXi server for virtualisation

## Runtime Independence

Organisational state must remain portable across runtimes. All state is persisted in CONSTITUTION.md, SYSTEM.md, ROLE.md, and MEMORY.md files.

## Current State

- CEO package complete and verified
- Skeletal directory structure with most subdirectories empty
- Gaps: no knowledge captured, no policies, no agent definitions, no projects directory
- Working toward Minimum Viable Foundation plan
---

## Runtime, Model and Hardware Independence

OpenCode is the current development/runtime implementation, not part of CEO
identity.

The organisation must remain portable between suitable runtimes and models.

Physical compute infrastructure is replaceable.

The organisation does not depend on any particular:

- CPU;
- GPU;
- accelerator;
- hardware vendor;
- driver stack;
- acceleration framework;
- workstation;
- server;
- cloud provider.

Specific hardware may be selected for an individual workload, but such a
selection belongs to infrastructure or project decisions rather than
organisational identity.

Future hardware changes must not require redesigning the CEO, agent definitions,
governance or organisational hierarchy.
