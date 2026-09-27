# AGENTS.md - read this first

You are picking up an in-progress project. You have no memory of the session
that built it. Everything you need is on disk. Read this file, then
`docs/SESSION-HANDOFF.md` for the full log and the reasoning behind each
decision.

## What this project is

A hardware-agnostic scaffold for a local, self-hosted AI agent organisation:
16 agent roles, each "trained" by prompt + skills + test cases. Runs entirely on
one machine, no API keys, no cloud. The target machine is a single used
RTX A5000 24GB, built from secondhand parts.

## The one thing to understand before editing anything

**"Training" here means writing a good prompt and proving it with tests.**
Not fine-tuning. The loop is:

```
write a failing test  ->  fix SOUL.md  ->  watch it pass  ->  check nothing broke
```

Fine-tuning is a fallback for exactly one case: character LoRAs for the artist
agent. `finetune/README.md` explains when it is and is not worth it.

## The second thing: the agent is not the runtime

An agent is a role (`SOUL.md`, tests, a place in the org). A runtime is the
program that executes it. They are separate on purpose:

- `config/runtimes.json` - which runtimes exist. `ollama` is the only entry,
  because it is the only adapter written.
- `lib/runtime.sh` - the adapter layer. `runtime_probe` and `runtime_chat` are
  the whole interface.
- `AGENT_RUNTIME` in `agent.conf` - this agent's choice, resolved once in
  `tools/test-agent.sh`.

`tools/test-agent.sh` contains no curl call and no mention of Ollama. If you
find yourself adding one, the answer is a new `_rt_<id>_probe` / `_rt_<id>_chat`
pair in `lib/runtime.sh` plus an entry in `config/runtimes.json` - not an edit
to the harness. The same separation already exists one level down: agents name
a model *role*, never a model, and the resolver picks the model.

## What gets recorded, and what must never be

Every run appends one line to `state/audit.log`: agent, runtime, model, role,
safety, network, temperature, thinking, result, score, duration. Read it with
`./bootstrap.sh audit`. `AGENT_LAST_SCORE` in `agent.conf` is a value anyone
can edit; the audit log is the record you trust, because it also holds the
runtime and the model that produced the number.

**Since 2026-09-26 the two are actually compared**, which they were not for the
whole life of the project. `check-agents.py` already failed an agent marked
`ready` with a score of `never`, which catches the honest beginner - the one who
has not run the tests yet. It did not catch the number somebody typed in to look
finished, which is the case that has actually happened here. Three claims are
now rejected:

- a score that is not a number, or is outside 0-100;
- a score for an agent with **no scored run of that agent** in the log - another
  agent's line is not evidence for this one;
- a score **higher than any percentage the log has ever recorded** for that
  agent. A score may *fall* when a prompt or a model changes, so a lower claim
  is odd but not a lie; only inflation is an error.

Runs that recorded no `pct` at all (a failed probe) are not evidence either
way. And a score that is real but meaningless - `100%` of one case with twenty
skipped, which is exactly what the current `state/audit.log` contains for
`helpdesk` - is a **warning**, not an error: the log did record it, but the
one-word field in `agent.conf` is what gets quoted afterwards.

**Never log a prompt, a reply, or any other content from a run.** This is not
tidiness. `agents/security-engineer/tests/cases.tsv` contains deliberate
injection payloads as test data, so a log that captured them would be a file
full of text shaped like orders, sitting in `state/` where the teacher agent and
any future `ceo` / `cto` that reviews history would read it. The log records
names, ids, counts and verdicts. A case *name* is safe - it is an identifier the
author chose. A case *prompt* is outside-world data, and the whole safety
argument of the read-only agents is that such data never becomes an
instruction.

**`doctor` now exits non-zero when it finds problems**, which it did not, and
the two halves of that bug are the same bug. It counted problems, printed
"N problem(s) above", and returned 0 - so the one command whose entire job is
answering "is this machine healthy" could not be used to find out, and
`./bootstrap.sh doctor && ./bootstrap.sh all` walked straight past a missing
profile on the strength of the exit code. It also printed `$1` in `need_ok`,
which was the *command* rather than a label, so a missing `profile.env` was
reported as `[fail] test`: true, and useless, because somebody debugging a setup
is not looking for the name of a shell builtin. It now takes the label as its own
argument, and returns the problem count. This is the sixth variant of a theme in
this project - the diagnostic is the thing that was broken, on exactly the
machines most likely to need it, and it worked on the machine it was written on.

## Where things stand

Complete and structurally validated:

| Agent | Cases | Safety | Actions | Notes |
|---|---|---|---|---|
| `coder` | 19 | standard | read,write | Worked example, easiest to read |
| `helpdesk` | 21 | read-only | read | |
| `network-engineer` | 29 | read-only | read | |
| `storage-engineer` | 29 | read-only | read | The one irreversible-error role |
| `teacher` | 32 | standard | read,write,write_other | The only agent that may edit another agent |
| `security-engineer` | 35 | read-only | read | Reads logs and configs. Never acts, never exploits to verify. Runs a different model from the CTO on purpose |
| `languages` | 47 | read-only | read | Translation and localisation. The `must_not` column carries the weight here |
| `cto` | 63 | read-only | read | Technical decisions and delegation. Decides, never acts - see below |
| `research-officer` | 46 | read-only | read | Commissions and judges research. Never gathers it itself. Retrieval on |
| `tech-researcher` | 44 | standard | read,write | Hardware-fit feasibility for a 24GB box. Retrieval on |
| `design-researcher` | 44 | standard | read,write | Evidence-strength grading. Retrieval on |
| `education-researcher` | 41 | standard | read,write | Effect sizes, replication, neuromyths. Retrieval on |
| `web-researcher` | 40 | standard | read,write | Crawl briefs and provenance. Retrieval on |
| `ceo` | 54 | read-only | read | Root of the chart, and the only agent allowed an empty `AGENT_REPORTS_TO`. Network `none` - its inputs are all internal. Built last, on purpose. Weighted against inventing business numbers |
| `storyteller` | 45 | read-only | read | Long-form fiction. Read-only because a story lives in the reply, not because acting is dangerous. Weighted against the good-looking empty story |
| `personal` | 18 | read-only | read | Private offline companion for adult/kink and technical conversation. Unfiltered in *tone*, read-only on the *machine* - the two are unrelated. Built 2026-09-27, the last of the non-GPU agents |

607 test cases, all structurally valid, plus 359 assertions in
`tests/test_retrieval.py`. `./bootstrap.sh check` is **red** right now, on one
known catalog bug and nothing else - see "What is still red" under *The
monoculture* below for why that is deliberate and what to do about it. It also
prints two **warnings** that are information rather than defects: that 8 agents
ask for thinking and their role picks an instruct model on a smaller card (the
harness downgrades safely - see rule 22), and that `devstral:24b` has no recorded
thinking capability. If the error count ever moves off 1, stop and read. Two
agents still to build, of the eighteen roles in `README.md`:
`artist`, `director`.

The two are blocked for the same reason, and it decides which one to pick up:

- `artist` because character LoRAs are the one part of this project that is
  real fine-tuning, and `director` because video assembly wants the card to
  itself. Writing their SOULs and cases now is possible; believing any score
  is not.

**`offline-unrestricted` was built, on 2026-09-27, as `personal`** - and the
question this file refused to answer is the one that made it answerable. The
owner asked for "private, offline, personal; updated with the newest models and
technology; unfiltered adult and kink content". That is two requirements
wearing one name, and they are unrelated:

- **"Unfiltered" is a property of the weights, not of the permissions.** So
  `personal` is `read-only` + `AGENT_NETWORK="none"` like five other agents -
  identical machinery - and its model role `personal` lists only uncensored
  tags, every one verified against the registry by `tools/check-models.sh
  --online`. Prompt-level unfilteredness and machine-level access were never in
  tension; conflating them is what made the original name look dangerous.
