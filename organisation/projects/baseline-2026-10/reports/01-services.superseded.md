<!-- Produced by Chalaak (CTO) via OpenCode on 2026-10-20T01:42:53+08:00. Elapsed 152s. Reviewed by CEO before acceptance. -->

[0m
> cto · qwen3.5:9b
I'll start by reading the task file to understand what needs to be done.
[0m→ [0mRead organisation/projects/baseline-2026-10/tasks/01-services.md 
> cto · qwen3.5:9b
Now I'll read the evidence file as specified in the brief.
[0m→ [0mRead organisation/projects/baseline-2026-10/evidence/01-services.md 
> cto · qwen3.5:9b
Now I'll produce the report in the exact output format specified.

---

**STATUS**: GREEN (read-only inspection)

**OBJECTIVE**: Produce services inventory report answering questions about systemd units, listening ports, AI processes, and the `services/` directory

**FINDINGS**:

1. **Which services are installed as systemd units, and which are actually running?**
   - VERIFIED: ollama.service is loaded=enabled, active=running (evidence section "systemd units matching ai/ollama/opencode/hermes/ceo/gateway")
   - ASSUMPTION: No other AI-related systemd units detected in evidence; only ollama.service is confirmed running
   - Citing evidence: Section 5 of evidence/01-services.md

2. **Which network ports are listening, which process holds each, and is each bound to localhost or exposed?**
   - VERIFIED: Ports captured in evidence (sections 14-26): 22 (SSH - exposed), 53 (DNS on 127.0.0.53/127.0.0.54 - localhost), 3100 (localhost), 35287 (ollama server on 127.0.0.1), 46303 (remote IP), 54329 (postgres on 127.0.0.1)
   - ASSUMPTION: Process ownership inferred from "users:" columns where present; no ports definitively bound to localhost-only vs exposed distinction available without process names
   - Citing evidence: Sections 14-26 of evidence/01-services.md

3. **Which long-running processes belong to the AI organisation, and how long has each been up?**
   - VERIFIED: 
     - `35204 ollama run qwen3:8b` — uptime 02:32:00 (section 29)
     - `52822 /usr/local/bin/ollama serve` — uptime 01:43:55 (section 30)
     - `62648 llama-server` — uptime 12:36 (section 31)
     - `64465 opencode serve --service` — uptime 03:09 (section 32)
   - ASSUMPTION: All listed are AI/organisation processes; exact organisation membership inferred from process names matching project scope
   - Citing evidence: Sections 27-32 of evidence/01-services.md

4. **What is in the `services/` directory, and does a running service correspond to each item there?**
   - VERIFIED: services/ contains two directories: ceo (with bootstrap.sh) and ceo-gateway (with gateway.py, .backup files, setup-telegram.sh, __pycache/) (sections 35-62)
   - ASSUMPTION: Running service corresponds to ceo-gateway (gateway.py is running as Python process based on evidence); ceo/bootstrap.sh is not currently running
   - Citing evidence: Sections 34-62 of evidence/01-services.md

5. **Is anything in `services/` NOT running, or anything running that `services/` does not describe?**
   - OPEN QUESTION: ollama.service running but no corresponding directory in services/ listed for it (only ceo and ceo-gateway directories exist)
   - ASSUMPTION: Other listening processes (postgres on 54329, generic TCP bind addresses) may represent services not described in services/
   - Citing evidence: Full evidence file; discrepancy noted between running systemd units (ollama.service) and services/ directory contents

**CONTRACTIONS**: None identified. Evidence consistently describes ollama as the primary service unit with gateway.py implementation under ceo-gateway directory.

**NEXT ACTION**: Report complete per sub-task 01-services brief requirements.
