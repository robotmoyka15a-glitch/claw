# claw — Control Local Agents Workspace

An isometric dashboard for Windows where your local AI agents "live" in a virtual
office. Each agent sits at a desk, works on a specific task (process monitoring,
VK feed, system alerts, terminal assistance) and you configure them visually by
clicking on their workstation.

![architecture](docs/architecture.md)

## Features

- **Isometric room** (Pixi.js, 2.5D flat vector) with desks, chairs, a central
  "boss" agent and side agents on specialized desks.
- **Process & system monitor** — `psutil` powered, real-time over WebSocket.
- **Integrated terminal** — real Windows PTY via `pywinpty`, rendered with
  `xterm.js`.
- **VK (ВКонтакте) integration** — official API via user access token
  (friends online, feed, notifications, profile).
- **LLM agent connectors**:
  - **Ollama** (local, any model you pulled)
  - **Qwen local** (OpenAI-compatible endpoint, e.g. vLLM / LM Studio / Qwen.cpp)
  - **Qwen cloud** (DashScope / OpenRouter / compatible)
- **Agent manager** — presets (Boss, SysAdmin, VK-watcher, Terminal-helper,
  Researcher), custom system prompts, per-agent memory and tool bindings.

## Quick start (Windows)

```powershell
git clone https://github.com/robotmoyka15a-glitch/claw.git
cd claw
copy backend\.env.example backend\.env
# edit backend\.env — put your VK token and LLM endpoints
run.bat
```

The script creates a venv, installs backend deps, installs frontend deps,
launches the FastAPI server on `http://127.0.0.1:8765` and the Vite dev server
on `http://127.0.0.1:5173`. Open the Vite URL in your browser.

## Project layout

```
claw/
├── backend/          FastAPI + psutil + pywinpty + LLM connectors
├── frontend/         React + Vite + Pixi.js + xterm.js + Tailwind
├── docs/             design notes
└── run.bat, run.sh   launch helpers
```

See `docs/architecture.md` for the full design.

## Security

- No telemetry. Everything runs locally.
- Your VK token and API keys live only in `backend/.env` on your machine.
- The backend binds to `127.0.0.1` by default — do **not** expose it to the
  public internet without adding auth.
