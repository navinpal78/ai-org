# Security

## Principles

- organisational state should remain under Owner control;
- local-first storage is preferred;
- secrets must not be stored in ordinary markdown;
- access should be granted only when required;
- permissions should follow least privilege;
- external transfer of sensitive information requires appropriate authority;
- important security decisions must be traceable.

## Data Classification

### Public

General organisational mission, principles and non-sensitive structural
information.

### Internal

Agent definitions, project information, policies, architecture and
operational documentation.

### Confidential

Sensitive project material, private organisational information and data that
should not be externally disclosed.

### Secret

API keys, passwords, authentication tokens, private keys and other
credentials.

Secrets must not be stored in ROLE.md, POLICY files or ordinary knowledge
documents.

## Access Controls

Agents and runtimes should receive only the tools, directories and permissions
required for their current task.

Filesystem access must follow task authority.

READ-ONLY tasks must have no persistent write authority where the execution
environment permits enforcement.

## Runtime Security

A runtime must not be treated as trusted merely because the model is trusted.

Where possible, authority should eventually be enforced by the execution
environment or control plane rather than by model instruction alone.

## External Services

External services should be treated as optional dependencies.

Before sending sensitive information externally, determine:

- what data leaves the local environment;
- why it is required;
- who receives it;
- what retention/control applies;
- what approval is required.

## Secret Management

Use environment variables, secret stores or other appropriate mechanisms.

Never place secrets directly in:

- ROLE.md;
- SYSTEM.md;
- MEMORY.md;
- policies;
- project documentation;
- source repositories.

## Current State

No secrets are intentionally stored in the organisational documentation.

Security enforcement is currently partly policy-based.

Stronger technical enforcement should be introduced through the future control
plane/runtime architecture.
