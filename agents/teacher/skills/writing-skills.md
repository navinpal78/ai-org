# Writing a skill

A skill is a procedure the agent can follow. It is not a document, an essay, or
a summary of a topic.

## The format

```markdown
# <Procedure name, as an action>

**When to read this:** the specific situation. Not the subject area.

## Do this
1. First step, with the actual command or value.
2. Second step.
3. ...

## If <expected thing> does not happen
- What that usually means.
- The next thing to try. Bound it — say how many attempts before escalating.

## Do not
- The specific mistake, and what it costs.

## Not covered here
- The adjacent thing this skill deliberately does not handle, and who does.
```

## The two questions

Before writing, answer both. If either answer is vague, the skill is not ready.

**What is the trigger?** "The agent is doing X and needs to know Y." Not
"when working with Z".

**How does the agent know it worked?** A visible state, an output to check, a
command that returns something specific. If you cannot name it, the skill has
no stopping rule and the agent will either stop early or loop.

## Narrowness

One procedure. A defined start and a defined end. If you need "and also" twice,
split it.

Length target: readable in under two minutes. Roughly 200-400 words. A skill
at a thousand words is a document nobody reads, and it will crowd out the short
skills that actually get used.

## What goes in, what does not

**In:** the order of steps. The branches. What to check. What to do when the
expected output does not appear. The specific mistake and its cost.

**Out:** definitions the model already has. Background history. Motivation.
Anything phrased as "it is important to understand that...".

The test for the "out" pile: *does removing this change what the agent does?*
If not, cut it.

## Failure sections are not optional

The failure section is the highest-value part of the skill and the part most
often left out. It is where the procedure stops being a script and becomes
judgement.

Bad: "If it fails, investigate the problem."

Good: "If `fsck -n` reports errors it did not report before, the filesystem is
degrading. Do not continue. Re-run the read-only checks and escalate — do not
add `-y`."

The second one tells the agent what to *stop* doing. That is what prevents the
expensive mistake.

## The "do not" section

Name the specific mistake, and what it costs. Concrete beats abstract:

- Bad: "Be careful with destructive commands."
- Good: "Never run `mkfs` as a diagnostic. It destroys the thing you were
  diagnosing, and the diagnosis is the only copy."

## After writing

Every skill needs a matching test case, written *before* the skill, that
fails without it. See `the-loop.md`.

If you cannot write a test that would fail without this skill, the skill is not
teaching anything the agent could not already do. Delete it or find the real
gap.
