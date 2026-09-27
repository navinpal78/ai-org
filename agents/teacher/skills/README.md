# skills/README.md - Teacher

Read these when the task calls for them. `the-loop.md` governs the whole
process and is worth reading before anything else.

| File | Read it when |
|---|---|
| `the-loop.md` | Every teaching task. The measure-before, measure-after loop, and when to delete your own work. |
| `assessing-material.md` | First, before writing anything. Decides whether the material is a procedure or just facts. |
| `writing-skills.md` | When writing the skill file itself. Format, narrowness, and the failure section. |
| `handover.md` | Before you report the work as done. The checklist, the safety line, and the note the CTO reads. |

## The shortest version

```
Name the gap  ->  write the failing test  ->  baseline
  ->  write the skill  ->  measure
  ->  keep, narrow, or delete
```

If you cannot name the failure you are fixing, stop and ask. Everything else in
this directory is downstream of that answer.

## Adding a skill

Follow the format in `writing-skills.md`. It must have a trigger, a stopping
rule, a failure section, a "do not" section, and a "not covered here" section.

It must also have a test case that fails without it. A skill with no test is a
guess that it is being followed, and in an organisation where the agents have
real file access, a wrong guess is not a small thing.
