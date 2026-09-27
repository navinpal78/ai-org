# ai-org

A local, self-hosted AI agent organization. Fourteen agents on your own
hardware, on your own network, with no subscription and no account.

**Beginner? Read [`docs/00-START-HERE.md`](docs/00-START-HERE.md) first.** It
explains every decision in this repository, and it is written for someone who
does not yet know what VRAM is.

---

## The one idea

Your hardware decides which models you get, and the software reads that answer
at install time instead of you maintaining a list.

```bash
./bootstrap.sh detect    # measures VRAM, writes the answer to config/profile.env
./bootstrap.sh all       # installs everything that fits
```

Nothing in the scripts has a model size hardcoded in it. Upgrade the graphics
card, run `detect` again, and every agent moves to a bigger model with no
configuration changes. The whole point is in
[`tools/resolve_models.py`](tools/resolve_models.py) and
[`config/models.json`](config/models.json).

---

## Quick start

```bash
chmod +x bootstrap.sh scripts/*.sh tools/*.sh
./bootstrap.sh all
./bootstrap.sh verify     # must say "100% GPU"
```

| Command | Does |
|---|---|
| `./bootstrap.sh detect` | Measure hardware, resolve models for it |
| `./bootstrap.sh ollama` | Install and tune the model server (needs sudo) |
| `./bootstrap.sh models` | Download the models that fit |
| `./bootstrap.sh ui` | Browser interface via Docker |
| `./bootstrap.sh verify` | End-to-end test, including GPU usage |
| `./bootstrap.sh check` | Validate the agents/ tree. No GPU or model server needed |
| `./bootstrap.sh status` | What is installed and running |
| `./bootstrap.sh doctor` | Diagnose problems |

---

## Requirements

- Linux (tested on Arch-based, written to work on Ubuntu and Debian too)
- NVIDIA, AMD, Apple Silicon, or nothing at all - it detects and adapts
- 8GB RAM minimum; 16GB+ strongly preferred if you are running agents locally
- Docker, only if you want the web interface. Everything else works without it.

One used RTX A5000 24GB is the budget sweet spot: quiet, 230W, single-slot, and
enough VRAM for 30B-class models. See the hardware table in the start-here doc.

---

## Building an agent

```bash
./tools/new-agent.sh my-agent
$EDITOR agents/my-agent/SOUL.md
./tools/test-agent.sh my-agent
```

`SOUL.md` is the personality. `tests/cases.tsv` is the checklist. The loop
between them is the whole method:

```
write a failing test  ->  fix SOUL.md  ->  watch it pass  ->  check nothing broke
```

Run `./bootstrap.sh check` first. It validates every agent's config and test
file without needing a GPU or a running model, and it catches the mistakes that
make a score meaningless: two cases sharing a name, a case with no checks that
can never fail, a model role that resolves to nothing.

This is how you "train" an agent, and at local model sizes it beats
fine-tuning by a wide margin for a fraction of the effort. Fine-tuning has its
place - see [`finetune/README.md`](finetune/README.md) for the three cases
where it is the right call and the nine where it is not.

---

## The agents

| Role | Purpose |
|---|---|
| `network-engineer` | Network configuration and diagnostics |
| `storage-engineer` | Filesystems, backup, data integrity |
| `cto` | Technical decisions. Heads network, storage, coding and IT. Decides, never acts |
| `research-officer` | Commissions research and judges findings. Never gathers sources itself |
| `tech-researcher` | Technology feasibility for this hardware, and reading benchmarks honestly |
| `design-researcher` | Design evidence: what is measured, what is taste, what is a convention |
| `education-researcher` | Learning research: effect sizes, replication, and the standing neuromyths |
| `web-researcher` | What may be crawled, from where, and how to trace a claim to its origin |
| `coder` | Implementation, debugging, code review |
| `teacher` | Trains the other agents on new skills |
| `security-engineer` | Read-only audits. Reports; never acts. Runs a different model from the CTO it audits, on purpose |
| `helpdesk` | Answers support questions, walks people through fixes |
| `ceo` | Business strategy and prioritisation |
| `languages` | Language learning and translation, plus religious texts |
| `personal` | Private offline companion. Unfiltered on topic and tone; read-only on the machine, and no network. Built 2026-09-27 from the roster's old `offline-unrestricted` line |
| `artist` | Photorealistic and anime image generation, plus character LoRAs |
| `director` | Video assembly: takes assets and produces finished video |
| `storyteller` | Long-form fiction and narrative. Weighted against the good-looking story with nothing underneath it |

`agents/coder/` is a complete worked example - a real `SOUL.md`, two skills, and
a test file that actually runs. Every new agent is generated from the same
shape by `tools/new-agent.sh`.

Sixteen of the eighteen above are built. The two that are not are `artist` and
`director`, and both need the GPU. `./bootstrap.sh check` validates all 607 test
cases plus 335 retrieval assertions, without needing a GPU or a model server. It
also validates the org chart itself - a reporting line naming an agent that does
not exist, a cycle, or more than one agent at the top fails the tree.

