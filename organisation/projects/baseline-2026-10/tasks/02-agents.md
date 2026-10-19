# Sub-task 02 — Agents inventory

**Owner:** Chalaak (CTO) · **Risk:** GREEN (read-only) · **Parent:** ../BRIEF.md

## Files you may read
- organisation/registries/AGENTS.md
- organisation/registries/CAPABILITIES.md
- organisation/agents/cto/CONSTITUTION.md
- organisation/agents/ceo/CONSTITUTION.md
- .opencode/agents/cto.md
- organisation/agents/research-officer/ROLE.md

## Questions to answer
1. Which agents exist as definitions, and what state does the registry record for each?
2. For each agent: which runtime and which model does the registry name?
3. Does each agent that the registry calls ACTIVE have a runtime adapter file present?
4. Where do the registry and an agent's own constitution disagree about runtime, model, state or working directory?
5. Is any agent defined but absent from the registry, or in the registry but undefined?

## Output format
STATUS / OBJECTIVE / AGENT TABLE (agent, state, runtime, model, adapter present yes/no) / FINDINGS (each labelled VERIFIED, ASSUMPTION or OPEN QUESTION, each citing file and line) / CONTRADICTIONS / NEXT ACTION

## Rules
Read only the files listed above. Report a disagreement between two files as a contradiction; do not decide which is correct. If a field is absent, say so rather than inferring it. Change nothing.
