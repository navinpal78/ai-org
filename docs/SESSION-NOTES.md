# Session notes — ai-org checker audit

**NOTE: this file was a copy of the live session notes at
`/tmp/opencode/session/notes.md`, originally kept at `~/Work/SESSION-NOTES.md` because `/tmp` may
not survive a reboot. On 2026-09-28 it moved into the repo at `docs/SESSION-NOTES.md`, alongside
`docs/CONTINUE-TOMORROW.md` and `docs/PENDING-WORK.md`, so the audit history is under version
control. The copies in `~/Work` are superseded — this is the canonical one.**

## Objective

Finish and commit the checker-instrument audit in `/home/papa/Work/ai-org`; leave GPU/model-quality
work and the artist/director runtime decision parked pending owner decisions.

**State at the time of writing: the audit objective is COMPLETE and committed.** Remaining work
needs either an owner decision or a decision to start a new audit block (see Pending).

## Important details

- Expected baseline, and what "healthy" means: 16 agents, 607 cases, **500 assertions**, 2 info
  warnings, 0 phantom model tags, 0 family warnings, **exactly 1 error** (deliberate).
- `bootstrap.sh check` **exits 1** by design. That is the known auditor-monoculture error, not a
  regression. If the error count is ever anything other than 1, that is a new problem.
- Git: local branch `main`, 12 commits, 145 tracked files, private remote
  `origin` (`github.com/navinpal78/ai-org`, added 2026-09-28), no uncommitted
  changes.
- Generated machine state is intentionally **untracked** (`.gitignore`): `config/models.env`,
  `config/profile.env`, `state/detect-history.log`, `state/previous-tier`. `config/hardware.json`
  is tracked and contains this box's local hardware, which is a known, accepted quirk.
- GPU work parked by owner instruction (2026-09-27). Do not buy hardware, do not tune prompts
  against small local models, do not treat a CPU or 0.6B score as a quality signal.
- `ollama` is **not** running (was stopped deliberately at the end of the doc-correction pass).
- A fresh clone with no GPU and no model server works: warns 16× to run `./bootstrap.sh detect`,
  then after `detect` reaches 500 checks with 1 known error. Verified twice.

## Work completed this session

All committed. `git log --oneline`:

| commit | what |
|---|---|
| `5c14a09` | initial commit: 16 agents, 607 cases, 359 assertions |
| `6014d1a` | 3 noise bugs in `check_reporting_graph` + tests |
| `80e8ab4` | 6 crashes + comment-only adapter false pass in `check_runtime_registry` + tests |
| `676cd5a` | `tools/` coverage hole in the loopback scan; removed a rule that could not fire |
| `84a5386` | corrected 5 stale claims in the session handoff |
| `92a3fde` | **owned 31 unasserted finding sites; proved the 69th cannot fire** |
| `902ec8b` | stopped the new test from making the project's own check lie |
| `f1b4cad` | recorded the audit's real numbers in AGENTS.md and the handoff |
| `70c6375` | committed the mutation harness so the claim can be re-derived |
| `371a2d8` | round-trip test: audit.sh's writer and check-agents.py's reader |
| `f169415` | documented the audit-log writer/reader seam |
| `f873d81` | tracked the 3 handoff files that lived outside the repo |
| `756a90d` | recorded the remote: pushed to a private `navinpal78/ai-org` |
| `73238a1` | **owned all 9 findings in `check-models.sh`; built the shell mutation harness** |
| `98e9108` | recorded that audit in AGENTS.md and the handoff |

## Second session, 2026-09-28/29 — durability, then the last instrument

Four things, in order, because that is the order they were safe to happen in.

**1. The handoff files moved into the repo.** `SESSION-NOTES.md`,
`CONTINUE-TOMORROW.md` and `PENDING-WORK.md` were the only piece of project state
git did not cover. Password verified absent before staging. The `~/Work` copies
were deleted afterwards, so there is now exactly one of each.

**2. The repo got a remote** — private `github.com/navinpal78/ai-org`, 15
commits. Until then it was only as durable as one disk. Every "no remote" and
"untracked by git" claim in the docs was corrected in the same commit that made
it false, because a doc that says "untracked" about something that is tracked is
the kind of quietly-wrong claim this project keeps having to correct.

**3. `tools/check-models.sh` had no tests at all.** PENDING-WORK item 7 called it
"optional hardening". It was the instrument behind the "0 phantoms" claim, and a
mutation audit found **9 finding sites, 0 owned** — the hand-written count said 5,
and the two it had right by luck included the phantom `[fail]` itself. Now 9/9,
all reachable offline with a fake `curl` on a hand-built `PATH`. 472 → 500.

**4. The harness was the interesting part.** Writing it produced five bugs, four
of which made the audit report a clean tree while measuring nothing. The worst
was `asserted = n - green - skips`: a mutation that never ran was counted as a
pass, so an unbound variable that killed all 8 sites printed a confident 8/8 with
zero false passes. A claim derived by subtracting failures from a constant cannot
tell "the test caught it" from "nothing happened" — which is the same lesson as
the `nvidia-smi` regression and the stderr fixture, one level up. The self-test
now gates it: the harness must report 0/2 on a target nothing tests, or it exits
non-zero rather than print a number.