---

## Safety boundaries are configuration, not prompts

```bash
AGENT_SAFETY="read-only"     # read-only | standard | full
AGENT_NETWORK="none"         # none | limited | unrestricted
```

Safety is two keys, and the order matters. `AGENT_SAFETY` is the ceiling -
`read-only`, `standard` or `full`. `AGENT_ACTIONS` is optional and may only ever
*narrow* it: asking for an action above the ceiling is a hard error in
`./bootstrap.sh check` and refuses the run in `tools/test-agent.sh`. So a config
cannot grant itself more than its safety level allows, and the effective set is
printed at run time and written to `state/audit.log` beside the score.

`coder` is the worked example. `standard` permits writing into other agents'
workspaces, which is right for the teacher and wrong for the coder, so the coder
takes `read,write` and leaves `write_other` alone.

This does not sandbox anything. An agent permitted to `execute` can still run the
wrong command; what the keys buy is that the permission set is explicit,
checkable, and attached to every measurement.

The security, network and storage agents ship read-only. This is not
prudence, it is capability: an AI cannot reliably distinguish data from
instructions, so text inside a log file it is reading to help you can be read
as an order. It is also equally confident when it is wrong, which is the
combination that takes firewalls offline at 2am.

The reason is explained properly in
[section 8 of the start-here doc](docs/00-START-HERE.md#8-read-this-before-you-build-the-security-agent).
Everything else on the list runs unrestricted.

---

## The agent is not the runtime

```bash
AGENT_RUNTIME="ollama"        # the program that executes this agent
AGENT_MODEL_ROLE="coding"     # which model role it draws from
```

An agent is a role: a name, a mission, a `SOUL.md` and a set of tests. A
runtime is the program that executes it. This project keeps them separate on
purpose, so you can replace one without touching the other.

Which runtimes exist is declared in [`config/runtimes.json`](config/runtimes.json).
How to talk to them is in [`lib/runtime.sh`](lib/runtime.sh). `agent.conf` names
one; `tools/test-agent.sh` asks the adapter layer to execute it and never
learns what is on the other end of the socket. `tools/check-agents.py` refuses a
runtime that is not in the registry, because a test run that quietly used a
different engine than you thought is worse than no run at all.

Today `ollama` is the only entry, because it is the only adapter written. To add
another: write `_rt_<id>_probe` and `_rt_<id>_chat` in `lib/runtime.sh`, add the
id to `config/runtimes.json`, then point agents at it. No other file changes.

The same separation already holds one level down: `AGENT_MODEL_ROLE="coding"` is
a role from `config/models.json`, not a model name, so the resolver re-picks a
bigger model when the card gets bigger. The runtime layer is the same idea for
the engine instead of the model.

---

## Layout

```
bootstrap.sh          single entry point
config/models.json    YOUR file: roles and candidate models
config/runtimes.json  YOUR file: which runtimes exist
config/profile.env    generated: what this machine can do
lib/                  shared bash helpers, hardware detection
lib/runtime.sh        the runtime adapter layer
lib/audit.sh          the audit log writer
scripts/              numbered setup steps
tools/                new-agent.sh, test-agent.sh, check-agents.py, resolve_models.py
tools/audit-log.sh    read state/audit.log
agents/<name>/        agent.conf, SOUL.md, skills/, tests/
finetune/             dataset prep, for later
state/                your data. Back this up.
  audit.log             every agent run: runtime, model, result, score
```

Everything in `config/` except `models.json` and `runtimes.json` is generated.
Delete the generated files and re-run `./bootstrap.sh detect` and you get them
back.

---

## Every run is recorded

```bash
./bootstrap.sh audit              # the last 20 runs, as a table
./bootstrap.sh audit --failures   # only the ones that did not pass
./bootstrap.sh audit --stats      # counts by agent
./bootstrap.sh audit --agent coder
```

One line per run in `state/audit.log`: which agent, which runtime, which model,
which safety tier, what temperature, and the result. `AGENT_LAST_SCORE` in
`agent.conf` says what an agent last scored; this says what produced that
number, which is the difference between a score and a measurement.

It records names, ids, counts and verdicts - never a prompt, a reply, or any
other content from a run. `security-engineer`'s test cases contain deliberate
prompt-injection payloads as test data, and a log that captured them would be a
file full of text shaped like instructions, sitting in `state/` where the
teacher agent would read it.

---

## Troubleshooting

```bash
./bootstrap.sh doctor
journalctl -u ollama -f
```

The single most common failure is a silent CPU fallback: everything works, it
is just fifty times slower than it should be. `./bootstrap.sh verify` reports
whether the model is actually running on the GPU. If it is not, fix that before
changing anything else.

More in [section 9 of the start-here doc](docs/00-START-HERE.md#9-when-something-breaks).
