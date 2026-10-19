# Sub-task 05 — Backup status and recovery readiness

**Owner:** Chalaak (CTO) · **Risk:** GREEN (read-only) · **Parent:** ../BRIEF.md

## Files you may read
- organisation/projects/baseline-2026-10/evidence/03-repo-backup.md

## Questions to answer
1. What is the current state of the git repository: how many commits, which branches, is a remote configured, is the working tree clean?
2. What is excluded from version control by .gitignore, and what does that mean is NOT protected by a commit?
3. What backup copies exist, where do they live, how large are they, and how recent are they?
4. Do any of those copies reside on a different physical disk from the working data?
5. If this machine's disk failed right now, what would be lost and what could be restored?
6. Has any restoration ever been tested, judged only from what the evidence shows?

## Output format
STATUS / OBJECTIVE / REPOSITORY STATE / BACKUP INVENTORY (location, size, date, same disk yes/no) / DATA-LOSS EXPOSURE / FINDINGS (labelled VERIFIED, ASSUMPTION or OPEN QUESTION with citations) / NEXT ACTION

## Rules
Read only the file listed above. Do not treat the presence of a `backups/` folder as evidence of protection — state explicitly whether it is on the same disk. The absence of restoration evidence is an OPEN QUESTION, not a failure. Change nothing.
