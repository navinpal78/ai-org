#!/usr/bin/env python3
"""
prepare_dataset.py - turn real usage into a fine-tuning dataset.

    ./finetune/prepare_dataset.py --agent coder --input raw.tsv --out data.jsonl
    ./finetune/prepare_dataset.py --agent coder --validate data.jsonl

This does NOT train anything. It normalises, validates and splits a dataset so
that when you do train, you are not training on your own test cases by
accident - which is the single most common way a fine-tune appears to work and
then does nothing in production.

Input formats accepted for --input:

  .tsv   name ::: user_prompt ::: the_reply_you_approved
  .jsonl already in chat format: [{"role": "...", "content": "..."}, ...]
  .md    a transcript: "## User" / "## Agent" sections, or "User:" / "Agent:"

Collecting the raw data:

  * Run real tasks through the agent with --verbose and keep the ones you were
    happy with. Those are your positive examples.
  * Keep the ones it got wrong, together with your correction. Those are your
    most valuable examples - they target exactly the failure.
  * The prompts in agents/<name>/tests/cases.tsv are your evaluation set. This
    script refuses to let them silently end up in the training data.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Reading the various input formats
# ---------------------------------------------------------------------------


def read_tsv(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split(":::")
        if len(parts) < 3:
            continue
        prompt, reply = parts[1].strip(), parts[2].strip()
        if not prompt or not reply:
            continue
        rows.append({"user": prompt, "assistant": reply})
    return rows


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"  line {i}: not valid JSON ({exc}) - skipped", file=sys.stderr)
            continue
        # Either a full conversation, or a simple user/assistant object.
        if isinstance(obj, list) and obj:
            user = next((m for m in obj if m.get("role") == "user"), None)
            assistant = next(
                (m for m in obj if m.get("role") in ("assistant", "model")), None
            )
            if user and assistant:
                rows.append({"user": user["content"], "assistant": assistant["content"]})
        elif isinstance(obj, dict) and "user" in obj and "assistant" in obj:
            rows.append({"user": obj["user"], "assistant": obj["assistant"]})
    return rows


def read_markdown(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    rows = []
    # "## User" / "## Agent" headings
    blocks = re.split(
        r"^##+\s*(User|Agent|Assistant|Human)\s*$", text, flags=re.M | re.I
    )
    current: str | None = None
    for block in blocks:
        role = "user" if block.lower() == "user" or block.lower() == "human" else "agent"
        if block in ("User", "Agent", "Assistant", "Human"):
            current = role
            continue
        if current == "user":
            rows.append({"user": block.strip(), "assistant": ""})
        elif current == "agent" and rows and not rows[-1]["assistant"]:
            rows[-1]["assistant"] = block.strip()
    # "User:" / "Agent:" inline prefixes
    if not rows:
        turns = re.split(r"^\s*(?:User|Human|Agent|Assistant)\s*:\s*", text, flags=re.M)
        for i in range(1, len(turns) - 1, 2):
            u, a = turns[i].strip(), turns[i + 1].strip()
            if u and a:
                rows.append({"user": u, "assistant": a})
    return [r for r in rows if r.get("user") and r.get("assistant")]


READERS = {".tsv": read_tsv, ".jsonl": read_jsonl, ".md": read_markdown, ".txt": read_markdown}


# ---------------------------------------------------------------------------
# Test-case leakage
# ---------------------------------------------------------------------------


def load_test_prompts(agent: str) -> list[str]:
    path = ROOT / "agents" / agent / "tests" / "cases.tsv"
    if not path.exists():
        return []
    prompts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split(":::")
        if len(parts) >= 2 and parts[1].strip():
            prompts.append(parts[1].strip().lower())
    return prompts


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def find_leakage(rows: list[dict], test_prompts: list[str]) -> list[tuple[int, str]]:
    """Return (index, prompt) for training rows that duplicate a test prompt."""
    if not test_prompts:
        return []
    leaks = []
    for i, row in enumerate(rows):
        n = normalise(row["user"])
        for tp in test_prompts:
            t = normalise(tp)
            if not t:
                continue
            # Exact, or one contained in the other, or high overlap.
            if n == t or t in n or n in t:
                leaks.append((i, tp))
                break
            words_t = set(t.split())
            words_n = set(n.split())
            if words_t and len(words_t & words_n) / len(words_t) > 0.8:
                leaks.append((i, tp))
                break
    return leaks


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def display(path: Path) -> str:
    """Project-relative when possible, absolute when the path is outside it."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_dataset(
    rows: list[dict], system_prompt: str, out: Path, val_frac: float
) -> tuple[Path, Path]:
    out.parent.mkdir(parents=True, exist_ok=True)
    train, val = [], []
    # Deterministic split: every 5th example goes to validation. Reproducible,
    # which matters when you are comparing two training runs.
    for i, row in enumerate(rows):
        record = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": row["user"]},
                {"role": "assistant", "content": row["assistant"]},
            ]
        }
        (val if i % 5 == 0 and val_frac > 0 else train).append(record)

    train_path = out.with_name(out.stem + "-train.jsonl")
    val_path = out.with_name(out.stem + "-val.jsonl")

    train_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in train), encoding="utf-8"
    )
    val_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in val), encoding="utf-8"
    )
    return train_path, val_path


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Normalise and validate a fine-tuning dataset."
    )
    ap.add_argument("--agent", required=True, help="agent name, e.g. coder")
    ap.add_argument("--input", type=Path, help="raw file: .tsv, .jsonl or .md")
    ap.add_argument("--out", type=Path, default=ROOT / "finetune" / "data" / "dataset.jsonl")
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument(
        "--validate",
        type=Path,
        help="just check an existing dataset file, produce nothing",
    )
    args = ap.parse_args()

    soul_path = ROOT / "agents" / args.agent / "SOUL.md"
    if not soul_path.exists():
        print(f"[fail] No SOUL.md for agent '{args.agent}'.", file=sys.stderr)
        return 1
    system_prompt = soul_path.read_text(encoding="utf-8").strip()

    test_prompts = load_test_prompts(args.agent)

    # ---- validate-only mode ----
    if args.validate:
        rows = read_jsonl(args.validate)
        return report(rows, test_prompts, args.agent, system_prompt, None)

    # ---- build mode ----
    if not args.input:
        ap.error("--input is required unless you pass --validate")

    if not args.input.exists():
        print(f"[fail] No such file: {args.input}", file=sys.stderr)
        return 1

    reader = READERS.get(args.input.suffix.lower())
    if reader is None:
        print(
            f"[fail] Unsupported extension '{args.input.suffix}'.\n"
            f"       Use .tsv, .jsonl, .md or .txt",
            file=sys.stderr,
        )
        return 1

    print(f"\n  Reading {args.input}")
    rows = reader(args.input)
    if not rows:
        print(
            f"[fail] No usable examples found in {args.input}.\n"
            f"       For .tsv, each line must be:\n"
            f"         name ::: user_prompt ::: approved_reply",
            file=sys.stderr,
        )
        return 1
    print(f"  Found {len(rows)} example(s)")

    return report(rows, test_prompts, args.agent, system_prompt, args.out)


