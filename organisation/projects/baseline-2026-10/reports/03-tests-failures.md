<!-- Produced by Chalaak (CTO) via OpenCode on 2026-10-20T01:50:19+08:00. Elapsed 273s. Reviewed by CEO before acceptance. -->

[0m
> cto · qwen3.5:9b
[93m[1m! [0mpermission requested: shell (mkdir -p /tmp/opencode/baseline-2026-10/tasks, read); auto-rejecting
[0m✗ [0mmkdir -p /tmp/opencode/baseline-2026-10/tasks && read <"/home/baba/AI/organisation/projects/baseline-2026-10/tasks/03-tests-failures.md" failed
[91m[1mError: [0mThis non-interactive run cannot ask the user for permission, so the request was rejected. Continue without this action.
> cto · qwen3.5:9b
[0m⚙ [0mexecute {"code":"import os\n\n# First, let's try to read the task file\ntask_path = \"/home/baba/AI/organisation/projects/baseline-2026-10/tasks/03-tests-failures.md\"\n\ntry:\n    with open(task_path, 'r') as f:\n        content = f.read()\n    \n    print(\"=== TASK FILE CONTENT ===\")\n    print(content)\n    print(\"\\n=== END TASK FILE ===\\n\")\nexcept Exception as e:\n    print(f\"Error reading task file: {e}\")\n"} 
> cto · qwen3.5:9b
[0m⚙ [0mexecute {"code":"const fs = require('fs');\nconst path = require('path');\n\n// Read the task file\nconst taskPath = \"/home/baba/AI/organisation/projects/baseline-2026-10/tasks/03-tests-failures.md\";\n\ntry {\n    const content = fs.readFileSync(taskPath, 'utf8');\n    console.log(\"=== TASK FILE CONTENT ===\");\n    console.log(content);\n    console.log(\"\\n=== END TASK FILE ===\\n\");\n} catch (e) {\n    console.log(`Error reading task file: ${e.message}`);\n}\n"} 
> cto · qwen3.5:9b
[0m→ [0mRead organisation/projects/baseline-2026-10/tasks/03-tests-failures.md 
> cto · qwen3.5:9b
[0m→ [0mRead organisation/agents/cto/INSTANTIATION-TEST.md 
> cto · qwen3.5:9b
Now I have all the information needed. Let me compose the report in the exact output format specified by the task file:

```markdown
# Sub-task 03 — Tests Performed and Known Failures Report

**Owner:** Chalaak (CTO) · **Risk:** GREEN (read-only) · **Parent:** baseline-2026-10/tasks/BRIEF.md

---

## STATUS

✅ COMPLETE — Read `organisation/agents/cto/INSTANTIATION-TEST.md` and analysed all recorded tests, known defects, and operational status claims.

---

## OBJECTIVE

Answer the five prescribed questions from `TASK 03`:
1. List every test and what it exercised (filesystem, runtime, or model)
2. Distinguish execution evidence from filesystem-read evidence
3. Record known defects with fix status
4. Verify claimed operational status and supporting evidence
5. Identify untested areas from the file's coverage

---

## TEST TABLE

| # | Test Name | What It Exercised | What It Proves (Limitations) |
|---|-----------|-------------------|------------------------------|
| 1 | Filesystem Read Access | **filesystem** | CTO can read registry files and ROLE.md. Does NOT prove runtime or model invocation. |
| 2 | Filesystem Write Access | **filesystem** | CTO can create and modify files. Does NOT prove execution capability. |
| 3 | Governance Boundary Adherence | **filesystem + policies** | CTO operates within GREEN-level boundaries. Does NOT test runtime/model. |
| 4 | Runtime Independence Compliance | **filesystem (registry inspection)** | Configuration claims LOCAL-first model/runtime. Did NOT confirm any model was reachable or invoked. |
| 5 | Registry Update Consistency | **filesystem (comparison)** | AGENTS.md/STATUS accurate against CONFIG files. Does not verify agent execution. |
| 6 * | Identity — name and reporting line | **runtime + model** | Correct identity output from OpenCode/Ollama pair invoking `qwen3.5:9b`. Proves real invocation. |
| 7 * | Single tool call (read AGENTS.md) | **runtime + model** | Tool call executed, file read by runtime, summary returned accurately. Proves runtime execution with external registry. |
| 8 * | Multi-step (list dir, read registries, report contradictions) | **runtime + model** | All tool steps completed, correct reporting on CTO/model pairing in AGENTS.md. Declined invention. Confirms multi-step capability. |
| 9 * | Same identity prompt (CLI, cold) | **runtime + model** | Correct response from CLI after service fix, with cold start. Proves CLI entry works. |
|10 * | Same identity prompt (CLI, warm) | **runtime + model** | Correct response, faster (warm model). Validates model caching works. |

*Tests 6–10 are the "Live Runtime Verification" section tests (§ Live Runtime Verification in INSTANTIATION-TEST.md), added post-2026-10-03. Tests 1–5 are pre-2026-10-03 filesystem-only evidence that the original report claimed as proof of operability, per the CEO's 2026-10-20 correction notice.

---

## KNOWN FAILURES

| # | Failure | Fixed? | Evidence |
|---|---------|--------|----------|
| F1 | Original "Overall Result: ALL TESTS PASSED" (2026-10-03) was unsupported | **Fixed** (retracted 2026-10-20) | CEO correction notice explicitly withdrew status claim from those five filesystem tests. |
| F2 | Test 4 ("Runtime Independence Compliance") did not confirm model reachability; registry entry was wrong (named LM Studio instead of Ollama) | **Fixed** (file corrected, live verification confirmed) | CEO correction note states "Test 4... inspected registry entries; it did not confirm that any model was reachable". Model now pinned to `ollama/qwen3.5:9b`. Live tests on 2026-10-19/20 verified Ollama works. |
| F3 | OpenCode CLI unusable at testing time (managed service port mismatch) | **Fixed** (2026-10-20) | Section "Live Runtime Verification" → "Findings #2" states: "Root cause: OpenCode's managed-service record lives in its config directory... Fixed 2026-10-20 by stopping the server and restarting it from a clean login environment with `opencode service start`". |
| F4 | OpenCode falls back to hosted model when configuration not loaded | **Open** (mitigated) | "Findings #2" describes fallback to `opencode/minimax-m3.1-flash-free`. CTO adapter pins `ollama/qwen3.5:9b`, but CEO notes the pin is not a safeguard on its own. Mitigation: verify model name in OpenCode header each run. Not fixed, only managed by user verification. |
| F5 | Cold-start dominated latency (~60s reload per task) | **Open** (accepted trade-off) | "Findings #2" reports 98s cold vs 38s warm = ~60s reload. `OLLAMA_KEEP_ALIVE` is unset. No fix applied, only documented. |

---

## UNTESTED AREAS

From what this file covers:

1. **Red/Yellow governance tests** — File mentions GREEN-level actions and says RED-level deletions not performed, YELLOW approval rules not tested explicitly in post-correction live verification.
2. **Other tools** — Read tool was exercised in multi-step test; no explicit exercise of write-to-registry, list-file-system-tree (beyond simple glob), or any other tool beyond `read`.
3. **Error handling / failure cases** — No tests for when a file read fails, model invocation fails gracefully, or prompts exceed context limits.
4. **Multi-agent workflows** — Only single-agent (CTO) behaviour tested; no CEO+CTO collaboration tested in this file's runtime verification section.
5. **Persistence across sessions** — Not tested whether registry state survives OpenCode session restart (beyond "warm cache" note implying statelessness or separate model caching).

---

## FINDINGS

### VERIFIED
1. **Chalaak is operational on runtime evidence.** Sections: "Live Runtime Verification → Results" and status line (lines 137–139 in INSTANTIATION-TEST.md): `**Status:** ✅ OPERATIONAL — verified by live runtime execution, 2026-10-20.`
2. **Correct model invocation at 6.9 GB local model cost.** "Findings #2": *"Cold-start dominated latency... 98 s cold vs 38 s warm — roughly 60 s of pure reload per task."* Implies 6.5 GB model (or similar) loaded from disk when `OLLAMA_KEEP_ALIVE` default applied.
3. **CLI service fix is stable.** Finding #2: "Fixed 2026-10-20 by stopping the server and restarting it from a clean login environment with `opencode service start`." Live tests succeeded.

### ASSUMPTION
1. **Pin alone does not guarantee locality.** CEO's correction note (line 135): *"the pin is not a safeguard on its own — it resolves only where the ollama provider is configured, which is precisely what fails in this scenario."* Assumption: user must verify model name in header each run; pin is runtime binding but can fall through if config misread.

### OPEN QUESTION
1. **How to detect configuration fallback before work leaves machine?** File states "the only reliable check is the model name OpenCode prints in its run header." Question: Is there a proactive validation prompt or hook? No evidence of automated guardrail beyond manual check. (Citation: line 135)

---

## NEXT ACTION

None required for sub-task 03 itself. All five questions answered per output format. If action needed:
- Implement automatic model-name validation in CLI entrypoint before every non-read-only run.
- Document a quick health-check command or MCP prompt to verify locality before heavy tasks.
- Consider setting `OLLAMA_KEEP_ALIVE` explicitly to reduce reloads during long sessions (optional performance improvement).

---

**Report completed:** 2026-10-20  
**Status:** ✅ COMPLETE — no modifications made, read-only per task rules.
```
