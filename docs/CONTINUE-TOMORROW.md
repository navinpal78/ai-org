# Continue tomorrow

_Last updated 2026-09-29. **Nothing is in progress and nothing is uncommitted.**
Clean tree, pushed to a private `github.com/navinpal78/ai-org`.
500 checks, 1 deliberate error._

_What changed since the last version of this file, and the one thing worth
knowing: **`tools/check-models.sh` had no tests at all.** It is the instrument
behind the "0 phantoms" claim - the one that caught `qwen3:72b` and
`qwen3-coder-next:80b` - and a mutation audit found **9 finding sites and 0
owned.** Silencing any one of them left the suite green. It had been filed as
"optional hardening, a tenth the size of the audit already done"; it was in fact
the last instrument in the tree with nothing behind it. All nine are now owned,
offline, and 472 -> 500 checks._

_The second thing worth knowing is how that number nearly lied. The harness
printed a clean **8/8 while every single mutation was dying** on an unbound
variable, because it computed `asserted = n - green - skips` and a mutation that
never ran was counted as a pass. Its self-test had never executed either - the
guard tested a variable after defaulting it. Both are fixed, and the harness now
refuses to print a number at all unless it has proved it can fail. The general
lesson, in `AGENTS.md` under "The last instrument had no tests at all": **a
coverage claim derived by subtracting failures from a constant cannot tell "the
test caught it" from "nothing happened."**_

_Three of the four Tier 1 owner decisions in `PENDING-WORK.md` are now closed:
the handoff files are under Git, and there is a remote. The rest of the parked
list is unchanged and is still waiting on the GPU box. **Do not re-derive it** -
it is in `AGENTS.md` and `docs/SESSION-HANDOFF.md`._

## The one thing to type

```bash
cd /home/papa/Work/ai-org
```

That is it. `opencode` loads `AGENTS.md` from the project directory
automatically, and `AGENTS.md` tells the next session everything: what the
project is, where each part stands, which rules are not obvious, and what to do
next.

If it does not load by itself, type this in the chat instead:

```
read AGENTS.md
```

**Be honest about what is happening here:** I do not remember this
conversation. A new session starts with no memory of it. The only thing that
carries over is what is written to disk. That is why `AGENTS.md` is written for
an agent with zero context - it is not notes for you, it is instructions for
the next me.

**Read `AGENTS.md` rule 22 and the section "The other two judges" before
touching `config/models.json`.** Both are about ways the tree can be quietly
wrong, and both were learned the expensive way.

## Where everything is

| What | Where |
|---|---|
| **Start here tomorrow** | `/home/papa/Work/ai-org/AGENTS.md` |
| Full session log and reasoning | `/home/papa/Work/ai-org/docs/SESSION-HANDOFF.md` |
| Plain-language beginner guide | `/home/papa/Work/ai-org/docs/00-START-HERE.md` |
| Your project | `/home/papa/Work/ai-org/` |

## If you want a summary instead

**16 of the 18 planned agents are built. 607 test cases, 500 retrieval
assertions.** The org chart is complete and now mechanically validated: `ceo`
at the top, `cto` heading the technical department including security,
`research-officer` heading the four research specialists. `personal` - the old
`offline-unrestricted` - was built last, on 2026-09-27.

**All GPU-dependent work is parked by owner instruction, 2026-09-27.** Do not
buy hardware, do not tune prompts against small local models, and do not treat a
CPU or 0.6B score as a quality signal. The card stays on the shelf until the
owner says otherwise.

**The parking list, so it is not re-derived from scratch later.** None of this
is abandoned; it is waiting, and every item says what unblocks it:

| Parked until the GPU arrives | Unblocked by |
|---|---|
| Every real agent score, `personal` included | `./bootstrap.sh detect && all && verify`, then `./tools/test-agent.sh personal` |
| Which unfiltered model is actually right - `orca2:13b` is picked by size, but `dolphin3:8b` is the better prior | one real run of the 18 cases |
| `AGENT_LAST_SCORE` for all 16 agents | same run |
| The 28-48GB auditor-monoculture error (deliberately red) | an owner decision; see `AGENTS.md` |
| `artist`, `director` | a generation runtime, then the card |

**Done since, needs no card:** the two phantom model tags are closed. The catalog
is 39 tags, zero phantoms, verified with `./tools/check-models.sh --online`.
`qwen3-coder-next:80b` was a real repo with an invented tag and is now
`qwen3-coder-next:latest`; `qwen3:72b` never existed and the entry is deleted, so
the 48-64GB band falls back to `qwen3:32b`. Nothing at or below 48GB moved.

