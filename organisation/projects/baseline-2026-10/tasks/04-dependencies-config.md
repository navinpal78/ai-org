# Sub-task 04 — Dependencies and configuration

**Owner:** Chalaak (CTO) · **Risk:** GREEN (read-only) · **Parent:** ../BRIEF.md

## Files you may read
- organisation/projects/baseline-2026-10/evidence/02-runtimes-deps.md
- organisation/registries/RUNTIMES.md
- organisation/registries/MODELS.md

## Questions to answer
1. Which runtimes are installed, at which versions, and which does the runtime registry record?
2. Which models are installed locally, at what size, and which are currently resident in memory?
3. What hardware is available (CPU, memory, GPU memory, disk), and how much is already consumed?
4. Which configuration values are deliberately tuned, and which are left at defaults?
5. Does the registry record the model-to-serving-layer pairing anywhere, or only the model name?
6. Which dependency or configuration facts in the evidence are NOT recorded in either registry?

## Output format
STATUS / OBJECTIVE / INSTALLED SOFTWARE TABLE / HARDWARE TABLE / CONFIGURATION TABLE (setting, value, tuned or default) / REGISTRY GAPS / FINDINGS (labelled VERIFIED, ASSUMPTION or OPEN QUESTION with citations) / NEXT ACTION

## Rules
Read only the files listed above. The registries are policy documents and may legitimately contain no inventory table; if so, record that as a gap, not as an error. Do not estimate a version or a size that is not shown. Change nothing.