The generalisable finding, and the one to carry forward: **three separate times
the instrument was right and the thing pretending to be the instrument was
wrong.** Twice in the stubs (the manifest URL puts the tag in the path, not after
a colon; `${@: -1}` on the `/api/show` call is the `-d` payload, not the URL) and
once in the site enumerator. Both stub traps are already documented in
`AGENTS.md` for the *real* tool — the tests walked into them from the other
direction.

### The audit, and the correction that matters

I claimed in two commits and in the handoff that "every function that can emit a finding now has
a test proving it emits one." **That was false.** Measured properly: **31 of 69 finding call sites
had no owner** — silence any one and the suite stayed green.

The 31 were not scattered:
- **12** malformed `agent.conf` values. Every existing test fed `check_agent` a well-formed agent,
  so the whole input-validation half of the function was unowned. A validator that has only ever
  seen good input is indistinguishable from a commented-out one.
- **3** the paths where the checker admits it cannot see the model catalog. The dangerous ones: if
  one goes silent the checker certifies an independence result it never computed.
- **4** one-offs, plus `check_readme_table`'s no-heading warning and `check_runtime_registry`'s
  "no runtimes object".

**Final: 69 sites, 68 owned by an assertion, 1 proved dead.** 415 → 460 checks from this
audit alone; the live suite is now 500 after the check-models.sh audit.

### How to measure this (do not substitute a cheaper method)

Mute one finding at a time; the suite must go red. Name-matching and line coverage both lie:
- naming a function in the test file misses helpers reached through a caller
- a line tracer misses every finding provoked in a subprocess, and a line that *executes* while
  nothing asserts its output is the same false pass as a line that never runs
- **two attempts in this session were wrong** (see `/tmp/opencode/session/notes.md` history below)
- **a third, later: an unmeasured mutation counted as a pass.** See the second-session entry above.
  This is the trap that survives every other fix, because the output looks perfect.

## Work in progress

None. Tree is clean, everything committed and pushed.

Both mutation harnesses are committed: `tools/mutation-audit.py` (the python
checker, `70c6375`) and `tools/mutation-audit.sh` (the shell one, `73238a1`).
Neither ever needed to live in `/tmp`.

## Blocked

- **Owner decisions, three of six now closed:**
  | decision | cost of leaving it |
  |---|---|
  | `artist`/`director` — ComfyUI adapter, or author image specs a human runs? | 2 of 18 agents unbuilt |
  | 28–48GB auditor band — different auditor for the 24GB target, or stay red? | stays deliberately red |
  | pull `devstral:24b` + `gpt-oss:20b` (~30GB) to confirm thinking capability? | `coder` may silently lose thinking on the design-target card |
  | ~~add a `git remote`?~~ | **done 2026-09-28** - private `navinpal78/ai-org` |
  | ~~move `CONTINUE-TOMORROW.md` into the repo?~~ | **done 2026-09-28** - `docs/`, along with the other two |
  | rotate the sudo password pasted into an earlier chat | unrelated to the code |
- **GPU-blocked:** all real agent scores, every `AGENT_LAST_SCORE`, and which uncensored model is
  actually right (`orca2:13b` is picked by size; `dolphin3:8b` is the better prior). Unblocked by
  `./bootstrap.sh detect && all && verify` on the A5000.

## Next steps

1. ~~Commit `tools/mutation-audit.py`~~ — **DONE**, commit `70c6375`. The tree is now fully
   committed: 9 commits, 141 tracked files, 0 uncommitted. There is no uncommitted work.
2. ~~Audit the two remaining untested instruments~~ — **DONE, differently than planned**, commit
   `371a2d8`. Checking whether the mutation method applied first showed `lib/audit.sh` was the
   wrong instrument (it is a *writer*, 0 findings — a findings mutation audit does not apply), and
   that `check-models.sh` has only 5 finding sites vs 69. The better target was a **seam**:
   `lib/audit.sh` writes `state/audit.log`, `check-agents.py` judges every `AGENT_LAST_SCORE` by
   it, and the two had never met — the reader's tests all hand-built log lines. Now tested as a
   real round trip, with two mutations proving it can fail (a renamed KEY, and a truncated VALUE
   that leaves every key intact — the subtler one).
3. ~~Optional: mutation-audit `tools/check-models.sh`~~ — **DONE**, commits `73238a1` and `98e9108`.
   It was called "5 finding sites, 3 needing a live Ollama or a real 404" and "a tenth the size of
   the audit already done". Measurement said **9 sites, 0 owned** — the instrument behind the
   "0 phantoms" claim had no tests at all — and all nine turned out to be reachable offline with
   a fake `curl`, so the "needs a live server" reasoning was the reason nobody had tried. Now
   9/9 owned, via `bash tools/mutation-audit.sh`.
