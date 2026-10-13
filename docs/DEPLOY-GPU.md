# Deploying on a GPU box

This is the runbook for the machine with the graphics card. It is written for
the RTX 3060 12GB, which is the card this project is being set up on, but the
same steps apply to any card in the safe band (16GB, 24GB, 80GB).

Read `docs/00-START-HERE.md` first if you have never run the project. Read
`AGENTS.md` before editing `config/models.json`.

---

## 1. The 3060 12GB is in the safe band

The org's central safety argument is that the auditor (`security-engineer`), the
audited party (`cto`) and the arbitrator (`ceo`) must not run identical weights.
"Safe band" means the resolver cannot converge their models at your card size.

Verified by running the real resolver (`tools/resolve_models.py`) against a
simulated 12GB profile. The two columns below are the whole reason this card is
fine, and they differ only because of one decision - **see section 2**:

| Role | Headless (12.0 GB usable) | With a desktop (10.8 GB usable) |
|---|---|---|
| coding | `qwen2.5-coder:14b` | `qwen2.5-coder:7b` |
| reasoning (CTO) | `phi4:14b` | `gemma3:12b` |
| adversarial-review (security) | `qwen3:14b` | `qwen3:8b` |
| adjudication (CEO) | `deepseek-r1:14b` | `deepseek-r1:8b` |
| evidence-review (research officer) | `aya-expanse:8b` | `aya-expanse:8b` |
| fast / translation | `qwen3:14b` | `qwen3:8b` |
| teacher | `qwen3:14b` | **nothing fits** |
| narrative (storyteller) | `qwen3:14b` | **nothing fits** |
| personal | `orca2:13b` | `orca2:13b` |
| vision | `qwen3-vl:8b` | `qwen3-vl:4b` |

In both columns the auditor and the CTO are different families (`qwen3` vs
`phi4`/`gemma3`), and the CEO is a third (`deepseek`), so the separation holds.
The important difference is at the bottom: **with a desktop running, `teacher`
and `storyteller` cannot run at all**, because their roles bottom out at
`qwen3:14b` (10GB) and there is only 10.8GB of usable VRAM.

**So run the GPU box headless.** It is worth 10% of the card and two agents.

---

## 2. Why headless changes the answer

`lib/hwdetect.py` reserves 10% of VRAM for a desktop/compositor when a display
server is running, because those pixels have to live somewhere:

```
AI_HEADLESS="true"   -> usable = total       -> 12.0 GB -> tier vram_12 -> context 16384
AI_HEADLESS="false"  -> usable = total * 0.90 -> 10.8 GB -> tier vram_8  -> context 8192
```

That is not just a bigger number - it moves `qwen3:14b` (10GB) across the
`tight_max` line. Headless it fits (10 / 12 = 0.83); with a desktop it does not
(10 / 10.8 = 0.93 > 0.92). `teacher` and `narrative` have nothing smaller, so
they resolve to nothing.

"Headless" here has a precise meaning: **no display server is running**. It is
detected from the `DISPLAY` / `WAYLAND_DISPLAY` environment variables, which are
unset on a machine that boots to a text console and are set in any desktop
session. Two consequences worth knowing:

- Booting to a text console (`multi-user.target`) is the real fix. Merely
  SSH-ing into a machine that still runs a desktop is *reported* as headless
  (SSH sessions have no `DISPLAY`) but the desktop is still using the VRAM, so
  the reported 12.0GB is optimistic and a 10GB model may still fail to load.
- Run `./bootstrap.sh detect` **over SSH or from the console**, never from a
  terminal inside a desktop session, or it will correctly reserve the 10% and
  you will get the right-hand column.

---

## 3. Setting up a headless machine

If the GPU box is a fresh install, the cleanest path is a **server OS with no
desktop**, which is headless by construction. Steps below are for Ubuntu Server
24.04 LTS; adapt for your distro.

### 3.1 Install the OS without a desktop

Install Ubuntu Server (or Debian minimal, or any server install). Do not install
a desktop environment. If a desktop got installed anyway, turn it off in 3.3.

### 3.2 Base packages and the NVIDIA driver

```bash
sudo apt update
sudo apt install -y git python3 curl openssh-server
# Docker is only needed for the optional browser UI (30-openwebui.sh):
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"     # log out/in for this to take effect

# NVIDIA driver, from the distro repo (survives kernel updates):
sudo ubuntu-drivers install        # or: sudo apt install nvidia-driver-550
sudo reboot
nvidia-smi                          # must show the RTX 3060 and a driver version
```

Do **not** install the driver from NVIDIA's `.run` installer - it breaks on
kernel upgrades, which a home-lab box will get.

### 3.3 Confirm it boots to a text console

```bash
systemctl get-default
```

It must say `multi-user.target`. If it says `graphical.target`, a desktop is
running; switch it off and reboot:

```bash
sudo systemctl set-default multi-user.target
sudo systemctl disable --now gdm3        # or sddm / lightdm, whichever is unit
sudo reboot
```

SSH access is unaffected - SSH is a service, not a display.

### 3.4 A stable address

Give the box a fixed address so the agents on other machines can find it: set a
DHCP reservation in your router for its MAC address, or configure a static IP in
`netplan`. Then reach it by that address.

```bash
# from another machine on the LAN:
ssh youruser@192.168.1.50
```

### 3.5 Check VRAM is fully available

Over SSH, after installing the driver:

```bash
nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits
```

