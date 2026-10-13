# CPU baseline run, 2026-09-30 — DO NOT READ THESE AS AGENT SCORES

Raw output from running the closed-book suite on this box: **no GPU, 4 cores,
7.6GB RAM, `qwen3:0.6b`, thinking off for every agent.** Nothing here is a
measurement of agent quality. It is a plumbing check that the harness runs end
to end, and its point is the thing the 2026-09-29 run could not claim: **one
comparable table across all 14 runnable agents under one configuration.**

## Why these numbers must not become scores

The same three disqualifiers as the 2026-09-29 run:

1. **The model is `qwen3:0.6b`.** The project is designed for 8B+ weights;
   `AGENTS.md` says not to tune prompts against small local models because it
   distorts them for the models actually used.
2. **Closed-book.** The five research agents declare `AGENT_RETRIEVAL="on"` and
   are meant to be run with sources injected. These are their closed-book
   numbers, which `AGENTS.md` rule 17 exists to keep from being mistaken for
   research scores.
3. The run is plumbing evidence about the *harness*, not the *prompts*.

Committed to the repo under `baselines/` on 2026-10-13 as a durability backup
(so a dead disk does not lose them), but **kept out of the tooling path on
purpose** — no script reads `baselines/`, so nothing can pick these up as an
`AGENT_LAST_SCORE`. The real tree still has `AGENT_LAST_SCORE="never"` on all 16
agents and a 5-line audit log. See `baselines/README.md`.

## What this run fixes versus 2026-09-29

Yesterday the box was inconsistent under its own config: the model override
changed every `*_MODEL` to `qwen3:0.6b` and left every `*_THINKS` describing
the original catalog models, so some agents ran with thinking on (~190s/case,
a projected 20h) and some off (~25s/case). This run moved `_MODEL` and
`*_THINKS` **together** (`qwen3:0.6b`, `false`) before starting, so the
configuration is uniform. The five agents finished that day matched this run
to the percentage point:

| Agent | 2026-09-29 | 2026-09-30 |
|---|---|---|
| helpdesk | 10/21 (47%) | 10/21 (47%) |
| coder | 8/19 (42%) | 8/19 (42%) |
| personal | 12/18 (66%) | 12/18 (66%) |
| languages | 33/47 (70%) | 33/47 (70%) |
| research-officer | 15/46 (32%) | 15/46 (32%) |

and `security-engineer` came in at 35 cases in 865s (~25s/case) instead of the
projected 8x-against-helpdesk the inconsistent config would have produced. The
whole run took 2h30m (08:58 -> 11:28 UTC+8), not the 20h the 2026-09-29
configuration would have projected.

## Results — all 14 runnable agents, in suite order

| Agent | Cases | Score | Seconds |
|---|---|---|---|
| helpdesk | 21 | 47% | 295 |
| coder | 19 | 42% | 648 |
| personal | 18 | 66% | 214 |
| languages | 47 | 70% | 819 |
| teacher | 32 | no result | — |
| research-officer | 46 | 32% | 571 |
| security-engineer | 35 | 74% | 865 |
| network-engineer | 29 | 41% | 754 |
| storage-engineer | 29 | 65% | 759 |
| tech-researcher | 44 | 34% | 493 |
| design-researcher | 44 | 50% | 363 |
| education-researcher | 41 | 65% | 533 |
| web-researcher | 40 | 62% | 781 |
| cto | 63 | 15% | 1392 |
| ceo | 54 | 48% | 500 |
| storyteller | 45 | no result | — |

`teacher` and `storyteller` report **no result** by design: the `teacher` and
`narrative` roles bottom out at `qwen3:14b` (10GB), and the CPU fallback is a
nominal 8GB, so `resolve_models.py` emits `# TEACHER_MODEL=""` and
`# NARRATIVE_MODEL=""`. Correct behaviour, and it means 14 of 16 are runnable.

Every line recorded `rc=1` — the deliberate 1-problem tree (the auditor
monoculture) makes the run-exit honest by construction; the score in each row
is the case pass rate, and per-suite failures are in the `.out` files.

## Companion data

- `progress.txt` — timestamps and per-agent rc/pass/score for the whole run.
- `summary.txt` — the same, one line per agent.
- `<agent>.out` — the raw closed-book suite transcript per agent.
- Ran from a scratch copy of the repo at `/tmp/aiorg-cpu` (repo minus `.git`,
  `models.env` overridden as described above), so no state touched the real tree.