def report(
    rows: list[dict],
    test_prompts: list[str],
    agent: str,
    system_prompt: str,
    out: Path | None,
) -> int:
    print()
    print(f"  Dataset report for agent '{agent}'")
    print("  " + "-" * 60)

    sys_words = len(system_prompt.split())
    user_words = [len(r["user"].split()) for r in rows]
    asst_words = [len(r["assistant"].split()) for r in rows]
    total_words = sys_words + sum(user_words) + sum(asst_words)

    def stats(v: list[int]) -> str:
        if not v:
            return "n/a"
        return f"min {min(v)}, median {sorted(v)[len(v)//2]}, max {max(v)}"

    print(f"  examples        {len(rows)}")
    print(f"  system prompt   {sys_words} words (fixed, from SOUL.md)")
    print(f"  user turns      {stats(user_words)} words")
    print(f"  replies         {stats(asst_words)} words")
    print(f"  approx tokens   ~{int(total_words * 1.3)}  (rough, 1.3 tokens/word)")
    print("  " + "-" * 60)

    # Leakage check
    leaks = find_leakage(rows, test_prompts)
    if leaks:
        print(f"  LEAKAGE WARNING: {len(leaks)} training example(s) duplicate a test case.")
        for idx, prompt in leaks[:10]:
            print(f"    row {idx}: \"{prompt[:70]}\"")
        print()
        print("    Training on your test cases makes the training score meaningless")
        print("    and the model no better. Remove these rows before training.")
        if out is None:
            print("  " + "-" * 60)
            return 1
    else:
        print(f"  leakage         none (checked against {len(test_prompts)} test prompts)")
    print("  " + "-" * 60)

    if out is None:
        print()
        return 1 if leaks else 0

    if len(rows) < 20:
        print(f"  NOTE: only {len(rows)} examples. That is very few for fine-tuning.")
        print("        Below roughly 50 the result is usually worse than the base")
        print("        model. Prefer prompt-and-test for now. See finetune/README.md")
        print("  " + "-" * 60)

    train_path, val_path = write_dataset(rows, system_prompt, out, 0.2)
    print()
    print(f"  Wrote {display(train_path)}")
    print(f"  Wrote {display(val_path)}")
    print()
    print("  Next steps (see finetune/README.md):")
    print("    1. Use train file for training, val file for evaluation")
    print("    2. Train a LoRA with Unsloth - not a full fine-tune")
    print("    3. Serve the adapter and re-run:  ./tools/test-agent.sh " + agent)
    print("    4. If the test score got worse, discard the adapter. That is a real")
    print("       outcome, not a mistake.")
    print()
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
