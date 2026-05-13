<div align="center">

<br/>

```
 ██████╗██╗      █████╗ ██╗    ██╗
██╔════╝██║     ██╔══██╗██║    ██║
██║     ██║     ███████║██║ █╗ ██║
██║     ██║     ██╔══██║██║███╗██║
╚██████╗███████╗██║  ██║╚███╔███╔╝
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
```

### Control Local Agents Workspace

*Твои ИИ-агенты живут в изометрической комнате и работают сами*

<br/>

[![Build](https://github.com/robotmoyka15a-glitch/claw/actions/workflows/release.yml/badge.svg)](https://github.com/robotmoyka15a-glitch/claw/actions/workflows/release.yml)&nbsp;
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)&nbsp;
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)&nbsp;
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)&nbsp;
[![License](https://img.shields.io/badge/License-MIT-F5B301)](LICENSE)

<br/>

**[⬇️ Скачать claw.exe](https://github.com/robotmoyka15a-glitch/claw/releases/latest)** &nbsp;·&nbsp;
**[📖 Документация](#быстрый-старт)** &nbsp;·&nbsp;
**[🐛 Сообщить о проблеме](https://github.com/robotmoyka15a-glitch/claw/issues)**

<br/>

</div>

---

<div align="center">

## Что такое claw?

</div>

**claw** — это личный рабочий стол, где ИИ-агенты сидят за столами в изометрической комнате и выполняют задачи вместо тебя. Они следят за системой, читают твои соцсети, управляют музыкой и выполняют команды в терминале — используя твои локальные языковые модели (Ollama / Qwen).

Всё работает **локально на твоём компьютере**. Никаких облаков, никакой телеметрии.

<br/>

---

<div align="center">

## ✨ Возможности

</div>

<table>
<tr>
<td width="50%">

### 🏠 Изометрическая комната
Агенты сидят за столами в 2.5D пространстве (Pixi.js). Лампы мигают когда агент думает, пузырьки показывают что он делает. Живая CPU-диаграмма на стене. Плавающие частицы пыли. Ковёр, полки с книгами, растения.

</td>
<td width="50%">

### 🤖 Автономные агенты
Агенты работают без тебя по расписанию или событиям. CPU вырос выше 85%? → агент `Sys` просыпается и находит причину. Пришло Telegram-сообщение? → агент `Vika` читает и отвечает. Всё через LLM tool-calling.

</td>
</tr>
<tr>
<td width="50%">

### 🧠 ModelRouter
Умный маршрутизатор моделей. Автоматически выбирает лучший провайдер под задачу — Ollama, Qwen local или Qwen cloud. Если провайдер недоступен — переключается на следующий в цепочке.

</td>
<td width="50%">

### 🔧 24 инструмента
Каждый агент может вызывать инструменты: смотреть процессы, убивать их, читать ленту ВК, ставить лайки, писать сообщения, управлять Spotify, выполнять shell-команды с таймаутом.

</td>
</tr>
<tr>
<td width="50%">

### 💬 Telegram интеграция
Агент получает сообщения через long-poll или Webhook (ngrok/cloudflare). Реагирует мгновенно — отвечает, пересылает, анализирует. Настраивается триггер прямо в UI.

</td>
<td width="50%">

### 🔒 Безопасность
CSRF-токен на каждый запрос. Опциональное шифрование `.env` мастер-паролем. Маскировка токенов в логах. Rate limiter. Всё работает на `127.0.0.1` — внешний трафик исключён.

</td>
</tr>
</table>

<br/>

---

<div align="center">

## 🤖 Агенты в комнате

</div>

| Агент | Роль | Инструменты |
|---|---|---|
| 🟡 **Chief** | Главный — координирует остальных | `agents.delegate` · `system.snapshot` · `notify.toast` |
| 🟢 **Sys** | Сисадмин Windows | `processes.list/detail/kill` · `system.snapshot` · `terminal.exec` |
| 🔵 **Vika** | Соцсети | `vk.*` · `telegram.get_updates` · `discord.read` |
| 🟣 **Shell** | Терминал | `terminal.exec` |
| 🩷 **Lex** | Исследователь | без инструментов (чат и анализ) |

<br/>

---

<div align="center">

## ⚡ Быстрый старт

</div>

### Вариант 1 — Скачать готовый EXE (рекомендуется)

```
1. Перейди на страницу Releases
2. Скачай claw.exe
3. Запусти — браузер откроется автоматически
4. Открой ⚙️ Настройки и вставь токены
```

> **[→ Скачать последнюю версию](https://github.com/robotmoyka15a-glitch/claw/releases/latest)**

---

### Вариант 2 — Из исходников

```powershell
git clone https://github.com/robotmoyka15a-glitch/claw.git
cd claw
copy backend\.env.example backend\.env
# Открой backend\.env и вставь токены
run.bat
```

Откроется:
- `http://127.0.0.1:5173` — фронтенд (dev-режим)
- `http://127.0.0.1:8765` — backend API

---

### Вариант 3 — Собрать EXE

```powershell
git clone https://github.com/robotmoyka15a-glitch/claw.git
cd claw
build_exe.bat    # ~3-5 минут → backend\dist\claw.exe
```

<br/>

---

<div align="center">

## 🔌 Поддерживаемые сервисы

</div>

<div align="center">

| Сервис | Что умеет |
|---|---|
| 🤖 **Ollama** | Любые локальные модели: Qwen 2.5, LLaMA 3.1, Mistral... |
| ☁️ **Qwen Cloud** | DashScope API, qwen-plus/max/long (1M контекст) |
| 💙 **ВКонтакте** | Лента, друзья, поиск, лайки, сообщения |
| ✈️ **Telegram** | Long-poll + Webhook, автоответ, триггеры |
| 🎮 **Discord** | Чтение и отправка сообщений |
| 🎯 **Steam** | Профиль, библиотека, статистика |
| 🎵 **Spotify** | Now Playing с прогресс-баром, управление |
| 🔔 **Windows** | Toast-уведомления, системный трей |

</div>

<br/>

---

<div align="center">

## 🏗 Архитектура

</div>

```
┌─────────────────────────────────────────────────────────────┐
│                    Браузер (React + Pixi.js)                 │
│                                                             │
│  ┌──────────────────────────┐  ┌──────────────────────────┐ │
│  │   Изометрическая комната  │  │  Floating Panels (16шт)  │ │
│  │   (Pixi.js WebGL)        │  │  Terminal · Processes    │ │
│  │   агенты за столами       │  │  VK · Telegram · Spotify │ │
│  │   анимации статуса        │  │  Autonomy · Models · ... │ │
│  └──────────────────────────┘  └──────────────────────────┘ │
│              ▲  WebSocket + REST                             │
└──────────────┼──────────────────────────────────────────────┘
               │
┌──────────────┼──────────────────────────────────────────────┐
│         FastAPI @ 127.0.0.1:8765  (70 маршрутов)            │
│                                                             │
│  Agents ──▶ ModelRouter ──▶ Ollama / Qwen local / Cloud     │
│     │            │                                          │
│  Tools (24)   Autonomy                                      │
│  ├ system     ├ EventBus (cpu_high, tg_message, ...)        │
│  ├ processes  ├ Scheduler (interval / cron / event)         │
│  ├ vk         └ Plan-and-Execute loop                       │
│  ├ telegram                                                  │
│  ├ discord    Connectors: Telegram long-poll / Webhook       │
│  ├ steam      Security: CSRF · rate limit · enc .env         │
│  └ spotify    DB: SQLite (agents, tasks, history)           │
└─────────────────────────────────────────────────────────────┘
```

<br/>

---

<div align="center">

## 📦 Что внутри EXE

</div>

Когда запускаешь `claw.exe`:

1. **Создаётся** `%LOCALAPPDATA%\claw\.env` с шаблоном токенов
2. **Запускается** FastAPI backend на `127.0.0.1:8765`
3. **Открывается** браузер автоматически
4. **Появляется** иконка в системном трее (правый клик → открыть / выход)

Один файл содержит:
- Python runtime + все зависимости
- Собранный React фронтенд
- SQLite для хранения агентов и истории

> **Требования:** Windows 10/11 x64 · 4 ГБ RAM
> Ollama нужен для локальных LLM. Без него — работает с Qwen cloud.

<br/>

---

<div align="center">

## 🛠 Стек технологий

</div>

<div align="center">

**Backend**

![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-000000?style=flat)
![psutil](https://img.shields.io/badge/psutil-FF6B35?style=flat)
![pywinpty](https://img.shields.io/badge/pywinpty-0078D7?style=flat)

**Frontend**

![React](https://img.shields.io/badge/React_18-61DAFB?style=flat&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![Pixi.js](https://img.shields.io/badge/Pixi.js-E72264?style=flat)
![xterm.js](https://img.shields.io/badge/xterm.js-000000?style=flat)
![Tailwind](https://img.shields.io/badge/Tailwind-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)

**LLM**

![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat)
![Qwen](https://img.shields.io/badge/Qwen-FF6A00?style=flat)
![OpenAI Compatible](https://img.shields.io/badge/OpenAI--compat-412991?style=flat&logo=openai&logoColor=white)

</div>

<br/>

---

<div align="center">

## 📄 Лицензия

**MIT** — используй свободно, без гарантий.

<br/>

---

*Сделан как персональный рабочий стол для тех, кто хочет чтобы ИИ работал для них — а не наоборот*

</div>
