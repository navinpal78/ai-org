# Handover

A skill you write is not finished when the file exists. It is finished when the
agent you wrote it for behaves differently, and someone else can tell.

## Before you hand it over

Every one of these must be true. If any is not, you are not done.

- [ ] A test exists that failed before the skill and passes after.
- [ ] The full suite was run, and the before and after numbers recorded.
- [ ] Nothing else regressed. A skill that fixes one case and breaks three is
      worse than the gap you started with.
- [ ] The skill does not contradict that agent's SOUL.
- [ ] The skill does not ask for anything its `agent.conf` forbids — check
      `AGENT_SAFETY` and `AGENT_NETWORK` against every command and every URL in
      the text.
- [ ] The skill's "not covered here" section exists.

## Check the safety line yourself

This is the check most likely to be skipped and least acceptable to skip.

Read the skill and list every command that writes, and every network access.
Compare against the target agent's `AGENT_SAFETY` and `AGENT_NETWORK`.

A `read-only` agent and a skill containing a command that modifies something
is a conflict. A `limited`-network agent and a skill containing a URL is a
conflict. Report both to the CTO. Do not soften the wording to make the
conflict go away, and do not edit `agent.conf` to make it legal.

## Write the handover note

The CTO reads this instead of re-running everything. Keep it short and put
numbers in it:

```
Skill:    skills/<file>.md
Agent:    <name>
Gap:      <the one-sentence failure this fixes>
Test:     <case name>, new, failed before / passes after
Before:   <score>%   After: <score>%
Notes:    <what else changed, regressions, what it still does not cover>
```

If you deleted a skill that did not work, that note is the only record. Write
it anyway — "tried X, moved the score by nothing, removed it" is a result, and
it stops the next person trying X again.

## Verify adoption, not just correctness

A test that passes is necessary but not sufficient. It shows the agent
behaves right when asked directly.

The failure mode this misses: the skill is correct but so long, or so
crowded-out by neighbouring skills, that the agent only reaches it in some
contexts. A green suite on one prompt is not evidence it will fire on a
differently-worded prompt.

So add at least one case using **different wording** for the same situation.
If the skill only triggers on the phrasing you taught, it did not transfer.

## When you cannot finish

If the gap needs a capability the agent's config does not give it, or a change
to SOUL, stop and report. Do not work around the boundary. A handover note
saying "this needs read-write on the storage engineer's workspace, CTO decision"
is a good result. A quietly widened agent is a bad one.