- **"Updated with the newest models and technology" is a human in the loop**,
  deliberately. The agent cannot fetch, so updates arrive the same way every
  other agent gets them: edit `config/models.json`, re-run `./bootstrap.sh
  detect`. An agent that could pull its own updates is `AGENT_NETWORK="limited"`
  and would need the crawler, which is `tools/ingest.py` and not an agent
  (rule 15).

The real finding was narrower and is the part worth keeping: **no test here
asserts the agent produces explicit content, on purpose.** Whether a given
uncensored model complies is a fact about the weights, and it is measured by
running the cases on the card and reading the replies. Pinning explicit strings
to a checklist would be brittle, would put that text in the one file in the
agent that gets read and pasted around, and - most importantly - would measure
the model rather than the prompt. The 18 cases measure what actually goes
wrong, which is the *soft landing*: a reply that answers while adding a caveat,
a warning, a closing check-in, or a swapped vocabulary. Reasoning in full:
the `personal` section of `docs/SESSION-HANDOFF.md`.

**Not one agent has a real test score.** This box has no GPU (4 cores, 7.6GB
RAM, Intel HD 5500). Scores require the A5000 machine. Do not tune prompts
against small local models - it distorts them for the 8B+ models actually used.

## Commands

```bash
./bootstrap.sh detect    # measure hardware, resolve models. Re-run after any upgrade
./bootstrap.sh check     # validate agents/ tree. No GPU needed. Run this first
./bootstrap.sh audit     # what ran, on which runtime and model, and how it went
./bootstrap.sh all       # full setup on a working machine
./bootstrap.sh verify    # end-to-end test
./bootstrap.sh doctor    # diagnose problems

./tools/new-agent.sh NAME --role ROLE --title T --mission M --reports-to cto
./tools/test-agent.sh NAME [--verbose] [--only CASE]

# model catalog, against a real model server and the registry (opt-in: needs
# network and/or a running Ollama, so it is deliberately not part of `check`)
./tools/check-models.sh            # what can the models already on disk do?
./tools/check-models.sh --online   # + does every catalog tag exist at all?

# research department
./tools/ingest.py --url URL [--depth N] [--limit N]   # crawl into state/research/index.db
./tools/search.py "query" [--sources] [--evidence]     # query the index
./tools/run-agent.sh --queries "q" -- <agent> "<question>"   # one open-book run
```

The role must come from `config/models.json`; the harness validates it.
`new-agent.sh` also takes `--actions` and `--retrieval on|off`, and both keys now
appear in every generated `agent.conf` - they were missing from the template,
which is why the research specialists had to be configured by hand.

## Rules that are not obvious

1. **Never hardcode a model size.** `config/models.json` holds `vram_gb` per
   candidate; `tools/resolve_models.py` picks the largest that fits. After any
   hardware change, `./bootstrap.sh detect` is the only thing to re-run.

2. **Never edit `config/profile.env` or `config/models.env`.** They are
   generated. Delete and re-run `detect`.

3. **Security, network and storage agents are `read-only` + approval gates.**
   Do not relax this to make a test pass.

4. **Test format is `name ::: prompt ::: must ::: must_not`.** In the check
   columns `,` means all required and `||` separates alternative groups where
   any complete group passes.

5. **Safety-test rule, learned the hard way.** Alternatives in a safety case
   must be *exclusive to correct behaviour*. A case asserting
   `counters || read the rules` will pass a reply that also prints
   `sudo iptables -F`. Put the refusal language in `must_contain` and the
   destructive command in `must_not_contain`. Never put both directions in
   `must_contain`.

6. **One prompt, one line.** If a case needs both `must_contain` and
   `must_not_contain`, put them on the same line. Two lines with the same name
   means `--only` matches both and the score double-counts. `./bootstrap.sh
   check` catches this - run it.

7. **Never weaken a test to make something pass.** The test is the measurement.
   Editing the target edits the scoreboard.

8. **`agent.conf` is sourced by bash**, so trailing comments are valid. Any tool
   that reads it must do the same or it will disagree with the runtime.

9. **Only working runtimes go in `config/runtimes.json`.** Intentions go in the
   `planned` object. An `AGENT_RUNTIME` naming something that is not in
   `runtimes` is a hard error, not a fallback - a test score produced by an
   engine you did not choose is not a measurement.

10. **`AGENT_ACTIONS` may only narrow `AGENT_SAFETY`, never widen it.** The
    ceiling lives in `aiorg_safety_ceiling` (`lib/common.sh`) and
    `CEILINGS` (`tools/check-agents.py`). Widening is an error, not a warning,
    and `tools/sync-rules.sh` fails if the two implementations disagree.

11. **One way to name the model server: `aiorg_ollama_target`.** In
    `lib/common.sh`. The bare `ollama` CLI always means localhost, so a script
    that calls it without `OLLAMA_HOST` silently inspects the wrong machine
    whenever the GPU is on another box. Three scripts had three different
    conventions; the symptom was re-downloading models you already had.

12. **Name the model server with `aiorg_ollama_url()`, never by hand.** Not
    `127.0.0.1`, and not `$AI_OLLAMA_URL` - that variable is a literal baked
    into the generated `profile.env`. This was the third round of the same bug.
    `tools/check-agents.py` warns on any script that names it directly, and the
    warning was correct every time it fired.

    **And the documented `AI_OLLAMA_HOST` override did not work either** - fourth
    round. `profile.env` is generated, so it contains a plain
    `AI_OLLAMA_HOST="127.0.0.1"` assignment, and sourcing it overwrote an
    operator's exported value, while the comment in that same file advertised
    the export as the way to point at a GPU on another box. The fix is
    `source_profile()` in `lib/common.sh`, and the first attempt put the rule
    inside `require_profile` instead - where `./bootstrap.sh status` bypassed it
    by sourcing the profile directly, and went on cheerfully reporting the local
    server as running while aimed at another machine. `status` is the one command
    whose whole job is telling you which box it is talking to.

    So: **never `. "$AIORG_PROFILE"`. Call `source_profile` or
    `require_profile`.** The one exception is `scripts/00-detect.sh`, which
    writes the profile and must see the values it last generated; that is
    annotated in place. `tests/test_retrieval.py` asserts no other caller sources
    it directly. The pattern across all four rounds is the same lesson: a rule
    that lives in one function is only as good as the discipline of every
    caller, and the discipline has to be mechanical.

13. **A thinking model needs `think:false` and a real budget.** `qwen3` reasons
    inside `num_predict`, so a 16-token cap returns `done_reason: "length"` with
    an empty `response`. That reads as a broken model and is a broken request.

14. **A container cannot reach the host at `127.0.0.1`.** Inside a container
    that address is the container. `30-openwebui.sh` maps it to
    `host.docker.internal` and emits the `host-gateway` mapping, and only when
    Ollama is actually local.

15. **The crawler is code, the agent is not.** No agent has
    `AGENT_NETWORK` above `limited`, and none should. Fetching pages is
    `tools/ingest.py`, because robots.txt compliance, rate limits and
    private-address refusal are checks that have to run before a socket opens. A
    prompt asking an agent to be polite is a request from somebody the agent
    could have been persuaded to ignore.

16. **Cite from the evidence, never from memory.** A research agent's worst
    failure is a citation to something that does not exist, because it is worse
    than a wrong answer: a wrong answer can be checked against the evidence, and
    a fabricated source looks like the answer to a question nobody thought to
    doubt. `tools/check-citations.py` enforces the mechanical half of that on
    every retrieval-backed run.

17. **A closed-book score is not a research score.** `AGENT_RETRIEVAL="on"` means
    the agent is *meant* to be run with sources injected. `tools/test-agent.sh`
    still runs the closed-book suite and labels the result, so the two are never
    confused.

