# baselines/ — raw CPU run output, NOT agent scores

These are the raw transcripts and summaries from running the closed-book suite
on this box (no GPU, 4 cores, 7.6GB RAM, `qwen3:0.6b`). They were moved here
from `~/Work/` on 2026-10-13 so a dead disk does not lose them.

**Nothing in this directory is a measurement of agent quality.** Read the
per-run `README.md` before reading any number here. The three disqualifiers, any
one of which is enough:

1. the model is `qwen3:0.6b` — the project targets 8B+ weights;
2. the run is closed-book, so the research agents' numbers are not research scores;
3. it is evidence about the *harness plumbing*, not about the *prompts*.

## Why it lives in the repo but not in the tooling path

The only thing these files must never become is an `AGENT_LAST_SCORE`. The tree
guarantees that by where the tooling looks, not by hiding the files: every tool
reads `agents/*/agent.conf`, `state/audit.log` and generated `config/*.env` —
**nothing walks `baselines/`**. So the numbers can be backed up to GitHub and
still be unpickable as scores. The real tree keeps `AGENT_LAST_SCORE="never"` on
all 16 agents.

`.out` files are the raw `tools/test-agent.sh` stdout: case names, pass/fail,
and expected-keyword diagnostics only — no prompts and no model replies.

## Contents

| Directory | What |
|---|---|
| `cpu-baseline-2026-09-29/` | First attempt. Only 5 agents finished, and `*_THINKS` was left describing the original models — inconsistent. Kept for the `*_THINKS` finding. |
| `cpu-baseline-2026-09-30/` | The do-over: all 14 runnable agents under one consistent config. The comparable table. |
