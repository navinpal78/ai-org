# Principles

## Local-First

All organisational state and data reside on local infrastructure. Cloud or external services are used only as transient, optional augmentations — never as the primary store.

## Runtime Independence

Organisational knowledge, agent definitions, and project registries must exist in portable files (markdown, constitution) that are not tied to any single execution runtime or platform.

## Explicit Approval

All significant changes require documented approval following the framework in policies/APPROVALS.md. No agent instantiation, project creation, or policy modification occurs without explicit authorisation.

## Transparency

Organisational structure, agent responsibilities, and decision-making processes are documented and visible across the organisation.

## Minimal Viable Structure

Start with the smallest possible foundation (CEO package, knowledge files, policy files, agent specs) and expand incrementally only as needed.

## Data Sovereignty

The organization owns and controls its data. Infrastructure (servers, NAS, workstations) is selected and maintained to ensure this sovereignty.
---

## Runtime, Model and Hardware Independence

Agent identity, role, runtime, model, tools, knowledge and infrastructure are
separate organisational layers.

No agent is permanently tied to a particular runtime or model.

The organisation is hardware-agnostic. No specific CPU, GPU, accelerator,
hardware vendor, driver stack or acceleration framework is an organisational
requirement.

Specific technologies may be used for particular workloads, but they remain
replaceable infrastructure choices.

Future NVIDIA, AMD, Intel, other accelerator, CPU-only, local, hybrid and
external compute configurations must remain possible without redesigning
organisational governance or agent identity.

GPU, CUDA, ROCm, Vulkan and vendor-specific assumptions must not be embedded in
general agent definitions unless a specific project explicitly requires them.
