/**
 * About / Help panel — version info, quick-start guide, keyboard shortcuts.
 */
export function AboutPanel() {
  const shortcuts = [
    ['Клик по агенту', 'Открыть чат + настройки агента'],
    ['Кнопка «+ агент»', 'Создать нового агента (пресет researcher)'],
    ['⚙ Настройки', 'Вставить токены ВКонтакте / Telegram / Spotify и т.д.'],
    ['Enter в чате', 'Отправить сообщение агенту'],
    ['Shift+Enter', 'Перенос строки в чате'],
    ['Заголовок панели', 'Перетащить панель'],
    ['× на панели', 'Закрыть панель'],
  ];

  const connectors = [
    { name: 'ВКонтакте', scope: 'friends,wall,offline (+ messages для отправки)', hint: 'vk.com/apps → OAuth Implicit Flow' },
    { name: 'Telegram', scope: 'Bot Token от @BotFather', hint: 'Создай бота, вставь токен' },
    { name: 'Discord', scope: 'Bot Token из Developer Portal', hint: 'discord.com/developers' },
    { name: 'Steam', scope: 'Steam Web API Key + SteamID64', hint: 'steamcommunity.com/dev/apikey' },
    { name: 'Spotify', scope: 'Client ID + Secret + Refresh Token', hint: 'Смотри раздел ниже' },
  ];

  const llms = [
    { name: 'Ollama (local)', hint: 'ollama.ai → ollama pull qwen2.5:7b', default: 'http://127.0.0.1:11434' },
    { name: 'Qwen local', hint: 'LM Studio / vLLM / llama.cpp server', default: 'http://127.0.0.1:8000/v1' },
    { name: 'Qwen cloud', hint: 'dashscope.aliyuncs.com — нужен API ключ', default: 'qwen-plus' },
  ];

  return (
    <div className="flex flex-col gap-4 text-sm h-full overflow-auto">
      {/* header */}
      <div className="flex items-center gap-3">
        <div className="text-4xl select-none">🐾</div>
        <div>
          <div className="text-xl font-bold text-[#f5b301]">claw</div>
          <div className="text-xs text-gray-400">Control Local Agents Workspace · v0.1</div>
        </div>
      </div>

      <div className="text-gray-300 text-xs leading-relaxed bg-[#0f1420] rounded p-3">
        Локальный рабочий стол для управления ИИ-агентами. Агенты сидят за столами в
        изометрической комнате и могут мониторить систему, писать в Telegram/Discord/ВК,
        управлять Spotify и выполнять команды в терминале — через LLM tool-calling.
        Всё работает локально на <code className="text-[#f5b301]">127.0.0.1:8765</code>.
      </div>

      {/* shortcuts */}
      <Section title="Горячие клавиши и управление">
        <table className="w-full text-xs">
          <tbody>
            {shortcuts.map(([k, v]) => (
              <tr key={k} className="border-t border-white/5">
                <td className="py-1 pr-3 text-[#f5b301] font-mono whitespace-nowrap">{k}</td>
                <td className="py-1 text-gray-300">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {/* LLM */}
      <Section title="Провайдеры LLM">
        <div className="space-y-2">
          {llms.map((l) => (
            <div key={l.name} className="bg-[#0f1420] rounded p-2">
              <div className="font-semibold text-[#a78bfa]">{l.name}</div>
              <div className="text-gray-400 text-xs">{l.hint}</div>
              <code className="text-gray-500 text-[10px]">{l.default}</code>
            </div>
          ))}
        </div>
      </Section>

      {/* Connectors */}
      <Section title="Коннекторы к сервисам">
        <div className="space-y-2 text-xs">
          {connectors.map((c) => (
            <div key={c.name} className="bg-[#0f1420] rounded p-2">
              <div className="font-semibold">{c.name}</div>
              <div className="text-gray-400">Scope / тип: <code>{c.scope}</code></div>
              <div className="text-gray-500">{c.hint}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* Spotify guide */}
      <Section title="Как получить Spotify Refresh Token">
        <div className="text-xs text-gray-300 space-y-1 bg-[#0f1420] rounded p-3">
          <p>1. Зайди на <a href="https://developer.spotify.com/dashboard" target="_blank" rel="noreferrer" className="text-[#1db954] underline">developer.spotify.com/dashboard</a>, создай приложение.</p>
          <p>2. В настройках приложения добавь Redirect URI: <code className="text-yellow-400">http://localhost:8888/callback</code></p>
          <p>3. Открой в браузере (вставь свой client_id):</p>
          <code className="block bg-[#141822] rounded p-2 text-[10px] break-all text-green-300">
            {'https://accounts.spotify.com/authorize?client_id=YOUR_ID&response_type=code&redirect_uri=http://localhost:8888/callback&scope=user-read-currently-playing%20user-read-playback-state%20user-modify-playback-state'}
          </code>
          <p>4. После входа скопируй параметр <code>?code=...</code> из URL.</p>
          <p>5. Обменяй code на refresh token через POST запрос к Spotify Accounts API.</p>
          <p className="text-gray-500">
            Удобнее всего использовать скрипт{' '}
            <a href="https://github.com/spotify/spotify-auth-examples" target="_blank" rel="noreferrer" className="text-[#1db954] underline">spotify-auth-examples</a>.
          </p>
        </div>
      </Section>

      {/* build EXE */}
      <Section title="Сборка одного EXE-файла">
        <div className="text-xs text-gray-300 bg-[#0f1420] rounded p-3 space-y-1">
          <p>Запусти скрипт сборки из корня репозитория:</p>
          <code className="block bg-[#141822] rounded p-2 text-green-300">build_exe.bat</code>
          <p className="text-gray-500">
            Скрипт собирает фронтенд (Vite), создаёт Python venv, запускает PyInstaller
            и кладёт <code>claw.exe</code> в <code>backend/dist/</code>.
            При первом запуске EXE создаёт <code>%LOCALAPPDATA%\claw\.env</code>
            с шаблоном токенов.
          </p>
        </div>
      </Section>

      <div className="text-center text-gray-500 text-xs pb-2">
        github.com/robotmoyka15a-glitch/claw · MIT License
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2 px-1">
        {title}
      </div>
      {children}
    </div>
  );
}
