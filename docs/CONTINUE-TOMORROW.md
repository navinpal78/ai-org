# Continue tomorrow

_Last updated 2026-09-27, late. The tree is under version control, both phantom
model tags are closed, and every function in `check-agents.py` that can emit a
finding now has a test proving it emits one. That last item is the one to know
about: **4 of the 5 untested functions were wrong** - six crashes, three noise
bugs, a coverage hole and a rule that could not fire - in a tree whose
`./bootstrap.sh check` was passing the whole time. The full account is the last
section of `docs/SESSION-HANDOFF.md`; `AGENTS.md` carries the per-function
findings._

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

**16 of the 18 planned agents are built. 607 test cases, 415 retrieval
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

**Closed:** `git init` - the tree is under version control as of 2026-09-27, 4
commits, 141 tracked files, clean working tree. It had been offered five times
before it was approved, and the first commit is the state right after the
coverage audit, so `git log` is a readable history of the day.

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

Two agents left, and they are blocked on the same thing - a generation runtime
this project does not have:

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

- **The project is under version control as of 2026-09-27.** Four commits on
  `main`, 141 tracked files, nothing uncommitted, no remote. The old
  `~/Work/snapshots/ai-org-2026-09-25.tar.gz` still contains only **five**
  agents and is now superseded - it is not a backup any more, it is a museum
  piece, and nothing since it depends on it.

  **There is no remote**, so the repository is only as durable as this disk.
  That is the remaining half of the problem the git init solved, and it is
  yours to close:

  ```bash
  cd /home/papa/Work/ai-org && git remote add origin <url> && git push -u origin main
  ```

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
16 agents, 607 cases, 472 assertions. **If the error count is ever anything other
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

- An `ollama serve` process (pid 85804) is still running, left over so the smoke
  test could reach a model server. Harmless - `pkill ollama` stops it. Nothing
  else is running.
- The Ollama store holds `qwen3:0.6b` and `deepseek-r1:7b` only. A 0.5GB test
  model (`qwen2.5:0.5b`) was pulled to verify the thinking behaviour and has been
  removed again.
- `state/` holds only the audit log and detect history, 12 KB. The research index
  is empty, which is expected.
- The tree is 1.4 MB with no stray temp files.

## Done this session, not yet in the older sections above

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
  writer with 0 finding call sites. `tools/check-models.sh` (5 finding sites) is
  the only remaining instrument worth auditing, and it is optional: 3 of its 5
  sites need a live Ollama or a real 404. The catalog is currently correct (0
  phantoms), so this is hardening, not a known red.
