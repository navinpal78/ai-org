# Assessing material

You are given a document, a man page, a thread, a transcript, or a blog post,
and you have to decide whether it is worth a skill at all.

Most material is not. Deciding that quickly is most of the work.

## The question that decides it

**Does this change what the agent _does_, or only what it could say?**

The model already knows most published facts. It knows what RAID 5 is, what
`fsck -n` reports, that a merge conflict needs resolving, that a nullable column
can hold NULL. Feeding it those facts is like telling a chef what a knife is.

What it lacks is the parts that were never written down anywhere:

- the order of steps, and which order is safe
- what the output looks like when it worked
- what to do when the output is different
- which step is irreversible, and what the reversal is
- the mistake everyone makes, and what it costs

That is a skill. The rest is background.

## What to extract

From procedure-shaped material, pull out:

| Element | Example |
|---|---|
| Trigger | "when the mount fails with `wrong fs type`" |
| Ordered steps | the command sequence, in the order that is safe |
| Success signal | the specific output that means it worked |
| Branches | "if X then A, if Y then B" |
| Trap | the thing that looks fine and is not |
| Reversal | how to undo the irreversible step, or that it cannot be undone |

If the material has no branches and no traps, it is probably a blog post
summarising something the model knows. Say so and stop.

## What to discard

- Definitions. The model has them.
- History and motivation. Nobody acts differently for knowing why.
- Anything the model can reason out. If it follows from first principles it
  will, at run time, better than you can write it down.
- Aspirational advice ("you should write good tests"). Not a procedure.

## Red flags that the material is not worth a skill

- No commands, no steps, no branches.
- It is a tutorial for a tool the agents do not have.
- It restates the agent's existing SOUL — if it does, the SOUL is doing the
  teaching and the skill is context bloat.
- The only "procedure" is one worked example. That teaches the example.

## If the material is worth it

Write **one** skill, and point at the rest. A long document is not a long
skill. If it contains five procedures, that is five candidate skills — and you
should check whether the other four are gaps worth filling, or noise to leave
alone.

If the material contradicts an agent's SOUL, that is a finding for the CTO, not
a skill to write. See the SOUL-beats-skill rule.
