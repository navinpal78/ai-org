# skills/README.md - Network Engineer

Read these when the task calls for them. `layered-diagnosis.md` is the default
and governs the shape of almost every answer; the other three are for specific
faults.

| File | Read it when |
|---|---|
| `layered-diagnosis.md` | Every fault. Works bottom-up from the physical layer and stops at the first thing that is broken. |
| `safe-changes.md` | Before you propose anything that alters configuration. How to propose a change that cannot cause an outage. |
| `dns.md` | Anything that looks like "no internet" with the link up. The most common fault, and the most misdiagnosed. |
| `wifi.md` | Anything wireless, and anything intermittent that changes when a cable is used. |

## Adding a skill

Keep it narrow and procedural: a heading, the commands, and what the output
means. Every skill should let the operator run one command and eliminate one
layer.

Every skill needs a matching test case in `tests/cases.tsv`. A skill with no
test is a guess that it is being followed.
