# skills/README.md - Storage Engineer

Read these when the task calls for them. `destructive-operations.md` governs
anything that writes to a device, and should be read *before* you propose a
command, not after.

| File | Read it when |
|---|---|
| `diagnosing.md` | Every fault. Identifies the device, reads the kernel log, and rules out the three boring causes first. |
| `destructive-operations.md` | Before you write a single command that alters storage. The pre-flight checklist and the command briefing. |
| `smart-and-health.md` | A disk that is slow, failing, or suspected of failing. Reading SMART as a trend, and the image-before-repair sequence. |
| `backups.md` | When someone says they have a backup, and whenever a destructive proposal depends on one existing. |

## Adding a skill

Keep it narrow and procedural. For this agent, every skill should end with an
explicit statement of what is destroyed and how to reverse it.

Every skill needs a matching test case in `tests/cases.tsv`. A skill with no
test is a guess that it is being followed - and here, a wrong guess is
irreversible.
