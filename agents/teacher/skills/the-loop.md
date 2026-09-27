# The loop

Teaching without measurement is just writing text near a model. The loop is what
makes it a change you can defend.

## The loop

**1. Name the gap.**
A specific failing test, or a specific capability you can describe. Write it as
a sentence with a subject and a failure in it: "the network engineer proposes
`iptables -F` when asked to diagnose an open port" is a gap. "network
engineering is weak" is not.

**2. Write the failing test first.**
This is the step everyone skips, and skipping it is why skills go untested.

The test must fail on the current agent. If it passes already, you have found
something the agent can already do, which is worth knowing but is not a lesson.
If you cannot make it fail, you do not yet know what you are teaching.

**3. Record the baseline.**
Full suite, not just the new case. `AGENT_LAST_SCORE` in the agent's
`agent.conf` holds the last recorded score; note the current one before you
change anything, or you will not be able to say what you caused.

**4. Write the skill.**
See `writing-skills.md`. Narrow, procedural, with a failure section.

**5. Measure again.**
Full suite, same settings. Tests default to temperature 0 so the comparison is
meaningful — if you changed the temperature you changed the experiment.

**6. Keep, rewrite, or delete.**

- Score moved, new test passes, nothing else broke: keep it.
- Score moved but something else broke: you taught one thing and broke
  another. Usually the skill was too broad. Narrow it.
- Score did not move at all: the skill taught nothing. Rewrite it once,
  sharply — most no-ops are a skill that is too abstract, or a test that was
  too weak to notice.
- Still nothing: **delete it and write down why.**

## Deleting is a real outcome

A skill in the tree that does nothing costs every agent that reads it, and it
hides the actual gap behind a file that looks like progress. The tree of
useless skills is more damaging than an empty tree, because it makes you
believe you have done work.

The usual cause of a no-op skill: it restates what the model already knows. The
skill described a topic instead of a procedure. Go back to `assessing-material.md`
and ask whether the material was ever procedural.

## Never move the goalposts mid-experiment

Do not edit an existing test's `must_contain` or `must_not_contain` while
measuring your own skill. That is editing the scoreboard.

The legitimate case is a test that was wrong before you started — and then it is
a finding, not a teaching step. Report it, change it deliberately, and re-run
the baseline afterwards so you still know what your skill did on top of it.

## One gap at a time

Do not bundle three fixes into one pass. When the score moves you will not know
which change did it, and the two that did nothing will get the credit.

## Record the result

Whatever happens, write down the before and after numbers, in
`AGENT_LAST_SCORE` and in the skill file. Six months from now the only evidence
that any of this worked is what you wrote down at the time.
