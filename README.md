# claw — Control Local Agents Workspace

[![Build & Release EXE](https://github.com/robotmoyka15a-glitch/claw/actions/workflows/release.yml/badge.svg)](https://github.com/robotmoyka15a-glitch/claw/actions/workflows/release.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Локальный рабочий стол для управления ИИ-агентами на Windows. Агенты «живут»
в изометрической комнате и могут мониторить систему, писать в Telegram/Discord/ВКонтакте,
управлять Spotify и выполнять команды в терминале через LLM **tool-calling**.

---

## Быстрый старт (Windows)

### Вариант A — один EXE-файл

1. Скачай последний `claw.exe` со страницы [**Releases**](https://github.com/robotmoyka15a-glitch/claw/releases)
2. Запусти — браузер откроется автоматически на `http://127.0.0.1:8765`
3. При первом запуске создаётся `%LOCALAPPDATA%\claw\.env` с шаблоном токенов
4. Открой **⚙️ Настройки** в дашборде и вставь свои токены

### Вариант B — из исходников

```powershell
git clone https://github.com/robotmoyka15a-glitch/claw.git
cd claw
run.bat          # создаёт venv, ставит зависимости, поднимает оба сервера
# Frontend → http://127.0.0.1:5173
# Backend  → http://127.0.0.1:8765
```

### Вариант C — собрать EXE самому

```powershell
git clone https://github.com/robotmoyka15a-glitch/claw.git
cd claw
build_exe.bat   # собирает frontend + PyInstaller → backend\dist\claw.exe
```

---

## Что умеет

| Функция | Детали |
|---|---|
| 🏠 Изометрическая комната | Pixi.js, 2.5D, агенты за столами с анимацией |
| 🤖 ИИ-агенты | 5 пресетов, LLM tool-calling, делегирование задач |
| 📊 Мониторинг | CPU / RAM / Disk / Network, список процессов (поиск, сортировка, детали) |
| 💻 Терминал | Встроенный PTY (`pywinpty`), полная поддержка ANSI / цветов |
| 💙 ВКонтакте | Лента, друзья онлайн, поиск постов, лайки, отправка сообщений |
| ✈️ Telegram | Входящие обновления, отправка сообщений через бота |
| 🎮 Discord | Чтение канала, отправка сообщений |
| 🎯 Steam | Профиль, недавние игры, библиотека |
| 🎵 Spotify | Now Playing с прогресс-баром, управление воспроизведением |
| 🔔 Уведомления | Windows tray + UI-тосты (агенты вызывают `notify.toast`) |
| ⚙️ Настройки в UI | Токены вводятся прямо в браузере, без правки файлов |

---

## LLM провайдеры

| Провайдер | Настройка | Модели |
|---|---|---|
| **Ollama** (локально) | `OLLAMA_BASE_URL=http://127.0.0.1:11434` | `qwen2.5:7b`, `llama3.1`, любые |
| **Qwen local** (OpenAI-compatible) | `QWEN_LOCAL_BASE_URL=http://127.0.0.1:8000/v1` | LM Studio, vLLM, llama.cpp |
| **Qwen cloud** (DashScope) | `QWEN_CLOUD_API_KEY=sk-...` | `qwen-plus`, `qwen-max` |

---

## Коннекторы — как получить токены

### ВКонтакте

1. Создай приложение на [vk.com/apps](https://vk.com/apps) (тип: «Standalone»)
2. Открой в браузере (подставь свой App ID):
```
https://oauth.vk.com/authorize?client_id=ВАШ_APP_ID&display=page
  &redirect_uri=https://oauth.vk.com/blank.html
  &scope=friends,wall,messages,offline
  &response_type=token&v=5.199
```
3. Войди и скопируй `access_token=...` из URL страницы после редиректа

> Scope `messages` нужен для отправки личных сообщений.

### Telegram

1. Напиши [@BotFather](https://t.me/BotFather) → `/newbot`
2. Скопируй токен вида `123456789:AAA...`
3. Для получения Chat ID: напиши боту любое сообщение, открой
   `https://api.telegram.org/botТОКЕН/getUpdates`, найди `"chat":{"id":...}`

### Discord

1. Открой [discord.com/developers/applications](https://discord.com/developers/applications) → New Application → Bot
2. Скопируй **Token** с вкладки Bot
3. Скопируй **Channel ID** (правая кнопка на канале → «Копировать ID», нужен Developer Mode)

### Steam

1. Получи ключ на [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
2. Найди свой SteamID64 через [steamid.io](https://steamid.io) (17-значное число, начинается с 7656...)

### Spotify

1. Зайди на [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → Create App
2. Добавь Redirect URI: `http://localhost:8888/callback`
3. Открой в браузере (подставь Client ID):
```
https://accounts.spotify.com/authorize?client_id=ВАШ_CLIENT_ID
  &response_type=code&redirect_uri=http://localhost:8888/callback
  &scope=user-read-currently-playing%20user-read-playback-state%20user-modify-playback-state
```
4. После входа скопируй `?code=...` из URL
5. Обменяй code на refresh_token через POST:
```bash
curl -X POST https://accounts.spotify.com/api/token \
  -H "Authorization: Basic BASE64(client_id:client_secret)" \
  -d "grant_type=authorization_code&code=КОД&redirect_uri=http://localhost:8888/callback"
```
6. Вставь `refresh_token` из ответа в настройки claw

---

## Структура проекта

```
claw/
├── backend/              Python FastAPI
│   ├── app/
│   │   ├── agents/       агенты, менеджер, пресеты
│   │   ├── api/          REST + WebSocket эндпоинты
│   │   ├── connectors/   Telegram, Discord, Steam, Spotify, Windows notify
│   │   ├── core/         config, db, ws_manager
│   │   ├── llm/          Ollama, OpenAI-compat, registry
│   │   ├── services/     psutil, terminal PTY, VK
│   │   └── tools/        tool-calling framework, 24 встроенных инструмента
│   ├── claw.spec         PyInstaller spec для сборки EXE
│   ├── launcher.py       точка входа EXE (tray + browser open)
│   └── requirements.txt
├── frontend/             React + Vite + TypeScript
│   └── src/
│       ├── panels/       Terminal, ProcessList, VKFeed, Spotify, Settings, About…
│       └── scene/        Room (Pixi.js изометрия)
├── build_exe.bat         сборка в один EXE
└── run.bat / run.sh      запуск для разработки
```

---

## Безопасность

- Бэкенд слушает только `127.0.0.1` — не доступен из сети
- Токены хранятся только в локальном `.env` файле, никуда не отправляются
- **Не открывай порт 8765 наружу** без добавления аутентификации
