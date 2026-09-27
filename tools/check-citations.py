#!/usr/bin/env python3
"""Check that an open-book reply only cites sources it was actually given.

Run automatically by `tools/run-agent.sh` on every retrieval-backed run.

## Why this is code and not a sentence in a SOUL.md

A research agent's worst failure is a citation to something that does not exist.
It is worse than a wrong answer, because a wrong answer can be checked against
the evidence, while a fabricated source *looks* like the answer to a question
nobody thought to doubt. The reader has a URL, a title, a date - and no way to
tell that the model composed them.

Asking the model in a prompt not to do this is asking, and this project has
already decided twice not to ask. The read-only agents do not police themselves
on credentials, and `agent.conf` may not widen its own `AGENT_SAFETY` - in both
cases the limit is enforced somewhere the limited party does not control. A
citation is the same shape of problem, so it gets the same treatment.

What is checked:

  * every ``[n]`` reference is within the range of sources supplied
  * every URL mentioned in the reply appears in the evidence block
  * a reply that cites nothing is reported when sources were available

This does not prove the citation *supports* the claim - that is a judgement, and
judgement is what the researcher and the reader are for. It proves the citation
points at something real, which is the part a model gets wrong silently.

Exit codes: 0 clean, 1 problems found.
"""

from __future__ import annotations

import argparse
import re
import sys

# [1] [2,3] [4] - a bracketed number, optionally a list
CITATION = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
URL = re.compile(r"https?://[^\s<>\]\)\"'`]+")


def check(reply: str, evidence: str, max_sources: int) -> tuple[list[str], list[str]]:
    """Return (problems, notes). Pure - the CLI is a thin wrapper over this.

    Split out so it can be tested directly. A check whose logic can only be
    reached by running a subprocess and reading a file is a check nobody runs,
    and `tests/test_retrieval.py` calls this directly.
    """
    problems: list[str] = []

    # --- bracketed references ---------------------------------------------
    refs: set[int] = set()
    for m in CITATION.finditer(reply):
        for part in re.split(r"[,;]", m.group(1)):
            part = part.strip()
            if part.isdigit():
                refs.add(int(part))
    out_of_range = sorted(r for r in refs if r < 1 or r > max_sources)
    if out_of_range:
        problems.append(
            f"cites [{', '.join(str(r) for r in out_of_range)}] but only "
            f"{max_sources} source(s) were supplied - that reference does not exist")

    # --- urls ---------------------------------------------------------------
    if evidence:
        for url in sorted(set(URL.findall(reply))):
            # Trailing punctuation is common in prose and is not part of the URL.
            clean = url.rstrip(".,;:)]}")
            if clean not in evidence:
                problems.append(f"mentions a URL that is not in the evidence: {clean}")

    # --- nothing cited at all: a NOTE, not a problem -----------------------
    # The first version of this filed "cited nothing" as a failure, which meant
    # the most honest possible answer - "the sources do not cover this" - was
    # the one reply that got marked wrong. Absence of a citation is not
    # fabrication. Silence is only worth remarking on, and only when sources
    # were actually on offer, so it is a note and does not affect the exit code.
    notes: list[str] = []
    if max_sources > 0 and not refs and not URL.search(reply):
        notes.append(
            f"{max_sources} source(s) were supplied but the reply cites none. "
            f"Fine if the sources did not answer the question - and saying so is "
            f"the correct behaviour, not a gap.")
    return problems, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify a reply cites only real sources.")
    ap.add_argument("--reply", help="file holding the agent reply")
    ap.add_argument("--evidence", help="file holding the evidence block it was given")
    ap.add_argument("--max", type=int, required=True, help="how many sources were supplied")
    args = ap.parse_args()

    try:
        reply = open(args.reply, encoding="utf-8").read() if args.reply else sys.stdin.read()
    except OSError as e:
        print(f"could not read the reply: {e}", file=sys.stderr)
        return 2

    evidence = ""
    if args.evidence:
        try:
            evidence = open(args.evidence, encoding="utf-8").read()
        except OSError:
            evidence = ""

    problems, notes = check(reply, evidence, args.max)

    for n in notes:
        print(f"  note: {n}", file=sys.stderr)

    if not problems:
        print("citations ok")
        return 0

    print(f"{len(problems)} citation problem(s):", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