**Closed:** `git init` and then the remote. The tree is under version control as
of 2026-09-27 and pushed to a private GitHub repo on 2026-09-28, so it is no
longer only as durable as this disk. The first commit is the state right after
the coverage audit, so `git log` is a readable history of the day.

**What changed most recently, and what it means for tomorrow:**

- **The two undeclared judges are now separated.** `ceo` uses a new `adjudication`
  role (DeepSeek) and `research-officer` uses a new `evidence-review` role
  (Cohere). Both declare `AGENT_INDEPENDENT_OF`, so the checker proves they stay
  separable at **every** card size. Before this, 11 of 15 agents ran on
  `gpt-oss:20b` at 24GB - including every pair whose job is to disagree.
- **A latent crash was found and fixed.** Ollama *rejects* `think:true` for a
  model with no thinking channel, and 8 of 15 agents would have failed **every
  run** on an 8-16GB card, because the models added to `reasoning` yesterday to
  fix the monoculture are all instruct models. `aiorg_effective_think` in
  `lib/common.sh` now downgrades safely. Do not "fix" a future occurrence by
  setting those agents to `AGENT_THINK="off"` - that also kills thinking at 24GB,
  which is the design target.
- **Last night's rename had left the checker crashing, and it is now fixed.**
  `_tier_sampler` was extracted from two callers and one of them still called the
  old name, so `check-agents.py` died with a `NameError` partway through
  `main()`. **All 15 agents were going unvalidated and every other signal read
  green** - the exit code was 1, the same 1 the known auditor error produces.
  A traceback is now a test failure of its own
  (`test_check_agents_reaches_a_verdict`), so this cannot happen quietly again.
  The general lesson is written up in AGENTS.md under "A checker that crashes is
  not a checker that failed".

**Not one agent has a real test score yet**, because that needs the GPU box.
Nothing is verified until `./bootstrap.sh all && ./bootstrap.sh verify` runs on
real hardware. That is the single most important unproven path in the project,
and it is the thing the owner paused.

**One part of that path is now proven.** A real agent run completed end to end
on this CPU box - model server, SOUL, probe, generation, scoring, audit record
- which had never happened before. It used `qwen3:0.6b` on a single case and
proves the *plumbing* works, not that any agent is good.

### What to build next

**Nothing, unless you have decided to.** Every item below is blocked on the GPU
box or on an owner decision, and no amount of work on this box unblocks any of
them. This is the honest state of the project, not an oversight: the parts that
can be built without a card are built and tested.

The two unbuilt agents are blocked on the same thing - a generation runtime this
project does not have:

| Agent | State |
|---|---|
| `artist` | **Blocked on a missing runtime, not just the GPU.** There is no image generation anywhere in this project - the only runtime is `ollama` chat, and the `vision` role *reads* images with `qwen3-vl`. An agent is a chat model, so "artist" cannot literally generate images. Either it authors image specs a human runs, or `lib/runtime.sh` grows a real ComfyUI adapter. Undecided - see the handoff. |
| `director` | Blocked on the GPU, and on the same missing generation runtime as `artist`. |
`offline-unrestricted` is **done.** It was the one item here waiting on a
question from you, and the question is answered. It is `personal`: a private
offline companion, `read-only` and `AGENT_NETWORK="none"` like five other
agents, running on a registry-verified uncensored model, and updated by editing
`config/models.json` and re-running `./bootstrap.sh detect`. "Unfiltered" turned
out to describe the *weights*, not the *permissions* - which is why the name read
like a contradiction and was not one.

### The one question I asked that has not been answered

**Should I pull `devstral:24b` (~16GB) and `gpt-oss:20b` (~14GB) to confirm their
thinking capability?** They are the two models the 24GB design target actually
uses, for `coder` and every `reasoning` agent. `./bootstrap.sh check` prints a
warning that `devstral:24b` has no *recorded* thinking capability, so it runs
`think=off` until confirmed. That is the safe default and not a bug - unrecorded
is treated as "cannot think", because `think:off` on a thinking model merely
costs deliberation while `think:on` on an instruct model means the run never
happens.

So the only cost of leaving it is that `coder` may be losing thinking on the
design-target card. Settling it takes one pull on the GPU box and then:

```bash
./tools/check-models.sh          # asks the model server what each model can do
```

`tools/check-models.sh --online` also re-verifies that every catalog tag exists.
**It currently reports zero phantoms** - the two that were open are closed, and
nothing new appeared. That is the useful result: a checker run on a catalog
believed clean is what confirms the clean-up rather than a fresh catastrophe.

## Four things to be aware of

