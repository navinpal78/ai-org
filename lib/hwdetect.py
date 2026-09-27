#!/usr/bin/env python3
"""
hwdetect.py - profile the machine, then write the config the rest of the
project reads.

This is the "check the specs first" step. It is the ONLY place hardware is
inspected. Everything downstream (model choice, context length, parallelism,
creative-work scheduling) reads config/profile.env, which this script writes.

Re-run it after any hardware change. The project adapts; nothing else to edit.

Outputs:
  config/hardware.json  machine-readable, for tools and the resolver
  config/profile.env     shell-sourceable, for every bash script

Standard library only. No pip installs.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
STATE = ROOT / "state"

# Headroom reserved for the desktop / compositor / display server when a GPU
# is driving a monitor. On a headless box (no display server) this is released
# back to the model server.
HEADROOM_RATIO = 0.90


def run(cmd: list[str], timeout: int = 10) -> str:
    """Run a command, return stdout, never raise."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return ""


def read_first(path: str) -> int:
    """Read the first integer out of a sysfs file. 0 if unreadable."""
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------


def detect_nvidia() -> list[dict]:
    if not shutil.which("nvidia-smi"):
        return []
    raw = run([
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    if not raw:
        return []
    gpus = []
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            vram_mb = int(float(parts[2]))
        except ValueError:
            continue
        gpus.append({
            "index": parts[0],
            "name": parts[1],
            "vram_mb": vram_mb,
            "driver": parts[3] if len(parts) > 3 else "",
            "vendor": "nvidia",
        })
    return gpus


def detect_amd() -> list[dict]:
    gpus: list[dict] = []

    # Preferred: rocm-smi
    if shutil.which("rocm-smi"):
        raw = run(["rocm-smi", "--showproductname", "--showmeminfo", "vram"])
        # Parse "GPU[0]: ...  total : 24576 MiB"
        for m in re.finditer(r"GPU\[(\d+)\]", raw):
            idx = m.group(1)
            tail = raw[m.end(): m.end() + 400]
            vm = re.search(r"total\s*:\s*([\d.]+)\s*(MiB|GB)", tail)
            if vm:
                amount, unit = float(vm.group(1)), vm.group(2)
                mb = int(amount * 1024) if unit == "GiB" or unit == "GB" else int(amount)
                gpus.append({
                    "index": idx,
                    "name": "AMD GPU",
                    "vram_mb": mb,
                    "driver": "",
                    "vendor": "amd",
                })

    # Fallback: kernel DRM sysfs
    if not gpus:
        for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
            dev = card / "device"
            if not dev.exists():
                continue
            mb = read_first(str(dev / "mem_info_vram_total")) // (1024 * 1024)
            if mb <= 0:
                continue
            real = dev.resolve()
            gpus.append({
                "index": card.name.replace("card", ""),
                "name": real.name,
                "vram_mb": mb,
                "driver": "",
                "vendor": "amd",
            })
    return gpus


def detect_apple() -> dict | None:
    if platform.system() != "Darwin":
        return None
    raw = run(["sysctl", "-n", "hw.memsize"])
    try:
        total_bytes = int(raw)
    except ValueError:
        return None
    # Apple Silicon shares one memory pool between CPU and GPU. Roughly 75% of
    # it is addressable by the GPU with wired memory, so budget against that.
    return {
        "index": "0",
        "name": "Apple Silicon (unified memory)",
        "vram_mb": int(total_bytes / 1024 / 1024 * 0.75),
        "driver": run(["sw_vers", "-productVersion"]),
        "vendor": "apple",
        "unified_memory": True,
    }


# ---------------------------------------------------------------------------
# System detection
# ---------------------------------------------------------------------------


def detect_ram_mb() -> int:
    total_kb = 0
    if platform.system() == "Linux":
        total_kb = read_first("/proc/meminfo")  # placeholder, replaced below
        try:
            with open("/proc/meminfo") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        total_kb = int(line.split()[1])
                        break
        except OSError:
            total_kb = 0
    elif platform.system() == "Darwin":
        try:
            total_bytes = int(run(["sysctl", "-n", "hw.memsize"]) or 0)
            total_kb = total_bytes // 1024
        except ValueError:
            total_kb = 0
    return total_kb // 1024


def detect_cpu() -> dict:
    model = platform.processor() or ""
    physical = 0
    if shutil.which("lscpu"):
        raw = run(["lscpu"])
        m = re.search(r"^Model name:\s*(.+)$", raw, re.M)
        if m:
            model = m.group(1).strip()
        cores = re.findall(r"^Core\(s\) per socket:\s*(\d+)", raw, re.M)
        sockets = re.findall(r"^Socket\(s\):\s*(\d+)", raw, re.M)
        if cores:
            physical = int(cores[0]) * int(sockets[0]) if sockets else int(cores[0])
    logical = os.cpu_count() or 1
    return {"model": model or "unknown", "physical_cores": physical, "logical": logical}


def detect_disk_free_gb(path: str = "/") -> float:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / 1024**3, 1)
    except OSError:
        return 0.0


def is_headless() -> bool:
    """True when nothing is displaying on this box, so the GPU is free to be
    fully allocated to inference."""
    if platform.system() != "Linux":
        return False
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return False
    return True


def has_command(name: str) -> bool:
    return bool(shutil.which(name))


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_profile() -> dict:
    nvidia = detect_nvidia()
    amd = detect_amd()
    apple = detect_apple()

    gpus: list[dict] = nvidia or amd
    if not gpus and apple:
        gpus = [apple]

    total_vram_mb = sum(g["vram_mb"] for g in gpus)
    headless = is_headless()
    usable_vram_mb = int(total_vram_mb * (1.0 if headless else HEADROOM_RATIO))

    ram_mb = detect_ram_mb()
    cpu = detect_cpu()
    disk_free = detect_disk_free_gb()

    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "cpu": cpu,
        "ram": {
            "total_mb": ram_mb,
            "total_gb": round(ram_mb / 1024, 1),
            "recommended_minimum_gb": 64,
            "ok": ram_mb >= 64 * 1024,
        },
        "gpu": {
            "count": len(gpus),
            "devices": gpus,
            "vendor": gpus[0]["vendor"] if gpus else "none",
            "total_vram_mb": total_vram_mb,
            "total_vram_gb": round(total_vram_mb / 1024, 1),
            "usable_vram_mb": usable_vram_mb,
            "usable_vram_gb": round(usable_vram_mb / 1024, 1),
            "headless": headless,
        },
        "disk": {"free_gb": disk_free, "recommended_minimum_gb": 100},
        "tools": {
            name: has_command(name)
            for name in ["docker", "docker-compose", "ollama", "nvidia-smi", "git", "jq", "curl"]
        },
    }