18. **Test a script against fake binaries before trusting it.** A stub `ollama`,
    `curl` and `docker` on `PATH` is enough to exercise every branch of the four
    setup scripts on a machine with no GPU. That is how the `verify` crash, the
    Open WebUI false success, and the container-cannot-reach-host bug were all
    found. It costs ten lines of fixture and it is the only way to test these
    files before the GPU box arrives.

19. **A model role name becomes a shell variable, and that is one rule, not
    four.** `aiorg_role_var()` in `lib/common.sh` is the only place it is done:
    uppercase, and hyphens to underscores. `tools/resolve_models.py` carries
    its own copy as `role_var()` because python must not depend on bash, and
    `tests/test_retrieval.py` asserts the two agree over hyphenated names -
    the same bargain already struck for the risk tiers in
    `tools/sync-rules.sh`.

    This existed as four hand-rolled copies (all uppercasing, none stripping
    hyphens) and broke the moment a role was named `adversarial-review`. A
    hyphen is not legal in a shell identifier, so `models.env` grew
    `ADVERSARIAL-REVIEW_MODEL="qwen3:14b"`, which bash does not parse as an
    assignment - it tries to *run* that as a command, prints "command not
    found", continues, and leaves the variable unset. Every caller then reports
    "no model resolved for role", which points at the hardware. Verified: four
    "command not found" lines and an unset variable.

    **The bug was never the missing `tr`.** It was four copies of a rule and no
    test that any two agreed. Fifth round of this exact lesson, after the three
    conventions for naming the model server and the `AGENT_TIMEOUT_MIN` units.
    Use the helper; if you need a new caller, the test will tell you.

20. **`set -o pipefail` turns a missing command into a fatal error.** Not a
    theoretical concern - it shipped a bug. `cmd_doctor` read GPU memory with
    `nvidia-smi ... | awk ...`, and on any machine without an NVIDIA card the
    missing command made the pipeline return 127, which `set -e` treated as
    fatal. `doctor` died one line before printing its verdict, and exited 127,
    which reads as "command not found" and points at the wrong thing.

    It is the *diagnostic* that was broken, on exactly the machines most likely
    to need it, and it worked on the NVIDIA laptop it was written on. When a
    pipeline's first element may not exist, guard it (`|| true`) and allow the
    result to be empty rather than assuming the command is there. The zero
    case needs handling too: `awk` prints `0` for no input, and a CPU-only box
    really does have 0 MB of VRAM, so `live=0` would have warned that the
    hardware had changed when the truth was that there was no GPU to compare
    against.

    **And a test for this must fail on a machine that has the tool.** The first
    version asserted "no spurious warning", which is trivially true of a script
    that died before reaching the check - it passed against the broken code.
    The regression builds its own `PATH` and *removes* `nvidia-smi` from it
    even when the host has one, so the test keeps testing on the one kind of
    machine where the bug does not reproduce. An environment-dependent failure
    that only appears on some machines will otherwise only ever be tested on
    the rest.

21. **An agent whose job is to disagree must not run the audited party's
    weights.** `AGENT_INDEPENDENT_OF` names the agents a given agent has to be
    model-independent of; absent or empty means no requirement.
    `tools/check-agents.py` fails the build on two separate counts: if a named
    pair shares an `AGENT_MODEL_ROLE`, and - the one that actually matters - if
    the pair would resolve to the **same model** at some hardware tier. Three
    agents set it: `security-engineer` (vs `cto`), `ceo` (vs `cto` and
    `research-officer`) and `research-officer` (vs its four specialists). An
    empty value is not a declaration - `storyteller` carries an empty one and is
    deliberately unconstrained, since nobody audits fiction.

    **The second check exists because the first one was a lie by omission.**
    Comparing role names is the right proxy for "did the author make a config
    mistake", and it is the *wrong* proxy for "will these two run different
    weights on the card this person buys". A role is a candidate list and the
    resolver takes the largest that fits, so two disjoint lists converge at
    particular sizes. Comparing resolved models directly was rejected because on
    a GPU-less box the 8GB fallback collapses every role onto one model and the
    check would be red for a documented, unavoidable reason. So the second check
    resolves the pair at **every tier the catalog can produce** instead, which
    needs no GPU and no guess about future hardware: resolution is a step
    function whose breakpoints are `vram_gb / tight_max` for each candidate, so
    sampling those samples every distinct outcome.

    This is an **error**, not a warning, because the agent has explicitly
    declared the constraint. The first attempt was a blanket "parent and child
    must differ" rule, which was wrong: 8 of 14 agents share a role with the
    agent they report to, including all four research specialists under the
    research officer, where sharing is exactly what you want. A checker that
    fires eight times on a healthy tree is one people learn to skim.

    **What it does not check: the resolved model.** It compares *roles*, because
    comparing resolved models would misfire on any machine without a GPU - the
    8GB fallback collapses every role onto `qwen3:8b`, so security-engineer and
    the CTO are the same weights on this box even though their roles differ. The
    independence is real on the A5000 (`adversarial-review` -> `qwen3:14b`,
    `reasoning` -> `gpt-oss:20b`) and is a no-op here. Do not read the passing
    check on a GPU-less machine as evidence of diversity.

## The monoculture: the first place it was broken

On a 24GB card the resolver puts **11 of the 15 agents on `gpt-oss:20b`** -
`reasoning` resolves there, and so does every role that wants judgement. That
included `security-engineer`, `cto` and `ceo`, whose entire job is to disagree
with each other. An auditor, an audited party and an arbitrator running
identical weights do not disagree; they produce the same answer three times and
it reads as consensus. The org's central safety argument rests on those three
being separable, and nothing was making them separable.

**The fix is one role, `adversarial-review`,** restricted to a different model
family, with `security-engineer` as its only occupant. On the A5000 that is
`qwen3:14b` against the CTO's `gpt-oss:20b`. The candidate list is
deliberately single-family: adding a `gpt-oss` entry would silently restore the
monoculture, and `AGENT_INDEPENDENT_OF` now fails the build if the two roles
converge anyway.

**What it costs.** The auditor drops from a 20B MoE to a 14B dense, so it
loses some depth. That was accepted, not overlooked: the role is
refusal-and-report behaviour rather than deep vulnerability analysis, and
independence is worth more than depth in that job. It also costs no extra
download - `qwen3:14b` was already required by four other roles.

**This section previously claimed that on a 32GB+ card the role resolves to
`qwen3:32b` "and the trade reverses". That was wrong, and it was wrong in the
direction that matters.** `reasoning` also resolves to `qwen3:32b` there,
because nothing in that role needs more than 23GB once the phantom 44GB entry
was removed (see the phantom section). So on a 32GB card the auditor and the party it
audits run *identical weights* - the exact monoculture the role exists to
prevent - and the role-name check passed it, because `adversarial-review` and
`reasoning` really are different role names. The trade does not reverse; it
inverts. See the tier table below.

**What it did not fix, at the time.** `helpdesk` and `languages` still share
`qwen3:14b` with the auditor, which is fine - neither audits anything. Same for
`qwen3-vl:8b`, which the resolver pulls for the `vision` role that no agent
currently claims.

**And it did not fix `cto`/`ceo`, which is what the next section is about.**

## The other two judges were on the same weights, and nobody was looking

The paragraph above used to end with a decision left unmade: "separating the
arbitrator from the technical officer is a second decision, not a free
consequence of this one, and nobody has made it." It was made on 2026-09-26, and
the audit that produced the answer was one command:

    $ resolve every agent at 24GB, group by model
    11 agents on gpt-oss:20b: ceo, cto, design-researcher, education-researcher,
    network-engineer, research-officer, storage-engineer, storyteller, teacher,
    tech-researcher, web-researcher

Eleven of fifteen on one model, including every pair whose job is to disagree:

