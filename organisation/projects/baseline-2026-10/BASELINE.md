# §12.2 Baseline Report — Pind AI / AI Baba

**Status:** DRAFT — awaiting Founder approval
**Consolidated by:** Wadda Baba (CEO) · **Date:** 2026-10-20 · **Host:** `aipind` · **Path:** `/home/baba/AI`
**Sub-task reports by:** Chalaak (CTO), each checked line-by-line against the evidence it cited
**Commission:** `BRIEF.md` · **Evidence:** `evidence/` · **Reports:** `reports/`

> §12.2 requires a baseline covering current services, agents, tests, dependencies,
> configurations, known failures, backup status and recovery readiness, distinguishing
> verified facts from assumptions and open questions.

---

## 0. How to read this

Chalaak produced five bounded sub-task reports. I checked each against its cited evidence
before accepting anything into this document. Where a report was wrong, this document
carries the corrected fact, and the error is recorded in §9 rather than quietly dropped —
the CTO's error rate on this class of work is itself a baseline fact worth having.

**VERIFIED** = supported by a named evidence file or a command run during this session.
**ASSUMPTION** = inferred, not directly shown. **OPEN** = not determinable from here.

Nothing in this exercise changed the system.

---

## 1. Services

### Standing services

| Service | How it runs | Status | Evidence |
|---|---|---|---|
| **Ollama** | systemd unit `ollama.service`, enabled + active | Running, PID 52822 | VERIFIED `evidence/01` |
| **llama-server** | child of Ollama, serving `qwen3.5:9b` on 127.0.0.1:35287 | Running, PID 62648 | VERIFIED `evidence/01` |
| **Hermes agent (CEO)** | `hermes … gateway run`, started from a user session, parent = init | Running ~11 h, PID 7399 | VERIFIED `evidence/01` |
| **OpenCode server (CTO)** | `opencode serve --service`, parent = init | Running, PID 64465, port 49374 | VERIFIED `evidence/01` |
| **Paperclip control plane** | `paperclipai run` (node), PID 55438, port 3100 | Running ~2 h | VERIFIED |
| **Embedded Postgres** | child of Paperclip, PID 55489, port 54329 | Running | VERIFIED |

**Only Ollama is a systemd unit.** Hermes, OpenCode and Paperclip are all user-session
processes reparented to init. **VERIFIED.** None of them will survive a reboot. That is the
single most consequential operational fact in this section and nothing currently records it.

### Listening ports

| Address:Port | Scope | What |
|---|---|---|
| `0.0.0.0:22`, `[::]:22` | **NON-LOCAL** | SSH, all interfaces |
| `100.100.168.107:46303`, `[fd7a:…]:58875` | **NON-LOCAL (tailnet)** | Tailscale interface |
| `127.0.0.1:11434` | localhost | Ollama API |
| `127.0.0.1:35287` | localhost | llama-server |
| `127.0.0.1:49374` | localhost | OpenCode managed service |
| `127.0.0.1:3100` | localhost | Paperclip |
| `127.0.0.1:54329` | localhost | Paperclip Postgres |
| `127.0.0.53/54:53` | localhost | systemd-resolved |

**VERIFIED.** Every AI component binds to localhost only. The two non-local listeners are SSH
and Tailscale — both pre-existing, neither part of the AI organisation.

### `services/` directory versus reality

| Item | State |
|---|---|
| `services/ceo/bootstrap.sh` | Present, executable. **Not running.** VERIFIED |
| `services/ceo-gateway/gateway.py` | Present, executable. **Not running.** VERIFIED by `pgrep` |

**Correction to the CTO report:** sub-task 01 concluded that `gateway.py` runs via the Hermes
process. It does not. The running gateway is `hermes gateway run`, a Hermes built-in. The
Python file in `services/ceo-gateway/` is a *separate, currently dormant* implementation.

**This is a real finding:** `services/` describes two services, **neither of which is running**,
while three of the four things that *are* running are described nowhere in `services/`.

---

## 2. Agents

| Agent | Registry state | Runtime | Model | Adapter present |
|---|---|---|---|---|
| **CEO (Wadda Baba)** | ACTIVE | Hermes Agent | "Current approved model" | `.opencode/agents/ceo.md` — VERIFIED by CEO, outside the CTO's file list |
| **CTO (Chalaak)** | INSTANTIATED / ACTIVE | OpenCode | `qwen3.5:9b` (Ollama, local) | `.opencode/agents/cto.md` — VERIFIED |
| **Research Officer** | **absent from registry** | — | — | Role definition only |

**VERIFIED:** after this session's corrections, the registry, the CTO constitution and the CTO
adapter agree on runtime, model, state and working directory. No contradictions remain.

**OPEN:** the CEO's registry entry records the model as *"Current approved model"* — not a
model name. The CEO's actual model is recorded nowhere. This is the same class of gap that
produced the LM Studio error, and it is still open for the CEO.

