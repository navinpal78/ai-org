# Project Registry

Projects are registered here when work moves from a request into sustained delivery.
Keep entries short and true; the detail lives in the project workspace.

---

## PIN-17 — Personal Assistant (chat first, voice/visual later) ✅ COMPLETE

- **Owner:** board (local-board)  
- **Accountable:** Sarpanch (CEO)
- **Workspace:** `/home/baba/AI/organisation/projects/PIN-17-personal-assistant/`
- **Status:** ✅ **COMPLETE** — Chat running at http://192.168.1.30:7860
  - Persona: submissive lover + tech expert + stock trader + sexual researcher  
  - Loves learning new positions/kinks, reads/researches materials together with owner first
  - Shares findings like horny tutor—teaching while remaining obedient guide
- **Scope now:** text chat only. Voice and visual explicitly deferred until owner is satisfied.
- **Stack:** local Ollama (`dolphin3:8b` for chat), stdlib Python server, browser/terminal UI on
  `http://192.168.1.30:7860` / `http://100.100.168.107:7860`. No cloud, no marginal cost.
- **Services:** `ollama-rani.service` (`:11434`, her models) + `rani-chat.service` (`:7860`),
  both user units enabled at boot. Agent stack keeps its own Ollama on `:41825`.
- **Fixed 31 Oct:** chat outage (`Connection refused`) — app pointed at a dead port. Endpoint
  probing + cross-daemon GPU eviction added; verified by chat round trips.
- **Tone (31 Oct):** normal conversation by default, 1–3 short sentences; flirty/naughty only
  when the owner flirts. Reply cap + stop tokens prevent essays and lists.
- **Honesty (2 Nov):** she has no email, browser, phone, files or trades, and no live prices.
  A fabricated "email sent" was traced to the model, not to any code. Capability rules added to
  the persona and to every request; verified she now refuses honestly.
- **Status (2 Nov):** **PARKED by owner** — `rani-chat` and `ollama-rani` stopped and disabled,
  GPU fully released to the agent stack. Data preserved. Reactivate with `rani` or
  `systemctl --user start rani-chat.service`.
- **Shared resource:** one RTX 3060 (12 GB). The assistant and the agent stack take turns;
  see `app/gpu.py` (`assistant` / `agents` / `status`) and `PIN17_IDLE_YIELD`.
- **Known risk:** a leaked `llama-server` process can hold several GB of VRAM with no API
  handle on it. Clearing it needs root.
- **Disposition recorded via workspace registries** (API intentionally SUI-only per design)
- **Documentation:** `.PAPERCLIP_COMPLETE.txt` records full state and disposition

---

Future projects should contain, where appropriate:

- objective;
- requirements;
- architecture;
- research;
- decisions;
- implementation;
- testing;
- risks;
- approvals;
- outputs;
- handover information.