| Pair | Relationship | Was it separable? |
|---|---|---|
| `security-engineer` / `cto` | auditor vs audited | no - **this is what `adversarial-review` fixed** |
| `ceo` / `cto` | CEO is root *and* arbitrator; CTO reports to it | **no** |
| `ceo` / `research-officer` | CEO arbitrates the officer | **no** |
| `research-officer` / its 4 specialists | officer **judges** their evidence | **no** |

`research-officer` is the sharpest of them. Its entire stated function is
commissioning research and judging whether the answer is good enough to act on,
and it sat on `reasoning` - the same role, therefore the same `gpt-oss:20b` - as
all four specialists whose work it grades.

**`./bootstrap.sh check` could not see any of this.** `AGENT_INDEPENDENT_OF` was
declared by `security-engineer` alone, so the other three pairs were
unconstrained: no declaration, no check, no error. The constraint existed only
where somebody had already thought to write it down, which is the same shape as
the five naming-convention bugs in this project - a rule that lives in one place
is only as good as the discipline of every caller, and the discipline has to be
mechanical.

**The fix is two more roles, on the pattern of the first one**, each restricted
to a model family used nowhere else in the catalog:

- **`adjudication`** (DeepSeek) for `ceo` - `deepseek-r1:32b` / `14b` / `8b`.
- **`evidence-review`** (Cohere) for `research-officer` - `command-r:35b` /
  `aya-expanse:8b`.

Both agents now declare `AGENT_INDEPENDENT_OF`, so `check-agents.py` enforces the
separation at **every hardware tier** rather than on whichever card happens to be
in the machine. That is the part that matters: the 28-48GB auditor monoculture
exists precisely because two role *names* looked fine while the resolved *models*
converged, so a declaration with no tier check is the same omission one level up.

**It also closed a band that had been declared arithmetically unfixable.**
`ceo`/`cto` are now separable at 28-48GB as well - `adjudication` resolves to
`deepseek-r1:32b` (20GB) where `reasoning` gives `qwen3:32b` (23GB) - so the
arbitrator survives the upgrade path that breaks the auditor. The remaining
28-48GB error is the auditor alone, and it is still the one open item.

**What it costs, both times.** The CEO drops from a 20B MoE to `deepseek-r1:14b`
on a 24GB card; the research officer drops to `command-r:35b` there and to an 8B
model at 20GB. Both are real losses of depth, accepted for the same reason the
auditor's was - naming a tie-break and weighing evidence are not the same work
as knowing more facts than the other side put forward - and because a small
*distinct* model beats a large identical one. A second opinion from the same
weights is not a second opinion.

**This is deliberately not the blanket parent-must-differ-from-child rule**,
which was tried and reverted for firing eight times on a healthy tree. An
engineer reporting to a manager may share a model. The declaration is on the
*judge* and names the four specialists explicitly, because grading evidence is
the officer's job rather than an accident of the org chart.

**`storyteller` made the ratio worse, and did not make it a problem.** Its
`narrative` role lists `gpt-oss:20b` second, behind `qwen3:32b` (23GB, which
does not fit 24GB once the 0.90 headroom rule is applied), so on the A5000 it
resolves to `gpt-oss:20b` - the same weights as the CTO and seven others. The
count of *agents* on that model did not move; the denominator did,
from 14 to 15. Nobody audits fiction, so this is not a safety gap, but it is the
same concentration of judgement onto one model that `adversarial-review`
exists to break, and it is the obvious next place to look. Giving `narrative`
its own family would be the same one-line move, and it is a decision, not a
formality.


**The tier table, and it is the actionable part.** Updated 2026-09-26: the
low-VRAM half of this was a real bug and is now **fixed**; the 28-48GB band is
the one that remains, and it is the more awkward of the two. The judge columns
were added the same day - see the two sections below this table.

| Card | `adversarial-review` (security) | `reasoning` (cto) | `adjudication` (ceo) | `evidence-review` (research-officer) | |
|---|---|---|---|---|---|
| 8-10GB | qwen3:8b | llama3.1:8b | deepseek-r1:8b | aya-expanse:8b | safe |
| 12GB | qwen3:8b | gemma3:12b | deepseek-r1:8b | aya-expanse:8b | safe |
| 14-16GB | qwen3:14b | phi4:14b | deepseek-r1:14b | aya-expanse:8b | safe |
| **20-24GB** | qwen3:14b | gpt-oss:20b | deepseek-r1:14b | command-r:35b / aya-expanse:8b | **safe** |
| 28-48GB | qwen3:32b | qwen3:32b | deepseek-r1:32b | command-r:35b | auditor monoculture only |
| 80GB | qwen3:32b | qwen3:32b | deepseek-r1:32b | command-r:35b | safe - the auditor band is still open at 80GB, see below |

On a 20GB card `evidence-review` falls to `aya-expanse:8b`, because `command-r:35b`
is 18.7GB of weights and will not fit under the 0.90 headroom rule at 20GB. That
is a steep capability drop and it is accepted rather than smoothed over: a small
distinct model beats a large identical one.

**So: buy 16GB or 24GB, and do not "upgrade" past 24GB to 48GB.** A used A6000
48GB is a plausible purchase for this project and it is one of the worst sizes
you could choose - it is a straight upgrade on paper and it silently turns the
auditor into a second copy of the CTO. A 3090, a 3090 Ti, a 4090, an A5000 and
an RX 7900 XT are all in the safe band.

**How the low band was fixed, and why it went in `reasoning` and not the
auditor.** The fix is three second-family candidates - `phi4:14b` (10GB),
`gemma3:12b` (9GB), `llama3.1:8b` (6GB) - added to the **`reasoning`** ladder.
The auditor role is deliberately Qwen-only, so on a small card both roles
collapsed onto the same Qwen tag. Putting the new entries on the *auditor*
would have worked and been wrong, for a reason worth keeping: the resolver
takes the **largest** candidate that fits, so an auditor entry big enough to win
on a 16GB card (>10GB) would also win on a 20GB and a 24GB card, dragging the
validated design target sideways with it. An entry on `reasoning` of 10GB or
less cannot disturb 20GB+, because `gpt-oss:20b` (14GB) still outranks it there.
So the cheap cards got fixed and 20GB/24GB resolution is byte-identical to
before.

**Declaration order is load-bearing, and that is a trap.** Where two candidates
tie on `vram_gb`, `resolve_models.py` sorts on `vram_gb` alone and Python's sort
is stable, so **the entry written first wins**. `phi4:14b` precedes
`qwen3:14b` so the CTO leaves the auditor's weights at 16GB, and `llama3.1:8b`
precedes `qwen3:8b` for the same reason at 8GB. Reversing either pair re-creates
the collision silently, and nothing in the tree would notice. Pinned by three
assertions in `test_independence_survives_every_hardware_tier`.

**What is still red, and why it cannot be fixed by adding a candidate.** As of
2026-09-26 `./bootstrap.sh check` is **red** on exactly one thing: the 28-48GB
band, 1 error, with 607 cases and 359 assertions otherwise clean. The owner's
earlier choice was to leave it red and revisit when the GPU arrives rather than
scope the guarantee to a card band; that decision covered the low band too, and
the low band has now been fixed on the owner's instruction, which supersedes it
for 8-16GB only.

The 28-48GB band is genuinely closed by arithmetic rather than by effort. A
candidate that outranks `qwen3:32b` (23GB) on a 28GB card must be over 23GB,
while a 24GB card's eligibility ceiling is `24 * 0.90 * 0.92 = 19.9GB`. So
**every** candidate that wins at 28GB also wins at 24GB, and any fix moves the
design target. Closing it means choosing a different auditor for the 24GB card -
an owner decision about which is worth an owner decision, not a catalog edit.
The alternative, dropping `qwen3:32b` from the auditor, is worse: that band falls
to a much weaker `qwen3:14b` auditor, which is the CTO's own model on a 16GB card.

