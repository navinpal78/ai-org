# Sub-task 01 — Services inventory

**Owner:** Chalaak (CTO) · **Risk:** GREEN (read-only) · **Parent:** ../BRIEF.md

## Files you may read
- organisation/projects/baseline-2026-10/evidence/01-services.md

## Questions to answer
1. Which services are installed as systemd units, and which are actually running?
2. Which network ports are listening, which process holds each, and is each bound to localhost or exposed?
3. Which long-running processes belong to the AI organisation, and how long has each been up?
4. What is in the `services/` directory, and does a running service correspond to each item there?
5. Is anything in `services/` NOT running, or anything running that `services/` does not describe?

## Output format
STATUS / OBJECTIVE / FINDINGS (numbered, each labelled VERIFIED, ASSUMPTION or OPEN QUESTION, each citing the evidence file) / CONTRADICTIONS / NEXT ACTION

## Rules
Read only the file listed above. If the evidence does not answer a question, write "not present in the files provided". Do not guess a port, a path or a process. Change nothing.