A 3060 reports `12288` (MiB). After `detect` (section 4) the project should print
`12.0 GB usable (headless, full allocation)`. If it prints the 10% version,
something is still running a display server - go back to 3.3.

Nothing else should be running on the box. Headless means the model server gets
the whole card, and that is the point.

---

## 4. Deploy the project

The repository is **private** (`github.com/navinpal78/ai-org`), so clone with
authentication - either `gh auth login`, or a personal access token over HTTPS.

```bash
gh auth login
git clone https://github.com/navinpal78/ai-org.git
cd ai-org
chmod +x bootstrap.sh scripts/*.sh tools/*.sh
```

Then, in order. `detect` is always first: it writes `config/profile.env` and
`config/models.env`, which are generated per machine and deliberately not in
Git, so a fresh clone has neither until this runs.

```bash
./bootstrap.sh detect       # confirm: "12.0 GB usable (headless, full allocation)"
sudo ./bootstrap.sh ollama  # installs + tunes the model server (needs sudo, local box)
./bootstrap.sh models       # downloads only what fits the 3060
./bootstrap.sh ui           # optional browser UI (Docker; not needed for agents)
./bootstrap.sh verify       # THE test - see section 5
```

`./bootstrap.sh all` runs all five in order if you prefer.

### After any hardware change

One command re-resolves everything; nothing is hardcoded:

```bash
./bootstrap.sh detect && sudo ./scripts/10-ollama.sh && ./bootstrap.sh models
```

---

## 5. Prove it is actually on the GPU

`./bootstrap.sh verify` runs a real generation and reports the speed and the
offload percentage. The line that matters:

```
[ ok ] running at 100% GPU
```

**If it does not say 100% GPU, stop.** A silent CPU fallback is the single most
common way an evening is wasted: everything looks fine, it is just ~50x slower,
and you end up blaming your prompt. The usual fix:

```bash
sudo usermod -aG video,render ollama
sudo systemctl restart ollama
```

`10-ollama.sh` applies that already when run as root; `verify` is what proves it
took.

---

## 6. Validate the agents, then run them

```bash
./bootstrap.sh check        # no GPU needed; validates the agents/ tree
```

Expect **551 checks passed and exactly 1 error.** That one error is the 28-48GB
auditor monoculture - a property of the *catalog*, checked at every tier, so it
shows on your 3060 too even though the 12GB band itself is safe. It is
deliberate and documented in `AGENTS.md` under "What is still red". **If the
error count is ever anything other than 1, stop and read - that is a new
problem.**

Then measure the agents for real. This is the step the whole project was waiting
for, and the one no CPU baseline could stand in for:

```bash
./tools/test-agent.sh personal            # the one agent nobody has scored
./tools/test-agent.sh coder --verbose     # read a passing case before a failing one
./tools/test-agent.sh network-engineer
# ... then the rest; `./bootstrap.sh audit` records every run
```

Read `docs/00-START-HERE.md` section 6 for the loop (edit `SOUL.md` -> test ->
read the failure -> fix). A 0/1 on a correct reply is a broken **test**, not a
bad prompt, at least as often.

Also settle the open hardware question now that the card exists:

```bash
./tools/check-models.sh            # confirms thinking capability of models on disk
./tools/check-models.sh --online   # re-verifies every catalog tag exists (expect 0 phantoms)
```

---

## 7. Using it from other machines

The model server listens on the LAN, so the agents (or the browser UI) can live
on any other PC. Only the model server needs the GPU.

- **Browser UI:** `http://<gpu-box-ip>:3000` from any machine. Create the admin
  account immediately - the first account created is the administrator.
- **Agents on another box:** that box does not run Ollama. Point it at the GPU
  box with one variable:

  ```bash
  AI_OLLAMA_HOST=192.168.1.50 ./bootstrap.sh detect
  ```

  `10-ollama.sh` then detects the server is remote and does nothing locally,
  which is correct - there is nothing to install where there is no GPU.

---

## 8. Security

`0.0.0.0` means every device on your network can reach the model server
(port 11434) and the UI (port 3000), including a phone on guest WiFi. There is
no authentication on the model port. This is usually fine at home, but read
`docs/FIREWALL.md` and pick a level before you put anything real on it - Level 2
(restrict to your LAN subnet) is the setting for almost everyone.

---

## 9. Watch-outs, in one place

- **Headless is the decision.** Boot to a text console and run `detect` over
  SSH. It is worth two agents and a larger coder.
- **`verify` must say 100% GPU.** Nothing else in the run is trustworthy until
  it does.
- **1 error in `check` is expected; 2 is not.** The one is the catalog's 28-48GB
  band, not your card.
- **Many models are `tight` at 12GB.** After `detect`, read the "Tight fits"
  list. If a task dies out-of-memory, lower `AI_CONTEXT_OVERRIDE` (default
  `16384`) or drop that role one rung in `config/models.json`.
- **RAM:** 64GB is recommended so a model that nearly fills VRAM can spill into
  RAM instead of failing. Under 64GB still works, just less forgiving.
- **Do not tune prompts against a small model** to "make the score better" - the
  whole method assumes the real weights. And a closed-book score for a research
  agent is not a research score (`AGENTS.md` rule 17).
- **`artist` and `director` still cannot run**, even with the card: there is no
  image/video generation runtime in the project yet. That is a separate owner
  decision (`AGENTS.md`, "What to build next"), not a setup step.
- **Never edit `config/profile.env` or `config/models.env` by hand.** They are
  generated. Re-run `./bootstrap.sh detect`.