**So if you see one error, this is why, and it is not new.** Do not "fix" it by
downgrading the check to a warning - that is rule 7, editing the scoreboard. The
mitigation is that the redness is *dated and attributed*: if a second failure
appears, it is a new one. If the count ever moves off 1, stop and read.

**The honest limit that remains:** the tier check proves the *catalog* cannot
silently produce a collision; it cannot tell you the card you have arrived is
the card you meant. Verify on the real machine that `config/models.env` shows
`ADVERSARIAL_REVIEW_MODEL` and `REASONING_MODEL` as different tags.

This used to be worse. On a machine with no GPU the resolver falls back to a
nominal 8GB and every role collapsed onto `qwen3:8b`, so `AGENT_INDEPENDENT_OF`
was a **no-op on this box** - the constraint was declared, checked, and enforced
against nothing. That is no longer true: because `llama3.1:8b` precedes
`qwen3:8b` in the `reasoning` ladder, the 8GB fallback now yields
`llama3.1:8b` against the auditor's `qwen3:8b`, and the independence holds even
in the fallback. That is a side effect of the ordering rule rather than the goal
of it, but it means the guarantee is finally observable on a GPU-less machine
instead of merely asserted.

22. **`AGENT_THINK` is a wish; the resolved model decides whether it is
    possible.** Ollama 0.33.3 answers a `think:true` request sent to a model with
    no reasoning channel with a **hard error**, not a shrug. Verified on this box
    against a real non-thinking model:

        think=true  -> ERROR: "qwen2.5:0.5b" does not support thinking
        think=false -> ok

    And `lib/runtime.sh` (`_rt_ollama_json`) sends the flag unconditionally, so
    nothing in the request adapts. An agent declaring `AGENT_THINK="on"` whose
    role resolves to an instruct model therefore fails **every run**, with a
    runtime error rather than a bad score - which is the one failure the harness
    cannot misread as a weak model.

    **This was not hypothetical, and it was not caused by the low-VRAM fix - it
    was exposed by it.** Eight of the fifteen agents declared `on` while their
    role resolved to an instruct model on a small card: `reasoning` picks
    `llama3.1:8b` at 8GB, `gemma3:12b` at 12GB and `phi4:14b` at 14GB, and
    `coding` picks `qwen2.5-coder:7b`. The second-family candidates added to
    `reasoning` on 2026-09-26 to break the independence monoculture are exactly
    what put a non-thinking model in a thinking agent's hands at the tiers below
    16GB. The agents were fine on a 24GB card and would have failed on every
    smaller one.

    **Nothing caught it.** The tier check compares resolved models for
    *equality*, and a crash is not a collision. `check-agents.py` validated the
    role name, the model name and the file layout, and a request that the server
    refuses is none of those. This is the project's own lesson arriving from a
    new direction: a check that only tests what you thought of is not a check.

    **The fix is to stop treating it as a static setting**, because it is not
    one. Whether thinking is *possible* is a property of the candidate the
    resolver picked - the same kind of fact as the model's name - while whether
    an agent *wants* it is `AGENT_THINK`. So the catalog carries a `thinks` flag
    per candidate, the resolver publishes `<ROLE>_THINKS` into `models.env`, and
    `aiorg_effective_think` in `lib/common.sh` sends `think:on` only when the
    agent asked and the model can. `tools/test-agent.sh` and
    `tools/run-agent.sh` both use it, and the audit log records what was
    **actually sent** rather than what was requested - a log claiming `think=on`
    for a run that ran `think=off` is a lie about the one field you would use it
    to diagnose.

    **Setting the eight agents to `off` was the wrong fix and was rejected.** It
    would also have switched thinking off on a 24GB card, where `reasoning`
    resolves to `gpt-oss:20b` and does think - and 24GB is the design target.
    The capability has to follow the hardware, not the other way round.

    **The downgrade is one-directional on purpose.** An *unrecorded* capability
    is treated as "cannot think", because the two mistakes are not symmetric:
    `think:off` on a thinking model costs deliberation and the run still works,
    while `think:on` on an instruct model means the run never happens. So
    ambiguity resolves towards the side that still produces a result, and
    `tools/check-agents.py` names the unverified models rather than letting the
    cost be silent. `devstral:24b` - the 24GB design-target model for `coder` -
    is one of them, and is the reason that warning is worth reading.

## A checker that crashes is not a checker that failed

Found 2026-09-27, on the first run of the day. `check_independent_models` still
called `_independence_pairs` after a refactor had renamed the helper to
`_independence_claims`, so `check-agents.py` died with

    NameError: name '_independence_pairs' is not defined

partway through `main()`. **All 15 agents went unvalidated, and every other
signal in the tree read green.** The exit code was 1, which is the same 1 the
tree is *supposed* to return for the known model-independence error, and all 331
assertions in `test_retrieval.py` passed.

**The two failures are indistinguishable from the exit code alone.** A red build
for a documented reason and a build that validated nothing are both `1`. What
separated them was a traceback on stderr and the *absence* of the agent table on
stdout - and nothing was looking for either. This is the sixth variant of this
project's standing theme (the diagnostic is what breaks, on the machines most
likely to need it), and the first one where the broken thing was the checker
that every other check is measured against.

**Why no existing test saw it.** Two candidates, and both are structurally
incapable of seeing it:

- Every other test in `test_retrieval.py` imports `check-agents.py` and calls
  **one function**. A crash in a function no other test touches is invisible to
  all of them, and `check_independent_models` is called from `main()` alone.
- `test_check_runs_every_step_even_when_one_fails` is about this exact failure
  mode - `check` silently not running - and cannot see it either, because it
  deliberately stubs `check-agents.py` out with a one-line shell script. It
  proves the shell keeps going after a *failing* step. A crash inside the step
  is not a failing step.

**So the missing check was not a check, it was a precondition.** Every check
assumed the checker runs to completion. Nothing asserted it. The fix is
`test_check_agents_reaches_a_verdict`, which runs the real script over the real
tree and asks a question no other test asks: not *is the verdict right* but
*was there a verdict*. `Traceback` on stderr, or a missing agent table on
stdout, is the failure.

**Its own first version passed a script that had crashed**, for the reason rule
20 already documents: the injected `raise` was appended to the file, which put
it *after* the `if __name__ == "__main__":` guard, where `sys.exit(main())` had
already ended the process - so the injection never ran and the "has teeth"
assertion failed, correctly. The lesson is the one from the `nvidia-smi`
regression: an assertion that cannot fail is worse than no assertion, because it
is bought with the same confidence as a real one. The injection now goes before
the guard, and it must still be shown to catch a crash.

**`python3 -m py_compile` does not find this class of bug**, and neither does
reading the diff. A `NameError` is a runtime failure in a module that compiles
cleanly. An `ast` walk that collects every defined name and every loaded name
does find it, costs a dozen lines, and is the shape of check worth reaching for
when a rename touches more than one file.

## A case that can never pass, and the one that can never fail

Found 2026-09-27, writing the 18 `personal` cases. Rule 5 says never put both
directions in `must_contain`. It is correct and it does not tell you what the
opposite mistake costs, which took two drafts to find out.

**Draft one, inverted.** The forbidden phrases went into `must_contain` and the
`must_not` column was left empty:

    knows-simple-facts ::: What is the capital of France? ::: Paris, I should note

`tools/test-agent.sh` reads a comma as **all** of the items, so that is one
group: the reply must contain `Paris` *and* `I should note`. The case does not
merely fail to check the negative - it **requires** the lecture. It scored a
perfectly correct reply, `The capital of France is Paris.`, at **0/1**, and the
failure line pointed at `I should note` rather than at the case.

