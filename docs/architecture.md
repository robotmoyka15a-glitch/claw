# claw architecture

## Big picture

```
┌─────────────────────────────── browser ────────────────────────────────┐
│                                                                        │
│   React + Pixi.js                                                      │
│   ┌──────────────────────────────┐   ┌──────────────────────────────┐  │
│   │  Isometric room (Pixi)       │   │  Floating panels (React)     │  │
│   │  • desks, chairs, agents     │◀──▶  • Terminal (xterm.js)       │  │
│   │  • click agent → open panel  │   │  • Process list, charts      │  │
│   │  • hover → tooltip           │   │  • VK feed, Agent config     │  │
│   └──────────────────────────────┘   └──────────────────────────────┘  │
│              ▲                                      ▲                  │
│              └──────────── WebSocket / REST ────────┘                  │
└────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────── localhost ──────────────────────────────────┐
│   FastAPI  (uvicorn @ 127.0.0.1:8765)                                  │
│                                                                        │
│   api/        REST endpoints                                           │
│   services/   processes(psutil) · terminal(pywinpty) · system · vk     │
│   llm/        Ollama · Qwen-local (OpenAI-compat) · Qwen-cloud         │
│   agents/     base · manager · presets  (SQLite for persistence)       │
│   core/       config · ws_manager                                      │
└────────────────────────────────────────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
     Windows OS          Ollama @ 11434       Qwen cloud (DashScope)
     (processes,         or Qwen local        or OpenRouter
      PTY, filesystem)   OpenAI-compat        compatible
```

## Agents model

Each agent is a runtime object with:
- `id`, `name`, `role` (preset key), `seat` (position in the room),
- `llm` binding: provider (`ollama` | `qwen_local` | `qwen_cloud`) + model,
- `system_prompt`, `memory` (last N turns kept in SQLite),
- `tools`: list of callable service handles (`processes.list`,
  `system.stats`, `vk.friends_online`, `terminal.exec`, ...).

Frontend renders them as seated sprites. Clicking opens the **AgentPanel**
which has three tabs: **Chat**, **Config**, **Live view** (what the agent
is currently observing).

## WebSocket channels

| path                 | payload                                     |
|----------------------|---------------------------------------------|
| `/ws/system`         | `{cpu, ram, disk, net}` every second        |
| `/ws/processes`      | process deltas (added/removed/top-CPU)      |
| `/ws/terminal/{id}`  | bidirectional PTY stream                    |
| `/ws/agents/{id}`    | agent state changes + streamed LLM tokens   |

## Security model

- Backend binds to `127.0.0.1` only.
- VK and LLM tokens are read from `backend/.env` (or a local SQLite settings
  table), never sent to the frontend in plaintext.
- Terminal spawns with the current user privileges; no elevation.
