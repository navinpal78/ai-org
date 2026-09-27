#!/usr/bin/env python3
"""
resolve_models.py - turn the detected hardware into a concrete model choice.

Reads:
  config/hardware.json   written by lib/hwdetect.py
  config/models.json     your editable catalog of roles and candidates

Writes:
  config/models.env      shell-sourceable: ROLE=model, plus fit notes

The rule, in one line:
  for each role, pick the LARGEST candidate that fits the detected VRAM.

"Fit" is measured as vram_gb / usable_vram_gb, so the same catalog produces a
small model on a 3060 and a large one on a 48GB card with no edits. Nothing
here knows any specific model size in advance - it only compares the numbers
in the catalog against the numbers the hardware reported.

Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
HARDWARE = CONFIG / "hardware.json"
CATALOG = CONFIG / "models.json"
OUT = CONFIG / "models.env"


def load_json(path: Path, label: str) -> dict:
    if not path.exists():
        print(f"[fail] Missing {label}: {path}", file=sys.stderr)
        print(f"       Run './bootstrap.sh detect' first.", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"[fail] {label} is not valid JSON: {exc}", file=sys.stderr)
        print(f"       Fix the JSON in {path}", file=sys.stderr)
        sys.exit(1)


def role_var(role: str) -> str:
    """The env var PREFIX for a model role: `adversarial-review` -> `ADVERSARIAL_REVIEW`.

    MUST stay identical to aiorg_role_var() in lib/common.sh, which the three
    bash readers use. Two implementations on purpose - this file must not depend
    on bash being present - but a hyphen is not legal in a shell identifier, so
    getting this wrong writes models.env lines that bash silently fails to parse
    and every caller then reports "no model resolved for role", which reads like
    a hardware problem. tests/test_retrieval.py asserts the two agree.
    """
    return role.upper().replace("-", "_")


def classify(ratio: float, fit: dict) -> str:
    if ratio <= fit["comfortable_max"]:
        return "comfortable"
    if ratio <= fit["tight_max"]:
        return "tight"
    return "too-tight"


def resolve_role(role: str, spec: dict, usable_gb: float, fit: dict) -> dict | None:
    """Pick the largest candidate that fits, preferring a comfortable fit."""
    evaluated = []
    for cand in spec.get("candidates", []):
        need = float(cand["vram_gb"])
        ratio = need / usable_gb if usable_gb > 0 else float("inf")
        evaluated.append({
            **cand,
            "ratio": ratio,
            "margin": classify(ratio, fit),
        })

    # Largest first.
    evaluated.sort(key=lambda c: c["vram_gb"], reverse=True)

    fitting = [c for c in evaluated if c["margin"] != "too-tight"]
    if not fitting:
        return None
    # The first entry is the largest that fits.
    return fitting[0]


def main() -> int:
    hw = load_json(HARDWARE, "hardware profile")
    catalog = load_json(CATALOG, "model catalog")

    usable_gb = float(hw["gpu"]["usable_vram_gb"])
    if usable_gb <= 0:
        # CPU-only: fake a small budget so resolution still produces something
        # sensible instead of failing. The note below tells the user.
        usable_gb = 8.0
        cpu_only = True
    else:
        cpu_only = False

    fit = catalog.get("fit", {"comfortable_max": 0.75, "tight_max": 0.92})

    lines = [
        "# ============================================================",
        "# GENERATED FILE - do not edit by hand.",
        "# Written by tools/resolve_models.py from config/hardware.json +",
        "# config/models.json. Re-run:  ./bootstrap.sh detect",
        "#",
        "# To change a model, edit config/models.json and re-run.",
        "# ============================================================",
        "",
        f'AI_USABLE_GB="{hw["gpu"]["usable_vram_gb"]}"',
        f'AI_TIER="{hw.get("_tier", "unknown")}"',
    ]

    resolved: dict[str, dict] = {}
    lines.append("")
    lines.append("# --- resolved models, one per role ---")
    lines.append("AI_ROLES=\"" + " ".join(catalog.get("roles", {}).keys()) + "\"")

    for role, spec in catalog.get("roles", {}).items():
        pick = resolve_role(role, spec, usable_gb, fit)
        if pick is None:
            lines.append(f'# ROLE {role}: nothing in the catalog fits {usable_gb} GB.')
            lines.append(f'# {role_var(role)}_MODEL=""')
            continue
        resolved[role] = pick
        key = role_var(role)
        lines.append(f'{key}_MODEL="{pick["model"]}"')
        lines.append(f'{key}_VRAM_GB="{pick["vram_gb"]}"')
        lines.append(f'{key}_MARGIN="{pick["margin"]}"')
        lines.append(f'{key}_NOTES="{pick.get("notes", "")}"')
        # Whether the resolved model can think at all. Published next to the
        # model because that is what it is a property of: whether thinking is
        # POSSIBLE is decided by the resolver, while whether an agent WANTS it
        # is AGENT_THINK in agent.conf. The two are different questions and
        # only the first one changes with the card.
        #
        # Empty means the catalog does not say, which is the honest state for a
        # model whose capability has not been confirmed against a running
        # Ollama. The harness treats empty as "cannot think" - see
        # aiorg_effective_think - because the two mistakes are not symmetric.
        thinks = pick.get("thinks")
        lines.append(f'{key}_THINKS="{"" if thinks is None else str(thinks).lower()}"')

    # A single default model for scripts and ad-hoc use: prefer the reasoning
    # model, fall back to whatever is biggest.
    if "reasoning" in resolved:
        default_model = resolved["reasoning"]["model"]
    elif resolved:
        default_model = next(iter(resolved.values()))["model"]
    else:
        default_model = ""
    lines.append("")
    lines.append("# --- convenience ---")
    lines.append(f'AI_DEFAULT_MODEL="{default_model}"')
    lines.append(f'AI_CODING_MODEL="{resolved.get("coding", {}).get("model", "")}"')

    emb = resolved.get("embedding", {})
    lines.append(f'AI_EMBED_MODEL="{emb.get("model", "")}"')

    emb_dim = {
        "nomic-embed-text": 1376,
        "mxbai-embed-large": 1024,
    }.get(emb.get("model", ""), 1024)
    lines.append(f'AI_EMBED_DIM="{emb_dim}"')

    vis = resolved.get("vision", {})
    lines.append(f'AI_VISION_MODEL="{vis.get("model", "")}"')

    # Remote free tiers, only if a key is actually present in the environment.
    lines.append("")
    lines.append("# --- remote free tiers (only set if a key is exported) ---")
    allow_remote = os.environ.get("AI_ALLOW_REMOTE", "").lower() in ("1", "true", "yes")
    for name, cfg in catalog.get("remote", {}).items():
        if name.startswith("_"):
            continue
        env_key = cfg["env"]
        if allow_remote and os.environ.get(env_key):
            suffix = name.replace("-", "_").upper()
            lines.append(f'AI_REMOTE_{suffix}_ENABLED="true"')
            lines.append(f'AI_REMOTE_{suffix}_BASE="{cfg["base_url"]}"')
            lines.append(f'AI_REMOTE_{suffix}_MODEL="{cfg["model"]}"')
        else:
            suffix = name.replace("-", "_").upper()
            lines.append(f'AI_REMOTE_{suffix}_ENABLED="false"')

    OUT.write_text("\n".join(lines) + "\n")

    # Human-readable report.
    print()
    print(f"  Resolved models for {usable_gb} GB usable VRAM")
    print("  " + "-" * 72)
    print(f"  {'ROLE':<14} {'MODEL':<26} {'NEEDS':>7}  {'FIT':<13}")
    print("  " + "-" * 72)
    for role, pick in resolved.items():
        print(f"  {role:<14} {pick['model']:<26} {pick['vram_gb']:>6}G  {pick['margin']:<13}")
    print("  " + "-" * 72)
    print(f"  default: {default_model}")
    print()

    if cpu_only:
        print("  NOTE: no GPU was detected, so a small model was chosen to keep")
        print("        the system usable. Re-run './bootstrap.sh detect' on the")
        print("        machine that has the graphics card.\n")

    if not allow_remote:
        print("  Remote free tiers are OFF (AI_ALLOW_REMOTE not set).")
        print("  That keeps every prompt on this machine. Set AI_ALLOW_REMOTE=true")
        print("  and export GEMINI_API_KEY to let the CTO/CEO roles use Google's")
        print("  free tier - much better judgement, but your prompts leave the box.")
        print()

    tight = [r for r, p in resolved.items() if p["margin"] == "tight"]
    if tight:
        print(f"  Tight fits (little room for long context): {', '.join(tight)}")
        print(f"  If a task dies with out-of-memory, either lower AI_CONTEXT_OVERRIDE")
        print(f"  or swap that role to the next candidate down in config/models.json.")
        print()

    print("  Written to config/models.env")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