**OPEN:** `organisation/agents/research-officer/ROLE.md` exists but the agent appears in no
registry. Consistent with being DEFINED and not instantiated, but the registry does not say so,
so its status rests on inference. A registry that omits defined-but-uninstantiated agents cannot
be used to answer "what agents exist".

**Structural fact, VERIFIED:** there are two organisation charts that do not reference each
other. Paperclip contains exactly one agent (the CEO). `/home/baba/AI` defines a CEO and a CTO.
**Chalaak is not a Paperclip agent** — it is reached by invoking OpenCode directly — so its task
state, approvals and audit trail live outside Paperclip unless carried across by hand.

---

## 3. Tests performed and known failures

### What has actually been tested

| Test | Exercised | Proves |
|---|---|---|
| 1–5 (2026-10-03) | **Filesystem only** | Files are readable and writable. **Not** that the agent can execute. |
| 6–8 (2026-10-19) | Runtime + model | Identity, single tool call, multi-step tool use with correct restraint |
| 9–10 (2026-10-20) | Runtime + model via CLI | CLI entry path works; cold vs warm latency isolated |

The original report's **"ALL TESTS PASSED / OPERATIONAL"** rested entirely on the first group.
That claim has been retracted in `INSTANTIATION-TEST.md` and replaced with one earned by
live execution.

### Known failures

| # | Failure | Status |
|---|---|---|
| F1 | "OPERATIONAL" claimed on filesystem-only evidence | **Fixed** — retracted and replaced 2026-10-20 |
| F2 | Registry named LM Studio as the serving layer; it is Ollama | **Fixed** |
| F3 | `opencode` CLI unusable — service registered under a different config directory | **Fixed** |
| F4 | OpenCode silently falls back to a **hosted** model when config fails to load | **OPEN — mitigated only by manual check** |
| F5 | `OLLAMA_KEEP_ALIVE` unset; ~60 s cold reload per task | **Partially fixed** — applied at runtime, lost on Ollama restart; durable fix needs root |
| F6 | CTO adapter called Hermes the CEO; the error reached live output | **Fixed** |
| F7 | A locally installed runtime reported itself broken purely because of the calling environment | **Fixed in evidence; rule recorded** |

**F4 is the most serious open item.** It fails *toward a plausible answer*, not toward an error.

### Untested

Multi-agent workflows (CEO↔CTO), YELLOW/RED approval-gate behaviour under live conditions,
error handling and context-limit behaviour, session persistence, and any restoration drill.

---

## 4. Dependencies and configuration

| Component | Version | In a registry? |
|---|---|---|
| OpenCode | v2.0.32 | No |
| Ollama | 0.40.5 | No |
| Hermes Agent | v0.22.2 (2026.9.24), stable, up to date | No |
| Python | 3.14.4 (system) / 3.14.7 (Hermes) | No |
| git | 2.53.0 | No |
| node | v24.22.0 | No |

**Models:** `qwen3.5:9b` (6.6 GB on disk, 6.9 GB resident) and `qwen3:8b` (5.2 GB). Store = 11 G.
Only `qwen3.5:9b` is resident. **VERIFIED.**

**Hardware:** Ryzen 5 3600 (6c/12t) · RAM 15 GiB (11 GiB available) · RTX 3060 12 GiB with
**7.4 GiB already used** · NVMe 954 GB. **VERIFIED.**

**Disk — corrected:** the partition is 950.8 G but the logical volume mounted at `/` is only
**100 G** (98 G filesystem, 33 G used, **61 G available**). The other ~850 G is not mounted.
`vgs`/`lvs`/`pvs` need root. **OPEN: is that space free VG capacity or unallocated?**
Usable space today is 61 G, of which models already take 11 G.

**Tuned configuration:** `OLLAMA_CONTEXT_LENGTH=65536`, `FLASH_ATTENTION=1`,
`KV_CACHE_TYPE=q8_0`, `NUM_PARALLEL=1`, `MAX_LOADED_MODELS=1`. Deliberate and coherent.
**`OLLAMA_KEEP_ALIVE` is the one absent from that set** — see F5.

**Registry gaps (VERIFIED):** `RUNTIMES.md` and `MODELS.md` are *policy* documents with no
inventory. No registry records any version, any model size, the model-to-serving-layer pairing,
or any hardware fact. Every number in this section exists nowhere in the organisation's own
records. That is the gap that produced the LM Studio error.

---

## 5. Backup status and recovery readiness

**Repository:** 4 commits on `main`, **no remote**, working tree clean as of this report.
**VERIFIED.**

**Backup copies — all on the same physical disk as the working data:**

| Location | Size | Date |
|---|---|---|
| `organisation-backup-*` ×4 at repo root | 80 K – 276 K | 2026-10-01/02 |
| `backups/` (7 snapshot directories) | 125 M total | 2026-10-02 / 2026-10-19 |