def tier_for_vram_mb(mb: int) -> str:
    """Must stay in sync with tier_for_vram_mb() in lib/common.sh."""
    if mb < 4000:
        return "cpu"
    gb = mb // 1024
    if gb < 11:
        return "vram_8"
    if gb < 16:
        return "vram_12"
    if gb < 24:
        return "vram_16"
    if gb < 32:
        return "vram_24"
    if gb < 48:
        return "vram_32"
    if gb < 80:
        return "vram_48"
    return "vram_80"


TIER_LABEL = {
    "cpu": "CPU only",
    "vram_8": "6-10 GB VRAM",
    "vram_12": "11-15 GB VRAM",
    "vram_16": "16-23 GB VRAM",
    "vram_24": "24-31 GB VRAM (single card)",
    "vram_32": "32-47 GB VRAM",
    "vram_48": "48-79 GB VRAM (multi-GPU or pro card)",
    "vram_80": "80+ GB VRAM (workstation)",
}

TIER_CONTEXT = {
    "cpu": 8192,
    "vram_8": 8192,
    "vram_12": 16384,
    "vram_16": 16384,
    "vram_24": 32768,
    "vram_32": 49152,
    "vram_48": 65536,
    "vram_80": 98304,
}

TIER_PARALLEL = {
    "cpu": 1, "vram_8": 1, "vram_12": 1, "vram_16": 2,
    "vram_24": 2, "vram_32": 3, "vram_48": 4, "vram_80": 6,
}


def shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\\''") + "'"