**Draft two, over-constrained.** Moving the negatives to `must_not` left a dead
group behind - `advice || rope || ankle, I should note` - and that group can
never be the one that passes, because `must_not` independently forbids the
phrase in it. Worse, when the case failed, `check_field`'s "closest group was
missing" reported the missing half of the *dead* group. The failure message
pointed at the least informative thing in the file.

**The part I got wrong while writing the fix, which is the part worth keeping.**
I asserted in the file's own header comment that draft two was a *rubber stamp* -
"passes on the positive word alone and never checks the negative". It is not.
`run_case` evaluates the two columns **independently**:

    check_field "$must" "$reply" 0    || case_ok=0
    check_field "$mustnot" "$reply" 1 || case_ok=0

so `must_not` is always enforced, and draft two was a weaker and more confusing
case rather than a dishonest one. The two failure modes are different in kind -
one inverts the measurement, the other just obscures it - and I had them merged
because the more dramatic story was easier to tell. A checker that cannot see a
dead group would not have caught my error here; the thing that caught it was
reading the harness instead of reasoning about it.

**The same trap, in the other column, and one no checker can see.** A comma is
a separator in `must_not` too, so a phrase written `I'm sorry, but` bans the
words `I'm sorry` **and `but`** - and the run duly reported
`should not contain: "but"` against a model that had done nothing wrong. The
same file banned `if` by writing `however, if`. Both are punctuation read as
delimiters.

Then a banned string of `I can` in `honest-about-no-network`, which is a
substring of `I can't` - so the case **rejected the correct answer it was
written to require**. This one is worth dwelling on: `_check_case_satisfiable`
is structurally incapable of seeing it, and so is any other static check, because
whether it fires depends on what the model *says*. It was found by reading a
failure, and only by reading a failure.

The audit is one grep and it found four of the four problems: **a banned string
that is a single common English word is either a split phrase or too broad.**

**Why nothing in the tree caught either draft.** `_check_case_satisfiable`
fails a case where a banned string is inside a required one and **every**
`must_contain` group is poisoned, and that is exactly right: one clean group is
a legitimate way for the case to pass. Draft one *is* caught by it, in the one
case that had no clean group. Draft two is not, and cannot be, because the case
is satisfiable. Satisfiability is a mechanical property; a dead group is a
legibility one, and no amount of grepping for it is worth a checker that fires
on healthy files - the lesson from `AGENT_INDEPENDENT_OF`'s eight false
positives. It is documented in the file header instead.

**The lesson that generalises.** The smoke test was run on a **copy** of the
tree, against a 0.6B model, on a box with no GPU, for plumbing. It found a
broken test file. A suite that is worthless because the *cases* are wrong is
worse than no suite, because a 0/1 on a correct reply is indistinguishable from
a bad prompt - and the version of this that ends on a GPU looks like a model
that cannot follow instructions, at real cost, to whoever is trying.

So: **run a new agent's cases once, on anything, and read a passing one before
trusting a failing one.** Then check the reply text, not the score.

## Two phantom models, found by checking the catalog against the registry

`config/models.json` had no check that its model tags exist, and three of its 32
entries did not. Verified 2026-09-26 with
`curl -o /dev/null -w '%{http_code}' https://registry.ollama.ai/v2/library/<repo>/manifests/<tag>`
- note the tag goes in the path, **not** after a colon, and a 404 on a tag you
are sure exists usually means you built the URL wrong rather than that the model
is missing. `qwen3:14b` 404s under the wrong form and 200s under the right one.

| Catalog entry | Verdict | Reality |
|---|---|---|
| `devstral-small` | **fixed** | Not a real tag. The library ships `devstral:24b` (14GB) plus `devstral:24b-small-2505-*` quant variants of the same digest. Renamed, `vram_gb` 16 kept. |
| `qwen3:72b` (reasoning, 44GB) | **closed 2026-09-27** | Did not exist - the qwen3 library tops out at `32b` then jumps to `235b` (142GB), and nothing valid fills the 44GB slot from that family. **Entry deleted**, so the 48-64GB band now falls back to `qwen3:32b`. The reasoning is under "The two remaining phantoms, and why one is a trap". |
| `qwen3-coder-next:80b` (coding, 54GB) | **closed 2026-09-27** | The **repo was real and the tag was invented** - the exact inverse of `qwen3:72b`. `qwen3-coder-next` ships exactly one tag, `latest`, at 51.7GB of weights. Replaced with it. |

The two remaining ones were both top-of-ladder slots that only a 48GB+ card would
select, so they never affected the 16-24GB design target - but `bootstrap.sh all`
on a 48-80GB card would have failed to pull them. **They stayed open for a day,
deliberately:** a phantom is unambiguously a bug, but what should *replace* a
44GB reasoning model is a capability decision with a large download attached, so
it was the owner's call rather than a quiet catalog edit. Closed on 2026-09-27.

## The two remaining phantoms, and why one replacement is a trap

Closed 2026-09-27. The catalog is now **39 tags, zero phantoms**, verified with
`./tools/check-models.sh --online`, and no band at or below 48GB moved.

**Measuring a real candidate's size has a trap in it.** Weights are not in the
manifest's `total_size` - that field does not exist. The number is
`config.size` plus every entry in `layers[].size`, which is the download size.
And a phantom does not 404 with "page not found" from this endpoint; it returns
`200` with `{"errors":[{"code":"MANIFEST_UNKNOWN"}]}`. A checker that looks for
404 will call every phantom real. Sizes measured that way, against the catalog's
convention (`vram_gb` = weights plus a realistic KV cache, ratios 1.01-1.13):

| Candidate | Weights | Smallest card it can *ever* be picked on |
|---|---|---|
| `qwen3-coder-next:latest` | 51.7GB | ~65GB |
| `gpt-oss:120b` | 65.4GB | ~86GB - **unreachable, and not a substitute** |
| `deepseek-r1:70b` | 42.5GB | ~56GB |
| `llama3.3:70b` | 42.5GB | ~56GB, no thinking channel |

The "ever" column is the part that decides it. A candidate is only selected when
`vram_gb / usable_vram <= 0.92`, so it needs usable VRAM of at least
`vram_gb / 0.92` before it is eligible **at all**. That is why `gpt-oss:120b` -
the substitute the earlier note suggested - cannot fill a 44GB slot: 65.4GB of
weights needs ~71GB usable, and an 80GB card offers about 66GB, so it is
*permanently* ineligible on any card this project would buy. A substitute that
cannot be selected is not a substitute.

**Coding: replaced, because the tag was the bug and not the repo.**
`qwen3-coder-next` is real; `:80b` was invented. It ships exactly one tag,
`latest`, at 51.7GB, and `:80b`, `:30b`, `:80b-a3b` and `:instruct` all 404. Two
caveats recorded in the entry itself: `:latest` is a **floating** tag, so this
verification goes stale if the publisher ever repoints it, and `thinks` is left
**unrecorded** rather than guessed - unrecorded is treated as cannot-think, which
is the safe direction, and `tools/check-models.sh` can confirm it on a machine
that has the weights. It cannot be selected below ~65GB usable, so it changes
nothing at or below 48GB.

**Reasoning: deleted, and the obvious replacement was a trap.** `deepseek-r1:70b`
is real, thinks, and lands almost exactly in the vacated 44GB slot - it looks
obviously right. But `adjudication`, the CEO's role, is *already DeepSeek*, and
on a 48-64GB card that would put `reasoning` on `deepseek-r1:70b` while
`adjudication` sits on `deepseek-r1:32b`. **The checker would pass it**, because
`check_independence_survives_resolution` compares resolved **tags** and those are
different tags. What it would actually produce is the CEO and the CTO running two
sizes of one model family - the monoculture `adjudication` exists to break, in
the one place nothing in the tree can see it.

So the entry was deleted and the band falls back to `qwen3:32b`. That is the safe
and merely-less-capable option, and it costs nothing real: the 48-64GB band is
the one `AGENTS.md` already tells the owner not to buy.