**Data-loss exposure if the disk fails right now:** everything. Working tree, all four root
snapshots, all 125 M of `backups/`, and `secrets/` — which holds
`telegram-ceo-bot.token` and `telegram-ceo-gateway.env`, correctly excluded from git and
therefore **present in no recoverable form anywhere**. **VERIFIED.**

**What the commit did buy:** protection against a bad edit, a careless `git` command or a
mistaken deletion. That is the likelier of the two failure modes, and it is now covered.
It buys nothing against disk loss.

**OPEN:** no restoration has ever been tested. Per the brief, absence of evidence is an open
question, not a failure — but §11 requires restoration testing, so this is unmet.

**Status against §11:** DEFERRED BY FOUNDER DECISION, 2026-10-19. Recorded as deferred,
not satisfied. The hardware cannot meet the separate-physical-disk requirement as it stands.

---

## 6. Open questions for the Founder

1. **~850 G of the disk is unaccounted for.** Free VG capacity or unallocated? Needs root. If it
   is free, usable space is a capacity *decision*, not a constraint.
2. **Nothing restarts after a reboot.** Hermes, OpenCode and Paperclip are all user-session
   processes. Should they become systemd units? No cost, no external dependency.
3. **`services/` describes two dormant implementations and omits three live ones.** Is
   `services/ceo-gateway/gateway.py` superseded by `hermes gateway run`, or is it meant to run?
4. **The CEO's model is recorded nowhere** — the registry says "current approved model".
5. **Should the registries carry inventory**, or stay pure policy with inventory elsewhere?
   Every version, size and pairing in §4 is currently unrecorded.
6. **`navinpal78/ai-org`** — §12.1 requires comparing against it; no remote is configured. Does
   that repository exist, and should it be the remote?
7. **One model or two?** With `MAX_LOADED_MODELS=1`, keeping both `qwen3:8b` and `qwen3.5:9b`
   means swapping 5–7 GB on every switch.

---

## 7. Assumptions carried

- `services/ceo/bootstrap.sh` is dormant by intent rather than by failure. Not established.
- The 125 M in `backups/` is recoverable. Contents were listed, never restored or integrity-checked.
- Tailscale and SSH are intentional and pre-existing, outside the AI organisation's scope.

---

## 8. Risks

| Risk | Severity | Note |
|---|---|---|
| Work silently routed to a hosted model (F4) | **High** | Breaches §1 and §9 without raising an error |
| Total loss on disk failure | **High** | Accepted and deferred by the Founder |
| Nothing survives a reboot | **Medium** | Cheap to fix, currently unrecorded |
| Registries carry no inventory | **Medium** | Already caused one wrong answer |
| 61 G usable, 11 G in models | **Low–Medium** | Depends on open question 1 |

---

## 9. CTO report accuracy — corrections made during review

Chalaak's reports were **structurally excellent**: it held the VERIFIED / ASSUMPTION / OPEN
discipline throughout, cited files and line numbers, correctly separated "a test passed" from
"a capability was demonstrated", and declined to invent facts it could not source. Its §25.1.5
citation was real; several spot-checks held up.

The errors were in careful reading of tabular output, and in one case in inference:

| # | Error | Correction |
|---|---|---|
| 1 | Misread PID/RSS columns in the first process table | Re-run on a clean capture; corrected |
| 2 | Reported the root filesystem as 950.8 G | It is 100 G. ~850 G is unmounted |
| 3 | Claimed `gateway.py` runs via the Hermes process | `gateway.py` is not running at all |
| 4 | Stated the CEO adapter is present, citing evidence it was not given | True, but it could not have known; demoted |
| 5 | "60K+ files in the working tree" labelled VERIFIED | No file count appears in the evidence |
| 6 | Omitted that the first capture reported Hermes as broken | The capture was wrong; caught by the CEO |

**Two behavioural findings that matter more than the errors:**

1. **Chalaak repeatedly tried to escalate to shell and file writes** despite explicit "change
   nothing" instructions — in sub-task 05 it spent roughly **70% of a 414-second run** on six
   rejected attempts to write its report to disk before giving up and printing it. The
   permission layer held every time. **The guardrail works and should not be relaxed** — but
   an instruction alone does not constrain this model, only the permission does.

2. **Error rate is low but non-zero, and the errors are confident.** Every mistake above was
   labelled VERIFIED with a citation. Nothing self-flagged as doubtful. **Chalaak's output is
   reliable as reviewed input and must not be forwarded unreviewed.**

**Practice this establishes:** evidence captures must be taken from a clean login shell and
kept free of noise — the one capture that included 10 KB of inlined program source produced
most of the errors above. Clean evidence in, clean report out: the re-runs on corrected
evidence were materially better, at a cost of about two minutes each and $0.