def write_profile(hw: dict) -> dict:
    tier = tier_for_vram_mb(hw["gpu"]["usable_vram_mb"])
    ctx = int(os.environ.get("AI_CONTEXT_OVERRIDE") or TIER_CONTEXT[tier])
    par = TIER_PARALLEL[tier]

    CONFIG.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)

    # Embed the tier in hardware.json so downstream tools (the resolver) do
    # not have to re-derive it.
    hw["_tier"] = tier
    hw["_tier_label"] = TIER_LABEL[tier]
    hw["_context"] = ctx
    (CONFIG / "hardware.json").write_text(json.dumps(hw, indent=2) + "\n")

    lines = [
        "# ============================================================",
        "# GENERATED FILE - do not edit by hand.",
        "# Written by lib/hwdetect.py. Re-run:  ./bootstrap.sh detect",
        "# Edit lib/hwdetect.py or config/models.json instead.",
        "# ============================================================",
        "",
        f'AIORG_PROFILE_VERSION="{hw["platform"]["python"]}"',
        f'AI_DETECTED_AT="{run(["date", "-Iseconds"])}"',
        "",
        "# --- platform ---",
        f'AI_PLATFORM="{hw["platform"]["system"]}"',
        f'AI_ARCH="{hw["platform"]["machine"]}"',
        "",
        "# --- cpu ---",
        f'AI_CPU_MODEL={shell_quote(hw["cpu"]["model"])}',
        f'AI_CPU_CORES="{hw["cpu"]["physical_cores"]}"',
        f'AI_CPU_LOGICAL="{hw["cpu"]["logical"]}"',
        "",
        "# --- memory ---",
        f'AI_RAM_MB="{hw["ram"]["total_mb"]}"',
        f'AI_RAM_GB="{hw["ram"]["total_gb"]}"',
        "",
        "# --- gpu ---",
        f'AI_GPU_VENDOR="{hw["gpu"]["vendor"]}"',
        f'AI_GPU_COUNT="{hw["gpu"]["count"]}"',
        f'AI_GPU_NAMES={shell_quote(", ".join(g["name"] for g in hw["gpu"]["devices"]) or "none")}',
        f'AI_VRAM_MB="{hw["gpu"]["total_vram_mb"]}"',
        f'AI_VRAM_GB="{hw["gpu"]["total_vram_gb"]}"',
        f'AI_USABLE_VRAM_MB="{hw["gpu"]["usable_vram_mb"]}"',
        f'AI_USABLE_VRAM_GB="{hw["gpu"]["usable_vram_gb"]}"',
        f'AI_HEADLESS="{str(hw["gpu"]["headless"]).lower()}"',
        "",
        "# --- disk ---",
        f'AI_DISK_FREE_GB="{hw["disk"]["free_gb"]}"',
        "",
        "# --- tier (the single knob everything else keys off) ---",
        f'AI_TIER="{tier}"',
        f'AI_TIER_LABEL={shell_quote(TIER_LABEL[tier])}',
        f'AI_CONTEXT="{ctx}"',
        f'AI_PARALLEL="{par}"',
        "",
        "# --- tools ---",
    ]
    for name, present in hw["tools"].items():
        key = name.upper().replace("-", "_").replace(".", "_")
        lines.append(f'AI_HAS_{key}="{str(present).lower()}"')

    lines += [
        "",
        "# Ollama endpoint. Override by exporting AI_OLLAMA_HOST before",
        "# bootstrap to point clients at a different machine on the LAN.",
        f'AI_OLLAMA_HOST="{os.environ.get("AI_OLLAMA_HOST", "127.0.0.1")}"',
        f'AI_OLLAMA_PORT="{os.environ.get("AI_OLLAMA_PORT", "11434")}"',
        f'AI_OLLAMA_URL="http://${{AI_OLLAMA_HOST}}:${{AI_OLLAMA_PORT}}"',
        "",
    ]
    (CONFIG / "profile.env").write_text("\n".join(lines))
    return {"tier": tier, "context": ctx, "parallel": par}


def print_summary(hw: dict, resolved: dict) -> None:
    g = hw["gpu"]
    ram_ok = "ok" if hw["ram"]["ok"] else "LOW"
    disk_ok = "ok" if hw["disk"]["free_gb"] >= 100 else "LOW"

    print()
    print("  Hardware profile")
    print("  " + "-" * 58)
    print(f"  CPU        {hw['cpu']['model']}")
    print(f"             {hw['cpu']['physical_cores']} physical / "
          f"{hw['cpu']['logical']} logical cores")
    if g["devices"]:
        for dev in g["devices"]:
            print(f"  GPU        {dev['name']}  "
                  f"({dev['vram_mb'] // 1024} GB, {dev['vendor']})")
        alloc = ("headless, full allocation" if g["headless"]
                 else "display attached, 10% reserved for the desktop")
        print(f"  VRAM       {g['total_vram_gb']} GB total, "
              f"{g['usable_vram_gb']} GB usable ({alloc})")
    else:
        print("  GPU        none detected - CPU-only mode")
        print("  VRAM       0 GB. Models will run on the processor instead.")
    print(f"  RAM        {hw['ram']['total_gb']} GB  [{ram_ok}]"
          f"   (64 GB recommended so models can offload instead of failing)")
    print(f"  Disk free  {hw['disk']['free_gb']} GB  [{disk_ok}]   "
          f"(100 GB minimum - models are large)")
    print("  " + "-" * 58)
    print(f"  TIER       {resolved['tier']}  ({resolved['tier_label']})")
    print(f"  Context    {resolved['context']} tokens")
    print(f"  Parallel   {resolved['parallel']} concurrent agent sessions")
    print("  " + "-" * 58)

    missing = [n for n, ok in hw["tools"].items() if not ok]
    if missing:
        print(f"  Missing:   {', '.join(missing)}")
    print()


def main() -> int:
    hw = build_profile()
    resolved = write_profile(hw)
    resolved["tier_label"] = TIER_LABEL[resolved["tier"]]
    print_summary(hw, resolved)

    if hw["gpu"]["count"] == 0:
        print("  NOTE: no GPU detected. A 7-8B model will run, but slowly.")
        print("        Everything still works - just expect agent turns to")
        print("        take tens of seconds. Re-run './bootstrap.sh detect'")
        print("        on the machine with the GPU.\n")
    elif hw["ram"]["total_gb"] < 64:
        print("  NOTE: under 64 GB RAM. Ollama will still work, but a model that")
        print("        nearly fills VRAM will have no room to spill into RAM.\n")

    print("  Profile written to config/profile.env")
    print("  Next:  ./bootstrap.sh all\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