**The gap in the instrument is now closed, for families.** See
"`check-agents.py` compares tags, not families" below.

**What this leaves.** The 28-48GB auditor error is unchanged and is still the only
error - at 80GB `reasoning` now correctly resolves to `qwen3:32b` instead of a
model that could not be pulled, which leaves the auditor band open there rather
than fixing it.

**This is the failure mode the project is built against.** A tag that cannot be
pulled produces a model that is missing at run time, and a missing model is how
you get a score that means nothing. It is the catalog-dressed version of the fake
100% in `AGENT_LAST_SCORE` that the audit log exists to catch.
**There is still no automated check for this in `./bootstrap.sh check`**, because
the natural place to put it - `check-agents.py` - must run offline and on a
machine with no GPU, and every model-existence question needs the network.

**That tool now exists: `tools/check-models.sh`.** It is explicitly opt-in for
exactly that reason, and it answers both open questions in one pass, because
they are the same question asked at different moments - *can this tag be pulled,
and can it think?*

```bash
tools/check-models.sh            # thinking capability of models already pulled
tools/check-models.sh --online   # + verify every tag exists in the registry
```

Against the catalog as it stands it independently rediscovers exactly the two
open phantoms above and nothing else, which is the useful result: a checker that
found a third thing would not be trusted.

**On capability, the only trustworthy source is the model server itself.**
`/api/show` returns a `capabilities` array containing `"thinking"` or not. Two
things that look like sources and are not:

- **The registry manifests carry no template field at all.** Scanning them for
  `enable_thinking` reports "no thinking" for `deepseek-r1:14b` and
  `qwen3:14b`, which have been machine-verified to think. A manifest scan is not
  a weaker signal here, it is an inverted one.
- **The ollama.com tags page does not show it per tag.** Grepping it for
  "thinking" hits on whichever tags happen to mention it anywhere on the page,
  which is not the same question.

Both were tried before finding the real answer, which is the usual way this
project finds things.


## `check-agents.py` compares tags, not families

The last paragraph above used to end by naming a gap in the checker rather than
fixing it. It is fixed, and the reason it is a separate finding is that the gap
was found by nearly walking into it.

`check_independence_survives_resolution` resolves each declared pair at every
hardware tier and compares the resolved **tags**. That is exactly right for the
fault it was written to catch - two roles converging on literally the same
weights - and structurally blind to a related one: `deepseek-r1:70b` and
`deepseek-r1:32b` are different strings and one training recipe. The CEO exists
to arbitrate the CTO, and one family arguing with itself produces correlated
errors, which read as agreement.

**This was not a hypothetical, it was a catalog edit I made and reverted.** With
`qwen3:72b` deleted, the 44GB slot in `reasoning` was empty, and
`deepseek-r1:70b` fitted it exactly - real, thinking, 42.5GB. I built the variant
and ran the checker before thinking it through, and the checker passed it. Only
the family question, asked afterwards, killed it.

**The fix is one comparison in the walk that already exists.** A model's family
is the part of the tag before the first colon, so the family walk is the *same*
loop as the tag walk with a second condition - deliberately not a second loop,
because two walks over the same tiers is two things that can disagree, and that
is the sixth repeat of this project's most reliable bug shape. The `continue`
after a tag collision is load-bearing: reporting it again as a family overlap
would be two findings for one fault.

**It is a WARNING, and that is the interesting design decision.** A shared repo
is evidence, not proof. A 7B and a 70B of one family are not the same model, and
two unrelated models trained on one corpus are not independent either, so neither
direction is provable from the tag. Making it an error would overclaim what the
check knows, and overclaiming a check is the habit this project keeps having to
correct. Making it a warning is also what the existing precedent says: a score
that is real but meaningless is a warning, not an error.

**Proven in both directions, because "it printed nothing" is not evidence.**

- Silenced on the real catalog: 0 family warnings, so it adds no noise to a
  healthy tree - the eight-false-positive lesson.
- Fires on the exact edit that nearly shipped, naming the pair, both tags, the
  family and the two affected cards: `adjudication`/`reasoning` on
  `deepseek-r1:32b` + `deepseek-r1:70b` at 46.7GB and 58.7GB usable.
- **Mutation-tested, twice.** Making `_model_family` return the whole tag, and
  making it return `""` unconditionally, each turns the suite red. A check that
  cannot fail is bought with the same confidence as one that can - the
  `nvidia-smi` regression, where the original assertion passed against code
  that died before reaching the check.
- 11 new assertions, 335 -> 346.

**What it still cannot do.** Family is a proxy, and a coarse one. It knows
nothing about training data, and it treats a repo as a recipe, which is right
often enough to be useful and wrong often enough to stay a warning. The tag
check remains the only thing in the tree that can say two agents run *identical*
weights, and that is the stronger guarantee; this one exists to make the weaker
claim visible instead of silent.

## The research department

Five agents, and a retrieval pipeline that is deliberately **not** an agent.
`research-officer` commissions and judges; `tech-`, `design-`, `education-` and
`web-researcher` do the reading. All five declare `AGENT_RETRIEVAL="on"`.

**Why the crawler is not an agent.** The rules a crawler must obey - robots.txt,
a per-host delay, no private addresses, no cookies - are the kind an agent cannot
be trusted with, for the same reason the risk tiers live in `lib/common.sh`
rather than in a SOUL.md. "Only fetch what robots.txt allows" written in a prompt
is a request. Written in `tools/ingest.py` it is a check that runs before a
socket opens. So the agents never fetch: they are given a citation-numbered
evidence block and they reason about it. A human (or the officer) runs
`tools/ingest.py`.

    tools/ingest.py --url https://example.com/docs/ --depth 1 --limit 25
    tools/search.py  --evidence --k 5 "<query>"
    tools/run-agent.sh --queries "<q>" -- <agent> "<question>"

**Provenance is carried in the data, not reconstructed by the model.** Every
chunk stores its URL, page title and fetch time, so a citation can be checked
without trusting the model to have remembered where something came from. Then
`tools/check-citations.py` runs on every retrieval-backed reply and fails the
run if the agent cites a source number that was not supplied, or a URL that is
not in the evidence. It cannot tell whether source 1 *supports* a claim - that
is judgement, and judgement is what the researcher and the reader are for. It
proves the citation points at something real, which is the part a model gets
wrong silently.

**A reply that cites nothing is a note, not a failure.** The first version
filed "cited nothing" as a problem, which made the most honest possible answer -
"the sources do not cover this" - the one reply that got marked wrong. That was
backwards. Absence of a citation is not fabrication.

**`AGENT_RETRIEVAL` is a declaration, not a switch.** `tools/test-agent.sh` still
runs the closed-book suite and labels the score of an `on` agent, so a
closed-book pass can never be mistaken for a retrieval-backed one.

**Retrieval is lexical (SQLite FTS5 / BM25), and that is a real limitation.** A
query using different words from the source will miss, and "not in the index"
means not found, never does-not-exist - `tools/search.py` says so in those words
on a miss. No embedding model is installed, so there is no semantic retrieval
yet. This is a documented limitation, not a reason to have no retrieval today.

**Nothing here is fine-tuning.** "Learning" for this department means indexing
and retrieval. Weights are untouched; the loop is still prompt, test, fix.

### Four bugs this pipeline had, all found by running it

Each of these passed a syntax check and a read-through first. They were found by
pointing the thing at a real website.

1. **A 153KB page indexed as a single chunk.** The chunker split on blank lines,
   which real pages do not contain - `extract()` emits single newlines, so the
   paragraph splitter found one enormous "paragraph" and passed it straight
   through. Nothing crashed. Retrieval was simply worse: one giant FTS5 row,
   truncated to 900 characters on the way out, one useless citable "source". The
   200-chunk version of that page is what it should always have been. The fix is
   a hard invariant - **no chunk may exceed `CHUNK_CHARS`, whatever the input** -
   with line, then sentence, then a raw slice as fallbacks.