4. Nothing else in the tree. Do not re-derive the parked list; it is in `AGENTS.md` and
   `docs/SESSION-HANDOFF.md`, and every item in it waits on the GPU box or on you.

**The one open thing with no hardware attached** is the `narrative` model role.
`AGENTS.md` records that `storyteller` lands on `gpt-oss:20b` — the CTO's weights — and that
giving the role its own family is a one-line catalog edit. Read the tier table before touching
`config/models.json`: the declaration order is load-bearing and three assertions pin it.

## Relevant files

- `/home/papa/Work/ai-org/tools/check-agents.py` — the audited instrument. 29 functions, 13 emit
  findings, 69 call sites.
- `/home/papa/Work/ai-org/tests/test_retrieval.py` — 500-assertion suite. New:
  `test_every_finding_is_asserted_somewhere`, `test_the_other_unowned_findings`,
  `test_the_audit_log_writer_and_its_reader_agree`,
  `test_check_models_catches_its_own_failure_modes`.
- `/home/papa/Work/ai-org/tools/mutation-audit.sh` — the shell mutation harness.
  Self-testing: it must report 0/2 on a target nothing tests, or it refuses to
  print a number at all.
- `/home/papa/Work/ai-org/tools/mutation-audit.py` — the harness. Committed (`70c6375`).
- `/home/papa/Work/ai-org/AGENTS.md` — project rules, live counts, per-function audit findings, and
  the new "Every finding the checker makes is owned by a test" section.
- `/home/papa/Work/ai-org/docs/SESSION-HANDOFF.md` — full session log; last section is the mutation
  audit, including the two times the measurement itself lied.
- `/home/papa/Work/ai-org/docs/CONTINUE-TOMORROW.md` — next-session entry point. Tracked.
- `/home/papa/Work/ai-org/config/models.json` — 39-tag catalog, 0 phantoms.
- `/home/papa/Work/ai-org/lib/runtime.sh`, `config/runtimes.json` — runtime registry + adapters.

## The four ways I was wrong this session (do not repeat)

1. **Asserted a completeness claim three times without a way to check it.** "Every function that
   can emit a finding has a test" — false, 31 of 69 unowned.
2. **The measurement lied twice.** `idx % WORKERS` chose a scratch *directory* but not a *thread*,
   so four concurrent mutations shared one tree and stomped each other; the total moved between
   identical runs (19, 21, 6). And a mutation that failed to land returned `SKIP`, which I counted
   as *asserted*. A mutation that never happened, reported as a pass, is the exact false-pass shape
   I was hunting. Until both were fixed, my conclusions were unfalsifiable.
3. **Wrote a test that made the project's own diagnostic lie.** It drove `main()` against a fixture
   and captured stdout only; `main()` prints findings to **stderr**. The fixture's fake
   `2 problem(s)` report appeared inside `./bootstrap.sh check` while the real checker said 1 and
   git was clean. The docs say the count must never be anything but 1, so a future session would
   have hunted a regression that did not exist. Nothing caught it because the assertions were
   passing the whole time.
4. **Claimed a branch was dead when it was redundant.** "has no known ceiling" is reachable —
   `check_agent` validates `AGENT_SAFETY` and then hands the same value to `effective_actions`
   independently, so a bad level is reported twice. I was wrong; the test caught it. The one
   genuine dead check is `check_cases`' "has no prompt column" (a string containing its own split
   separator always yields 2+ parts), now asserted dead with the invariant that proves it.

Also: `pkill -f "ollama serve"` matches its own command line and kills the shell running it. Use
`pidof`/`pgrep` on the exact binary name.

## Verification, so a future session can confirm this without trusting it

```bash
cd /home/papa/Work/ai-org
git log --oneline | wc -l          # 16
git remote -v                      # origin -> github.com/navinpal78/ai-org (private)
git status -sb                     # ## main...origin/main, no divergence
git status --porcelain | wc -l     # 0
./bootstrap.sh check 2>&1 | grep -E "checks passed|problem\(s\)"
#   1 problem(s). Fix these before trusting a test score...
#   500 checks passed
python3 tools/mutation-audit.py    # ~5 min: 68/69 owned, 1 proved dead
bash tools/mutation-audit.sh       # seconds: 9/9 owned, and it self-tests first
```

The one error is deliberate and is the 28-48GB auditor monoculture
(`security-engineer` / `cto` both resolving to `qwen3:32b` at 25.0GB usable).
If the error count is ever anything other than 1, stop and investigate — that is
the project's own documented rule, and this session produced a phantom "2
problem(s)" from a test fixture leaking to stderr, which is exactly how a future
session could waste an hour chasing a regression that does not exist.

**`bash tools/mutation-audit.sh` prints its self-test result on the first line.
Read it.** It must say `self-test ok`, and it exits non-zero rather than print a
coverage number if it cannot prove it can fail. A clean `9/9` from a run whose
first line is missing is worth nothing — that is precisely how it reported 8/8
while every mutation was dying.
