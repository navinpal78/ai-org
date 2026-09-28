# Pending work — pick anything, or none

Written at the end of the audit session, updated 2026-09-28. Everything below is
saved and committed; nothing here is half-done. Repo is at `~/Work/ai-org`, 12
commits, clean tree, no remote.

## What "healthy" looks like right now

```
472 checks passed
1 problem   <- deliberate, documented, known: the security-engineer/cto
               auditor monoculture at 25.0GB usable
```

The single error is not a regression. It is a design tension recorded in
`AGENTS.md` under "What is still red". **If the error count is ever anything
other than 1, that is a new problem** — investigate before touching anything else.

## Read this first

Two files carry the full history, both now under Git:

- `docs/SESSION-HANDOFF.md` — detailed audit history, the mutation method, the
  two writer/reader fixtures I got wrong and why.
- `docs/SESSION-NOTES.md` — work done / pending, decisions, verification
  commands.

They joined the repo on 2026-09-28, along with this file and
`docs/CONTINUE-TOMORROW.md`. Item 8 is done. The older copies in `~/Work` are
superseded; the `docs/` versions are canonical.

---

## Tier 1 — owner decisions. I deliberately did not guess at these.

These change behaviour or policy, not just code. They are yours.

**1. `artist` and `director` are still unbuilt.**
They are listed in the README plan but do not exist on disk. The open question is
what they *are*: a ComfyUI adapter (they call an image generator), or
human-operated specs for an artist to follow. Different projects. The runtime
registry has a comment-only adapter check now, but it cannot answer this for me.

**2. The 28–48GB auditor band.**
`security-engineer` declares `AGENT_INDEPENDENT_OF='cto'`. Both resolve to
`qwen3:32b` at 25.0GB usable, so the auditor and its audited party share weights.
Two honest resolutions:
  - accept a *different* auditor for the 24–28GB tier, or
  - leave it red and document the monoculture as a known cost.
The checker is right. The policy question is whether to keep it red.

**3. Do you want a 1B model with a thinking budget, or the 20B?**
`devstral:24b` and `gpt-oss:20b` are both flagged "thinking unconfirmed" — they
emit `<think>` text, which would corrupt exact-match scoring. Confirming costs
~30GB of pulls. `qwen3-coder-next:latest` is a floating tag with thinking
unrecorded, so a pull could change its behaviour under you.

**4. Git remote.**
12 commits, all local, one disk. No push has ever happened. **Open.**

---

## Tier 2 — real verification, needs hardware/time

**5. Re-run the 12 smoke-tested agents on a working GPU.**
Last real run: 12/18, with the 6 failures understood (2 unbuilt agents, 2
oversized, 1 rank error, 1 disabled). All scores currently in `agent.conf` are
from before that run. No CPU/0.6B quality judgments — those are not evidence and
I did not make any.

**6. Confirm `think` mode works before trusting any score from those models.**
If `think=high` leaks `<think>` into a reply, the score is garbage. This is why
`devstral`/`gpt-oss` are unconfirmed rather than marked working.

---

## Tier 3 — optional hardening. Nothing is currently red because of these.

**7. Mutation-audit `tools/check-models.sh`.**
The one remaining instrument never audited. Only 5 finding sites (lines 102, 113,
115, 139, 140) against 69 in `check-agents.py`, and 3 need a live Ollama or a
real 404 to reach. It is the instrument behind the "0 phantoms" claim and the one
that caught `qwen3:72b` and `qwen3-coder-next:80b` — nothing proves it would
catch a third. Method is reusable:
```
python3 tools/mutation-audit.py     # repoint SRC + rep.<kind> matching
```
Worth it only if you want the phantom-detection claim hardened. A tenth the size
of what is already audited.

**8. ~~Put the handoff files under Git.~~ — DONE, 2026-09-28.**
`docs/SESSION-HANDOFF.md` was already tracked. `docs/SESSION-NOTES.md`,
`docs/CONTINUE-TOMORROW.md` and `docs/PENDING-WORK.md` now are too. The copies
left in `~/Work` are superseded and can be deleted; `docs/` is canonical. The
password in item 9 was verified absent from all four before they were staged.

**9. Rotate the sudo password.**
It was pasted into a `git config --global user.email` command at some point and
is in this session's history. Not a repo problem, but a real one.

---

## Explicitly not worth doing

- **Do not re-run the check-agents mutation audit.** It is finished, committed,
  and deterministic: 69 sites, 68 owned by an assertion, 1 proved dead
  (`check_cases` cannot emit "no prompt column" — asserted as an invariant).
  Re-running gives the same number and takes ~5 minutes.
- **Do not "fix" the 1 error** without answering item 2 first. It is load-bearing
  documentation of a real tension, not an oversight.
- **Do not trust stale counts in older sections of the handoff.** 415 and 460 are
  both historical; the live suite is 472.

## Two rules learned the hard way

- **The instrument is usually what is wrong.** Three times this session the code
  was correct and my test was not (twice fixture paths, once a claim about a
  dead branch). Run the real tool in isolation before believing a red.
- **Coverage claims are only worth what their weakest link is.** "All 13 finding
  functions are tested" was false — 31 of 69 call sites had no assertion. Mute
  each call individually and count. Never match by function name or line number.