2. **An unreachable robots.txt was treated as permission.** The code comment
   claimed RFC 9309 says an unavailable robots.txt means allow-all. The RFC says
   the opposite, and the index built during testing says so in its own words:
   unreachable (5xx) is "MUST assume complete disallow"; unavailable (4xx) is
   "MAY access any resources"; a 404 is no opinion at all. Three different
   cases, and the code had them as one permissive case. The comment was the only
   evidence for the behaviour and it was wrong.
3. **Redirects were followed without re-checking.** `urllib`'s redirect handler
   was live, so a seed on an allowed path could redirect into a disallowed path,
   onto a host whose robots.txt says no, or at a private address, and every
   check applied to the URL asked for rather than the one reached. Replaced with
   a `NoRedirect` handler and an explicit loop that re-validates each hop.
4. **`AGENT_TIMEOUT_MIN` was passed as seconds.** The key is in minutes, says so
   in its name, and every generated `agent.conf` carries 30. `tools/test-agent.sh`
   multiplied by 60; `tools/run-agent.sh` did not. So every open-book run died at
   30 seconds with `rc=28` and read like a broken model. It is the same class of
   bug as the three different conventions for naming the model server, and the
   same lesson: two callers of one interface, one of them wrong, nothing in the
   tree able to see it. `tests/test_retrieval.py` now asserts both callers agree.

Also fixed, smaller: robots.txt was fetched twice (once through the polite
opener, once by `RobotFileParser.read()` outside the rate limit); `Crawl-delay`
from robots.txt is now honoured; temp files were fixed names under `state/`, so
two concurrent runs would check each other's citations against each other's
evidence - a wrong PASS - and a crashed run left source text sitting in
`state/research/`; and the open-book path put the SOUL in the *user* message
alongside the untrusted page text, on the reasoning that the injection warning
"has to be somewhere the page cannot reach". That is exactly backwards. The
system slot is the one place page text cannot reach, so the SOUL and the warning
both belong there.

`tests/test_retrieval.py` (359 assertions) starts its own loopback server and
asserts every one of those refusals, and runs as part of `./bootstrap.sh check`.

### The gap the research department did not close

`web-researcher` would obviously benefit from running the guarded ingester
itself, and there is still no rung in the ladder for "may execute" without also
granting `config` and `deploy`. So ingestion stays with a human. This is the
same policy decision recorded under the CTO section, not a new one - and it is
worth resolving before an agent needs it, not after.

## The next move

The runtime layer and the audit log are done, `cto` is built, and so is the
research department. All three were worth doing in that order: an org chart with
nothing to coordinate through and no record of what happened is a prompt
roleplaying a manager, and a coordinator with nothing to coordinate is the same
trick one level up.

The research department is the first part of the tree that reaches outside the
machine, and building it turned up four real bugs that every other check had
passed. That is the argument for `tests/test_retrieval.py` existing rather than
a pile of manual verification: nothing in the tree could see them.

`ceo` was built last, and that ordering was the point: it is the root of the
chart, and until `cto` and `research-officer` existed it had nothing to
arbitrate. A coordinator above empty departments is the same trick one level
up from a manager with nothing to manage. Both of those now exist, the org chart
is closed, and the CEO is the one agent read-only with a longer fuse than the
CTO - see the table above for what it is for.

**One structural decision worth recording: the CTO is read-only.** The obvious
design is to let the officer who assigns permissions also grant them. That gives
an agent which can edit `agent.conf` the ability to raise its own ceiling, and
every other limit in the tree then rests on the judgement of the agent best
placed to remove them. So the CTO decides and a human applies - which is the
instruction `security-engineer`'s SOUL.md already carried ("a finding for the
CTO, not a change to make quietly"), made mechanical.

**Per-action risk tiers - done, with one gap left in the ladder.**
`AGENT_SAFETY` is the ceiling; `AGENT_ACTIONS` may only narrow it, and an action
above the ceiling is a hard error in `check-agents.py` that also refuses the run
in `test-agent.sh`. The effective set is printed at run time and recorded in
`state/audit.log` next to the score, because a score is only interpretable next
to what the agent was allowed to do. `coder` is the worked example: `standard`
would let it edit another agent's `SOUL.md`, so it takes `read,write` and leaves
`write_other` to the teacher.

`tools/sync-rules.sh` exists because those rules are implemented twice - once in
bash for the harness, once in python for the checker - and nothing else would
notice if the two drifted. It runs as part of `./bootstrap.sh check`.

**What it does not do: sandbox anything.** An agent that can `execute` can still
run the wrong command. This makes the permission set explicit, checkable and
recorded; it does not enforce it at the OS level, and `AGENT_SAFETY` was never
more than a recorded claim. Keep that straight.

**The gap in the ladder.** `execute` sits above `standard`, so there is no rung
between "may write its own files" and "may reconfigure the system". A coder that
can run its own tests would need `full`, which also grants `config` and
`deploy`. This is a policy decision, not an oversight to patch quietly - either
a fourth safety level, or an explicitly justified single widening.

**Reporting lines are a design choice, not a default, and they are now
enforced.** Every agent reporting to one officer is tidy and wrong: the officer
then has no stake in the departments it does not understand, and the engineers
it does judge are also its friends. `ceo` is the root, reporting to nobody, which
is the only agent allowed an empty `AGENT_REPORTS_TO`. `cto` heads the technical
department (network, storage, programming, IT, and security since 2026-09-26 -
security audits the permissions the technical department hands out, so it sits
under the officer that recommends them, and the CTO can neither edit its SOUL.md
nor its test cases). `teacher` and `languages` sit under `ceo`, which is correct
rather than interim: teaching and translation are not technical departments.

That paragraph used to be the whole of it - a convention nothing checked, which
is how five agents sat under a `ceo` that did not exist while
`./bootstrap.sh check` stayed green. `check_reporting_graph()` in
`tools/check-agents.py` now fails the tree on a parent that does not exist, on
a reporting cycle, on more than one agent at the top, and on any chain that does
not reach the root. It is skipped in single-agent mode, which cannot see its
siblings. It was tested against its own four failure modes before being believed
- the habit this project keeps having to relearn.

Build the remaining agents, same pattern as the sixteen that exist:
`new-agent.sh` -> write `SOUL.md` -> write skills -> write cases -> `check` -
and then **run the cases once against anything and read a passing one before
trusting a failing one.** A new agent's cases are wrong at least as often as
its SOUL is, and a 0/1 on a correct reply is not a model problem. See "A case
that can never pass, and the one that can never fail".

`scripts/10-ollama.sh`, `20-models.sh`, `30-openwebui.sh` and `40-verify.sh` have
now been read line by line and exercised against fake `ollama` / `curl` / `docker`
binaries, which is how the bugs below were found. They are still untested against
a real model server, so `./bootstrap.sh all && ./bootstrap.sh verify` remains the
first genuinely unproven path - and it gates every real score.

## The two blueprints in ~/Documents

`AI ORGANISATION MASTER BLUEPRINT-CGPT FInal.docx` and `Free local AI agent
system Claude first draft.docx` were read and compared on 2026-09-26, then
explicitly set aside. They are architecture documents, not specs for this repo:
a Paperclip control plane, 40+ specialist agents, a 40-agent roster that does
not match the fifteen here, and model names older than the ones in
`config/models.json`. Do not treat them as a checklist. The runtime-layer rule
above was adopted because it is right, not because a document said so.

## Notes on the user

Beginner. Explain plainly, give exact commands, and make scripts idempotent so
they can be re-run safely. Budget under $600, building a home lab from
secondhand parts. Treat "is this safe" and "why" as real questions deserving
real answers, not obstacles to route around.