- **The project is under version control, and now has a remote.** 146 tracked
  files, nothing uncommitted, pushed to a **private**
  `github.com/navinpal78/ai-org` on 2026-09-28. Before that it was 4 commits and
  one disk; the old `~/Work/snapshots/ai-org-2026-09-25.tar.gz` still contains
   only **five** agents and is now superseded - it is not a backup any more, it
   is a museum piece, and nothing since it depends on it.

  Two things deliberately NOT committed, and the reasoning is in `.gitignore`:
  `config/models.env` and `config/profile.env` are rewritten by every
  `./bootstrap.sh detect`, and `profile.env` records *this* box - an i5-5300U
  with no GPU and `AI_TIER="cpu"`, which is the single knob every model decision
  keys off. Committing it would present a CPU-only laptop as the project's
  configuration and be wrong the moment `detect` ran on the A5000. Their absence
  is not silent breakage: a fresh clone prints one warning per agent naming
  `./bootstrap.sh detect` and exits non-zero.

- **`AGENT_LAST_SCORE` is now validated against the audit log.** The
  `helpdesk` fake 100% (a 0.6-billion-parameter model, one case) is why. It is
  reset to `never`, and `check-agents.py` now rejects a score that is not a
  number, is outside 0-100, has no scored run of *that agent* behind it, or is
  higher than any percentage the log ever recorded. A *lower* score is allowed,
  because a prompt or model change can legitimately cost cases. This bullet used
  to say "nothing would have caught it" - that is no longer true.

- **Both phantom model tags are closed; the catalog is clean.** `qwen3:72b`
  (44GB reasoning rung) never existed and the entry is **deleted**, so the
  48-64GB band falls back to `qwen3:32b`. `qwen3-coder-next:80b` (54GB coding
  rung) was a real repo with an invented tag and is now the real `latest`.
  Nothing at or below 48GB moved.

  The replacement decision turned out to have a trap in it, which is the part
  worth keeping: `deepseek-r1:70b` fits the vacated 44GB slot exactly, is real,
  and thinks - and putting it in `reasoning` would have put the CTO on one size
  of DeepSeek while the CEO's `adjudication` role sat on another. **The checker
  would have passed it**, because the two are different tags. It was rejected by
  hand, and the family check added afterwards now warns about that shape
  automatically. See "check-agents.py compares tags, not families" in
  `AGENTS.md`.

- **A sudo password was pasted into an earlier chat session.** It was never
  used and is not written down anywhere in the project. Still worth rotating, if
  you have not already.

---

**One thing that looks broken and is not:** `./bootstrap.sh check` currently
reports **1 error and exits non-zero**, plus two warnings that are information
rather than defects. The error is the known 28-48GB auditor monoculture and it is
deliberate - see "What is still red" in `AGENTS.md`. Everything else is clean:
16 agents, 607 cases, 500 assertions. **If the error count is ever anything other
than 1, that is a new problem.**

The two warnings are expected:

- 8 agents ask for thinking but their role picks a model with no thinking channel
  on a smaller card. Not a broken run - `aiorg_effective_think` downgrades
  `think=on` to `think=off` there. See rule 22 in `AGENTS.md`.
- `devstral:24b` has no recorded thinking capability. See the open question
  above.

**Still open, and the biggest remaining agent-correctness item:**
`security-engineer`/`cto` share `qwen3:32b` in the 28-48GB band. The two judges
that could be separated have been; this one is closed by arithmetic rather than
effort, and needs an owner decision about which model the auditor should be
measured against on a 24GB card. **Do not "fix" it by adding a candidate** - see
the proof in `AGENTS.md`. The 16GB and 24GB bands are safe, so it does not block
the recommended hardware.

## Housekeeping

- The old `ollama serve` process from the smoke test has been stopped. Nothing of
  mine is left running, and nothing needs to be for the next session.
- The Ollama store holds `qwen3:0.6b` and `deepseek-r1:7b` only. A 0.5GB test
  model (`qwen2.5:0.5b`) was pulled to verify the thinking behaviour and has been
  removed again.
- `state/` holds only the audit log and detect history, 12 KB. The research index
  is empty, which is expected.
- The tree is 1.9 MB with no stray temp files.

## Done this session, not yet in the older sections above

- **`tools/check-models.sh` is no longer untested** (commits `73238a1`,
  `98e9108`). It had **9 finding sites and 0 owned** — the hand-written count in
  `PENDING-WORK.md` said 5, and the two it had right by luck included the
  phantom `[fail]` itself. All nine are now owned by
  `test_check_models_catches_its_own_failure_modes`, offline, with a fake `curl`
  on a hand-built `PATH`. 472 → 500 checks.
  **The "3 of its 5 sites need a live Ollama or a real 404" reasoning was why
  nobody had tried it, and it was wrong** — every one is reachable with a stub.
