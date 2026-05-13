# claw — Control Local Agents Workspace

[![Build & Release EXE](https://github.com/robotmoyka15a-glitch/claw/actions/workflows/release.yml/badge.svg)](https://github.com/robotmoyka15a-glitch/claw/actions/workflows/release.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Локальный рабочий стол для управления ИИ-агентами на Windows.  
Агенты «живут» в изометрической комнате и работают **автономно** — мониторят систему, читают VK/Telegram, управляют Spotify, выполняют shell-команды — через LLM tool-calling с вашей локальной моделью (Ollama / Qwen).

---

## ⬇️ Быстрый старт — скачать готовый EXE

**→ [Releases → скачать claw.exe](https://github.com/robotmoyka15a-glitch/claw/releases/latest)**

1. Скачай `claw.exe` со страницы Releases  
2. Запусти — браузер откроется на `http://127.0.0.1:8765` автоматически  
3. Открой **⚙️ Настройки** и вставь токены (VK, Telegram, LLM и т.д.)  
4. Кликни на агента в комнате → начни чат или настрой автономные задачи

> Требования: Windows 10/11 x64, 4 ГБ RAM  
> Ollama нужен только для локальных LLM — без него работает с Qwen cloud

---

## Возможности

| Раздел | Что умеет |
|---|---|
| 🏠 **Изометрическая комната** | Pixi.js 2.5D, агенты за столами, анимации, частицы, CPU-картина на стене |
| 🤖 **ИИ-агенты** | 5 пресетов (Chief, Sys, Vika, Shell, Lex), tool-calling, делегирование |
| 🔄 **Автономия** | Задачи по расписанию / событиям (CPU > 85%, новый процесс, Telegram-сообщение) |
| 🧠 **ModelRouter** | Автовыбор провайдера под задачу + fallback-цепочка |
| 📊 **Мониторинг** | CPU/RAM/Disk/Net в реальном времени, список процессов (diff WebSocket) |
| 💻 **Терминал** | Встроенный Windows PTY (pywinpty), xterm.js |
| 💙 **ВКонтакте** | Лента, друзья, поиск постов, лайки, сообщения |
| ✈️ **Telegram** | Long-poll + Webhook, автоматическая реакция на входящие сообщения |
| 🎮 **Discord** | Чтение/отправка сообщений через Bot API |
| 🎯 **Steam** | Профиль, библиотека, статистика |
| 🎵 **Spotify** | Now Playing с прогресс-баром, управление воспроизведением |
| 🔔 **Уведомления** | Windows tray + dashboard toast от агентов (`notify.toast`) |
| ⚙️ **Настройки в UI** | Все токены вводятся прямо в браузере, без редактирования файлов |
| 🤖 **Модели LLM** | Мониторинг Ollama/Qwen: VRAM статус, pull новых моделей, удаление |
| 🔒 **Безопасность** | CSRF-токен, шифрование `.env`, маскировка логов, rate limiter |

---

## LLM провайдеры

| Провайдер | Настройка | Рекомендуемые модели |
|---|---|---|
| **Ollama** (локально) | `OLLAMA_BASE_URL=http://127.0.0.1:11434` | `qwen2.5:7b`, `llama3.1:8b` |
| **Qwen local** (OpenAI-compat) | `QWEN_LOCAL_BASE_URL=http://127.0.0.1:8000/v1` | LM Studio, vLLM |
| **Qwen cloud** (DashScope) | `QWEN_CLOUD_API_KEY=sk-...` | `qwen-plus`, `qwen-max` |

**ModelRouter** автоматически выбирает лучший провайдер под задачу:
- Задача с tool-calling → модель с высоким `tool_calling` score
- Длинный контекст → `qwen-long` (1M токенов)
- Облако недоступно → автоматически переключается на local

---

## Автономные агенты

Агенты работают сами, без участия пользователя:

```
CPU > 85%     →  агент Sys просыпается → находит виновный процесс → notify.toast
Новое TG-сообщение → агент Vika читает → отвечает или пересылает
Каждые 5 мин  →  агент Chief проверяет статус системы
Новый процесс →  агент Sys проверяет подозрительность
```

Панель **🤖 Автономия** в дашборде:
- **Задачи** — создать, настроить триггер (manual / interval / cron / event), запустить
- **События** — живой лог всего что происходит в системе  
- **Роутер** — визуальная capability-матрица всех моделей

---

## Коннекторы — как получить токены

### ВКонтакте
```
https://oauth.vk.com/authorize?client_id=ВАШ_APP_ID&display=page
  &redirect_uri=https://oauth.vk.com/blank.html
  &scope=friends,wall,messages,offline&response_type=token&v=5.199
```
Токен появится в URL: `#access_token=...`

### Telegram
1. Напиши [@BotFather](https://t.me/BotFather) → `/newbot` → получи токен `123456789:AAA...`
2. Напиши боту → открой `https://api.telegram.org/bot<TOKEN>/getUpdates` → найди `"chat":{"id":...}`
3. Для Webhook: задай `TELEGRAM_WEBHOOK_URL=https://твой-домен/webhook/telegram`

### Discord
1. [discord.com/developers](https://discord.com/developers/applications) → New Application → Bot
2. Скопируй Token с вкладки Bot
3. ID канала: Developer Mode → ПКМ на канал → Copy Channel ID

### Steam
- Ключ: [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
- SteamID64: [steamid.io](https://steamid.io) (17 цифр, начинается с 7656...)

### Spotify
1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → Create App
2. Redirect URI: `http://localhost:8888/callback`
3. Авторизация (вставь CLIENT_ID):
```
https://accounts.spotify.com/authorize?client_id=CLIENT_ID
  &response_type=code&redirect_uri=http://localhost:8888/callback
  &scope=user-read-currently-playing%20user-read-playback-state%20user-modify-playback-state
```
4. Обменяй `?code=...` на refresh_token через POST к Spotify

---

## Запуск из исходников

```powershell
git clone https://github.com/robotmoyka15a-glitch/claw.git
cd claw
copy backend\.env.example backend\.env
# отредактируй backend\.env — добавь токены
run.bat
```

Скрипт создаст venv, поставит зависимости, поднимет оба сервера:
- Backend → `http://127.0.0.1:8765`
- Frontend (dev) → `http://127.0.0.1:5173`

---

## Сборка EXE самостоятельно

```powershell
git clone https://github.com/robotmoyka15a-glitch/claw.git
cd claw
build_exe.bat   # собирает frontend + PyInstaller → backend\dist\claw.exe
```

Скрипт (~3-5 минут):
1. Собирает React фронтенд (`npm run build`)
2. Создаёт Python venv
3. Запускает PyInstaller с `claw.spec`
4. Кладёт готовый EXE в `backend/dist/claw.exe`

---

## Структура проекта

```
claw/
├── backend/                Python FastAPI
│   ├── app/
│   │   ├── agents/         агенты, автономия, планировщик, ModelRouter
│   │   ├── api/            REST + WebSocket эндпоинты (72 маршрута)
│   │   ├── connectors/     Telegram, Discord, Steam, Spotify, Windows
│   │   ├── core/           config, db, security, ws_manager, http_pool
│   │   ├── llm/            Ollama, OpenAI-compat, router с fallback
│   │   ├── services/       psutil, terminal PTY, VK API
│   │   └── tools/          24 инструмента для tool-calling
│   ├── claw.spec           PyInstaller spec
│   ├── launcher.py         точка входа EXE (tray + auto browser)
│   └── requirements.txt
├── frontend/               React + Vite + TypeScript
│   └── src/
│       ├── panels/         Terminal, ProcessList, VKFeed, Autonomy, Models…
│       └── scene/          Room (Pixi.js, изометрия, анимации)
├── .github/workflows/      GitHub Actions — автосборка EXE при теге
├── build_exe.bat           сборка в один EXE
└── run.bat / run.sh        запуск для разработки
```

---

## Безопасность

- Бэкенд слушает только `127.0.0.1` — не доступен из сети  
- Каждый мутирующий запрос требует `X-Claw-Token` заголовок (CSRF защита)  
- Токены можно зашифровать: задай `CLAW_MASTER_PASSWORD` и используй `security.py encrypt_value()`  
- Все логи автоматически маскируют `Bearer ...`, `access_token=...`, `sk-...`  
- **Не открывай порт 8765 наружу** без добавления аутентификации

---

## Лицензия

MIT — делай что хочешь, но без гарантий.
