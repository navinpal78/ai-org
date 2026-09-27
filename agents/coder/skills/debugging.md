# Debugging

Applies to: anything that is broken and you have been asked to fix.

## The rule that matters

**Reproduce before you fix.** An unfixed guess is a coin flip, and you will not
know which side you landed on until the user runs it. Get the error, the input
that triggers it, and the actual behaviour first.

## Order of work

1. **Get the exact error.** The full traceback, not the summary. Ask for it if
   you were not given it.
2. **Get the exact trigger.** What input, what sequence, how reliably.
3. **Find the line.** Read the file. Follow the traceback. Do not patch a
   function you have not opened.
4. **Form one hypothesis.** State it in a sentence: "I think X is Y because Z."
5. **Test the hypothesis.** Smallest possible check. Add a print, run a
   one-liner, read the source again.
6. **Fix the cause, not the symptom.** A `try/except` around a crash is a
   symptom fix. It hides the bug and leaves the data wrong.
7. **Check for the same bug elsewhere.** If it happened once, grep for the
   pattern. Say how many places you found.

## Common categories

**`KeyError` / `NoneType has no attribute`** — something is absent, not None.
Check whether the key exists before reading it, and check whether the lookup
returns None on a miss. Print the actual keys rather than guessing.

**Wrong results, no crash** — usually a silent type change, a float rounding
comparison, or an off-by-one. Check the boundary values and the empty case.
Do not trust a passing test that does not cover the edge.

**Slow** — find what is actually slow before optimising. `EXPLAIN ANALYZE` in
SQL, a profiler in Python, timing around the suspected block. The usual
culprits are: a query inside a loop, an N+1, a missing index, or work that
could be hoisted out of the loop entirely.

**Intermittent** — race conditions, ordering assumptions, uninitialised state,
clock skew, or genuinely random input. Add logging that records what varies
between the runs that pass and the ones that fail.

**Works locally, fails deployed** — compare the environment. Config, versions
of dependencies, file permissions, timezone, character encoding, case
sensitivity of paths.

## When you cannot reproduce it

Say so, and say what you would need: the input, the environment, logs, the
version. Do not ship a speculative fix. A speculative fix that appears to work
is worse than no fix, because it hides the problem and adds a second one.

## Before you say it is fixed

- Re-read your own diff. Not from memory.
- Run the test suite. Watch it pass.
- If you could not run it, say that plainly instead of implying you did.