- **A second mutation harness, `tools/mutation-audit.sh`**, for shell
  instruments, kept separate from the python one on purpose: it finds sites by
  grepping, and rule 19 is the reason not to merge two implementations of one
  idea into something neither language can call. It is self-testing and refuses
  to print a coverage number if it cannot prove it can fail.
- **Round-trip test for the audit-log seam** (commits `371a2d8`, `f169415`).
  `lib/audit.sh` *writes* `state/audit.log`; `check-agents.py` judges every
  `AGENT_LAST_SCORE` by it. The two halves had never met — the reader's tests all
  hand-built log lines, so nothing had ever checked that the real writer's
  output (after its aggressive key/value normalisation) is what the real reader
  actually accepts. Now tested as a real subprocess → real reader, deliberately
  on the writer's *default* log path so the test can't line the halves up itself.
  Two mutations prove it fails: a renamed key (`pct` → `percentage`) and, the
  subtler one, a truncated *value* that leaves every key intact.
  460 → 472 checks.
- **`lib/audit.sh` is explicitly NOT a findings-mutation-audit target** — it is a
  writer with 0 finding call sites. That left `tools/check-models.sh` as the only
  remaining instrument worth auditing, and it turned out not to be optional at
  all. **No instrument in the tree is now unaudited.**

---

## Added 2026-09-29: a CPU baseline run, and the `*_THINKS` trap

The first agent runs on this box, against `qwen3:0.6b`, on a **copy** at
`/tmp/aiorg-cpu`. Raw output and a full write-up are in
`~/Work/cpu-baseline-2026-09-29/` — deliberately outside the repo, so no tool
can mistake a 0.6B number for an `AGENT_LAST_SCORE`.

| Agent | Cases | Score | think sent |
|---|---|---|---|
| helpdesk | 21 | 47% | off |
| coder | 19 | 42% | off (downgraded) |
| personal | 18 | 66% | off |
| languages | 47 | 70% | off |
| research-officer | 46 | 32% | off |
| teacher | 32 | **no result** | — |

**These are not agent-quality scores and must never be quoted as such.** 0.6B
is far below the 8B+ weights this project targets, the research agents were run
closed-book (rule 17), and the five completed agents were not even measured
under a consistent configuration with each other. The run was stopped after
5 of 16 agents, 2 hours in.

**`teacher` and `storyteller` cannot run here at all** — the `teacher` and
`narrative` roles bottom out at `qwen3:14b` (10GB) and the CPU fallback is a
nominal 8GB, so `resolve_models.py` emits `# TEACHER_MODEL=""`. Correct
behaviour; 14 of 16 are runnable.

### The finding worth keeping: `*_THINKS` is a property of the *resolved model*

Overriding the model with one `sed` line —

    sed -i 's|_MODEL=.*|_MODEL="qwen3:0.6b"|' config/models.env

— changed every `*_MODEL` and left every `*_THINKS` describing the *original*
catalog model. The tree then looked fine and was internally wrong:

    CODING_THINKS="false"             -> thinking forced off  ->  ~25s/case
    ADVERSARIAL_REVIEW_THINKS="true"  -> thinking actually on  -> ~190s/case

`security-engineer` ran at **3.2 min/case against `helpdesk`'s 16s** — 8x
slower on the same 0.6B — purely because the flag said it could think, and
`qwen3:0.6b` is a qwen3 model, so it did. On that trajectory the full run was
20 hours, not 3, and the scores would not have been comparable to each other.

**This is rule 22 working exactly as designed.** The resolver publishes
`*_THINKS` beside the model tags precisely because the two must move together,
and `aiorg_effective_think` is the only thing that reads them. A *partial*
override is the one mistake that check cannot catch, because the tree is
self-consistent on its face. **If you override a model, override its
`*_THINKS` too, or leave both alone.**

### To resume

    cp -a ~/Work/ai-org /tmp/aiorg-cpu && rm -rf /tmp/aiorg-cpu/.git
    cd /tmp/aiorg-cpu
    sed -i 's|_MODEL=.*|_MODEL="qwen3:0.6b"|; s|_THINKS=.*|_THINKS="false"|' config/models.env
    nohup ollama serve &
    bash ~/Work/cpu-baseline-2026-09-29/aiorg-cpu-run-all.sh

~25s/case, so ~3h for the full 643, comparable across all 14 runnable agents.
Results land in `/tmp/aiorg-cpu-runs/` — copy them out of `/tmp` when done.

### The argument-guard fix, for reference

`--only` (and 13 sibling sites) died silently on a missing value. Fixed as
`aiorg_need_value` in `lib/common.sh`, exits 2. 500 → 516 checks. Detail and
the three ways my own test guessed at an interface instead of running it are in
commit `a2fd763` and `AGENTS.md` rule 23.
