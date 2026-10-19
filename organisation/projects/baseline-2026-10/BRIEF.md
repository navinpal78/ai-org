# §12.2 Baseline Report — Commission

**Commissioned by:** Wadda Baba (CEO) · **Date:** 2026-10-20
**Assigned to:** Chalaak (CTO) · **Authority:** Founder approval recorded on PIN-2, 2026-10-19
**Risk level:** GREEN — read-only inspection and reporting. No change to any system.

## What the specification requires

§12.2 of the approved workflow specification: *"The first deliverable after
design approval is a complete baseline report covering current services,
agents, tests, dependencies, configurations, known failures, backup status
and recovery readiness. It must distinguish verified facts from assumptions
and open questions."*

## How this is being delivered

Not as one open-ended report. Chalaak's capability was measured on 2026-10-19
(see `organisation/agents/cto/INSTANTIATION-TEST.md`): it is reliable on
narrow, explicit, verifiable tasks and degrades on sprawling mandates well
before it runs out of context. A single "produce the baseline" instruction
sits on the wrong side of that line.

The commission is therefore split into **five bounded sub-tasks**, each with
a named set of files to read, a fixed list of questions, and a fixed output
format. Each is independently checkable. The CEO consolidates the five into
the deliverable and is accountable for the result.

| # | Sub-task | Scope | Brief |
|---|----------|-------|-------|
| 01 | Services | Running services, units, ports, processes | `tasks/01-services.md` |
| 02 | Agents | Agent definitions, adapters, registry agreement | `tasks/02-agents.md` |
| 03 | Tests and known failures | What has been tested, what is only claimed | `tasks/03-tests-failures.md` |
| 04 | Dependencies and configuration | Runtimes, models, versions, tuning | `tasks/04-dependencies-config.md` |
| 05 | Backup and recovery readiness | Repository, snapshots, restorability | `tasks/05-backup-recovery.md` |

## Why the evidence is pre-captured

Chalaak's adapter sets `bash: ask`. In non-interactive invocation that
auto-rejects, so Chalaak cannot run `systemctl`, `ollama` or `git` itself.
Rather than widen its permissions for a GREEN reporting task, the CEO
captured the command output read-only into `evidence/` and Chalaak analyses
those files by name.

This keeps the CTO read-only, keeps the raw evidence reviewable, and means
the sub-task outputs can be re-checked against the captures later. The
trade-off is recorded honestly: **Chalaak is analysing a snapshot taken by
the CEO, not observing the system directly.** The capture timestamp is at
the top of each evidence file.

## Standing rules for every sub-task

1. Read only the files named in the brief. Do not range beyond them.
2. Label every statement **VERIFIED** (supported by a named file),
   **ASSUMPTION** (inferred, not shown) or **OPEN QUESTION** (not
   determinable from the files provided).
3. If something is not in the files, say *"not present in the files
   provided"*. Do not supply a plausible value. Never invent a path, a
   version, a port or a conflict.
4. Quote the file and line that supports each VERIFIED statement.
5. Report contradictions between files as findings rather than resolving
   them silently.
6. Change nothing.

## Review

The CEO reviews each report against the evidence file it cites before it is
accepted, and consolidates the accepted reports into `BASELINE.md`. Any
statement that cannot be traced to the evidence is removed or demoted to an
open question. The Founder approves the consolidated baseline; a sub-task
report is not a deliverable on its own.
