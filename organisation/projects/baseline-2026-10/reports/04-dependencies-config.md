<!-- Produced by Chalaak (CTO) via OpenCode on 2026-10-20T02:05:42+08:00. Elapsed 126s. Reviewed by CEO before acceptance. -->

[0m
> cto · qwen3.5:9b
I'll carry out this sub-task as defined. Let me start by reading the task brief first.
[0m→ [0mRead organisation/projects/baseline-2026-10/tasks/04-dependencies-config.md 
> cto · qwen3.5:9b
Now I need to read only the files it names as specified:
[0m→ [0mRead organisation/registries/MODELS.md 
[0m→ [0mRead organisation/projects/baseline-2026-10/evidence/02-runtimes-deps.md 
[0m→ [0mRead organisation/registries/RUNTIMES.md 
> cto · qwen3.5:9b
Now I have all the information needed. Let me compile the report in the exact output format specified:

```markdown
# Status: Green (read-only inspection complete) / Objective: Answer 6 dependency/config questions by comparing evidence to registries

## INSTALLED SOFTWARE TABLE
| Software | Version | State Source |
|----------|---------|--------------|
| opencode | v2.0.32 | Evidence 02-runtimes-deps.md, line 16 |
| ollama | 0.40.5 | Evidence 02-runtimes-deps.md, line 17 |
| Hermes Agent | v0.22.2 (2026.9.24) | Evidence 02-runtimes-deps.md, line 18; RUNTIMES.md records only as ACTIVE |
| Python | 3.14.4 (opencode), 3.14.7 (Hermes) | Evidence 02-runtimes-deps.md, line 19 |
| git | 2.53.0 | Evidence 02-runtimes-deps.md, line 20 |
| node | v24.22.0 | Evidence 02-runtimes-deps.md, line 21 |

*Registry record:* RUNTIMES.md lists runtime names and ACTIVE state only; does not record versions.

---

## HARDWARE TABLE
| Resource | Specification | Available | Used | Consumed % | Mount Point / Location |
|----------|--------------|-----------|------|-------------|------------------------|
| CPU | Not specified in evidence | — | — | — | — |
| Memory | 15 Gi total | 15 Gi | 3.9 Gi | ~26% | root `/` |
| Swap | 4.0 Gi total | 4.0 Gi | 117 Mi | ~3% | — |
| GPU | NVIDIA GeForce RTX 3060 | 12288 MiB | 7613 MiB | ~62% | Driver v595.99.02 |
| Disk | nvme0n1p3 (LVM) | 950.8 Gi partition / 61 Gi mounted | 33 Gi used of 98 Gi mounted | 35% | `/` |
| Ollama models store | — | 11 Gi occupied | — | — | /usr/share/ollama/.ollama/models |

*Registry record:* None; MODELS.md and RUNTIMES.md do not contain hardware inventory.

---

## CONFIGURATION TABLE (setting, value, tuned or default)
| Setting | Value | Tuned or Default | Source |
|---------|-------|------------------|--------|
| opencode.provider.ollama.npm | "@ai-sdk/openai-compatible" | Tuned | Evidence config JSON |
| opencode.provider.ollama.name | "Ollama Local" | Tuned | Evidence config JSON |
| opencode.provider.ollama.options.baseURL | "http://127.0.0.1:11434/v1" | Tuned | Evidence config JSON |
| opencode.provider.ollama.models.qwen3.5:9b.name | "Qwen 3.5 9B (Local)" | Tuned | Evidence config JSON |
| opencode.provider.ollama.models.qwen3.5:9b.limit.context | 65536 | Tuned | Evidence config JSON |
| opencode.provider.ollama.models.qwen3.5:9b.limit.output | 8192 | Tuned | Evidence config JSON |
| opencode.model | "ollama/qwen3.5:9b" | Tuned per role docs | Evidence config JSON |
| OpenCode.service.address | http://127.0.0.1:49374 | Tuned (listening) | Evidence service status |

*Registry record:* No configuration storage; RUNTIMES.md and MODELS.md are governance documents only.

---

## REGISTRY GAPS (facts in evidence NOT recorded in either registry)
| Fact Category | Evidence Source Location | Not Recorded In Registry |
|---------------|------------------------|--------------------------|
| Runtime versions (opencode, ollama, hermes) | Evidence 02-runtimes-deps.md lines 16–18 | RUNTIMES.md records only names/states |
| Model sizes installed in Ollama store | Evidence 02-runtimes-deps.md lines 23–25; line 33 (11 Gi total) | MODELS.md contains no model inventory |
| Models currently resident in memory | Evidence 02-runtimes-deps.md line 30–31 | Not recorded anywhere |
| GPU memory usage | Evidence 02-runtimes-deps.md line 36–37 | Not recorded anywhere |
| System memory and swap status | Evidence 02-runtimes-deps.md lines 39–42 | Not recorded anywhere |
| Disk filesystem usage | Evidence 02-runtimes-deps.md lines 58–59 | Not recorded anywhere |
| Ollama base URL configuration | Evidence config JSON line 70 | Not recorded in MODELS.md nor RUNTIMES.md |
| Context and output limits for qwen3.5:9b | Evidence config JSON lines 76–77 | Not recorded in MODELS.md nor RUNTIMES.md |

---

## FINDINGS (labelled VERIFIED, ASSUMPTION or OPEN QUESTION)

1. **VERIFIED** — The runtime registry uses state field (ACTIVE, CURRENT) to indicate availability rather than version numbers; versions are found only in evidence file Evidence 02-runtimes-deps.md (line 16–18).

2. **VERIFIED** — The model registry contains no model inventory table; it is a governance document (MODELS.md lines 3, 5–8) declaring independence principles rather than recording which models are installed or resident.

3. **VERIFIED** — RUNTIMES.md records only runtime names and ACTIVE state in its table (lines 6–9); does not record version numbers or hardware dependencies.

4. **ASSUMPTION** — The Ollama model store at /usr/share/ollama/.ollama/models shows 11 Gi occupied, which implies qwen3:8b (5.2 GB) and qwen3.5:9b (6.6 GB) are installed; their sizes from lines 24–25 of evidence match the total approximately.

5. **OPEN QUESTION** — The disk partition nvme0n1p3 is 950.8 Gi but only 100 Gi mounted as LVM at / (lines 53–59, note lines 55–93); remaining ~850 Gi not mounted and usage unknown without elevated commands.

6. **VERIFIED** — The model-to-serving-layer pairing is inferred from: configuration in ~/.config/opencode/opencode.json specifies qwen3.5:9b with service at 49374; RUNTIMES.md does not record this relationship, only that OpenCode serves as CTO/technical runtime.

---

## NEXT ACTION
No changes required for read-only sub-task. Evidence gathered and gaps documented. Recommend Owner review of OPEN QUESTION regarding unmounted disk space before any capacity planning or model deployment expansions.
```
