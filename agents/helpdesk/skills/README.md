# skills/README.md - Helpdesk

Read these when the task calls for them. Do not read all three every time;
`triage` is the default, and the other two are for specific moments.

| File | Read it when |
|---|---|
| `triage.md` | Every support conversation. The question order, and what counts as a safe step. |
| `escalation.md` | Before you hand a problem to anyone. How to hand it over, and what to include. |
| `knowledge-base.md` | Before you answer from documented knowledge, and when you hit a gap. |

## Adding a skill

Keep it narrow and procedural: a heading, the steps, and what goes wrong. A
skill that describes a topic rather than a procedure just adds noise to every
prompt.

Every skill needs a matching test case in `tests/cases.tsv`. A skill with no
test is a guess that it is being followed.
