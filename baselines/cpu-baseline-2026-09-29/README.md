# CPU baseline run, 2026-09-29 — DO NOT READ THESE AS AGENT SCORES

Raw output from running the closed-book suite on this box: **no GPU, 4 cores,
7.6GB RAM, `qwen3:0.6b`.** Nothing here is a measurement of agent quality.
It is a plumbing check that the harness runs end to end, plus a record of one
real finding.

## Why these numbers must not become scores

Three independent reasons, any one of which is disqualifying:

1. **The model is `qwen3:0.6b`.** The project is designed for 8B+ weights, and
   `AGENTS.md` says outright not to tune prompts against small local models,
   because it distorts them for the models actually used.
2. **`think` was inconsistent between agents.** See below. Different agents
   were measured under different configurations, so they are not comparable to
   *each other* either.
3. **Closed-book.** The five research agents declare `AGENT_RETRIEVAL="on"` and
   are *meant* to be run with sources injected. These are their closed-book
   numbers, which `AGENTS.md` rule 17 exists to keep from being mistaken for
   research scores.

These were kept in `~/Work/` and, since 2026-10-13, committed to the repo under
`baselines/` as a durability backup — but **kept out of the tooling path on
purpose**: no script reads `baselines/`, so no tool can pick them up as an
`AGENT_LAST_SCORE`. The real tree still has `AGENT_LAST_SCORE="never"` on all 16
agents and a 5-line audit log. See `baselines/README.md`.

## Results (5 agents completed, 2 could not run)

| Agent | Cases | Score | think sent |
|---|---|---|---|
| helpdesk | 21 | 47% | off |
| coder | 19 | 42% | off (downgraded) |
| personal | 18 | 66% | off |
| languages | 47 | 70% | off |
| research-officer | 46 | 32% | off |
| teacher | 32 | **no result** | — |
| security-engineer | 37 | **incomplete, 15 cases** | **on** |

`teacher` and `storyteller` **cannot run on this box at all.** The `teacher` and
`narrative` roles bottom out at `qwen3:14b` (10GB of VRAM), and the CPU
fallback is a nominal 8GB, so `resolve_models.py` leaves those two variables
empty in `config/models.env`:

    # NARRATIVE_MODEL=""
    # TEACHER_MODEL=""

That is correct behaviour, not a defect. 14 of 16 agents are runnable here.

## The one real finding: `*_THINKS` is coupled to the resolved model

I overrode the model with one line:

    sed -i 's|_MODEL=.*|_MODEL="qwen3:0.6b"|' config/models.env

which changed the `*_MODEL` variables and left the `*_THINKS` variables
describing the *original* catalog models. So the tree ended up internally
inconsistent:

    CODING_THINKS="false"              -> thinking forced OFF  -> ~25s/case
    ADVERSARIAL_REVIEW_THINKS="true"   -> thinking actually ON -> ~190s/case

`security-engineer` ran at **3.2 min/case against `helpdesk`'s 16s** — 8x
slower for the same 0.6B — purely because the flag said it could think and
`qwen3:0.6b` is a qwen3 model, so it did.

**This is rule 22 working as designed, and I broke it.** `*_THINKS` is a
property of *the resolved model*, and the whole reason the resolver publishes
those flags next to the model tags is that the two must move together. A
partial override is the one thing that check cannot protect you from, because
by then the tree is self-consistent-looking and internally wrong.

**If you override a model, override its `*_THINKS` too** — or leave both alone.

## To resume

The copy at `/tmp/aiorg-cpu` is gone after a reboot, which is fine; it is
reproducible. From the repo:

```bash
cp -a ~/Work/ai-org /tmp/aiorg-cpu && rm -rf /tmp/aiorg-cpu/.git
cd /tmp/aiorg-cpu

# Consistent this time: model AND capability flags move together.
sed -i 's|_MODEL=.*|_MODEL="qwen3:0.6b"|; s|_THINKS=.*|_THINKS="false"|' config/models.env

nohup ollama serve &                 # if not already running
bash ~/Work/cpu-baseline-2026-09-29/aiorg-cpu-run-all.sh
```

With `*_THINKS` all false, expect ~25s/case and **~3h for the full 643**,
comparable across all 14 runnable agents. `teacher` and `storyteller` will still
report no result.

Results are written to `/tmp/aiorg-cpu-runs/`. Copy them out of `/tmp` when the
run finishes.

## Reading a failure, if you do run this again

`AGENTS.md` is right that a 0/1 on a correct reply is a broken test, not a bad
prompt. I checked one by hand:

    case  triage-asks-scope-first
          ::: My internet is not working. Fix it.
          ::: one machine || other machines || both || all of them
    0.6B  "Could you describe what you're seeing? For example, is there a
          connection, a firewall, or a problem with your router?"

It asked a *symptom* question, not a *scope* question. A real helpdesk agent
asks whether this is one machine or all of them first — that is the entire
point of the case, and the test is correct. The 0.6B is too weak. So at least
one of these failures is a real model failure and not a bad case, which is the
only reason any of this is worth keeping.
