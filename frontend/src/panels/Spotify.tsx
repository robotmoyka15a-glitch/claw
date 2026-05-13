import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

function fmt(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export function SpotifyPanel() {
  const [now, setNow] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [localMs, setLocalMs] = useState(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = async () => {
    try {
      const data = await api.spotifyNow();
      setNow(data);
      setErr(null);
      // Reset local ticker to the current progress
      if (data?.is_playing) {
        setLocalMs(data.progress_ms ?? 0);
      }
    } catch (e: any) {
      setErr(String(e.message ?? e));
    }
  };

  // Poll every 5 s for remote state
  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 5000);
    return () => clearInterval(poll);
  }, []);

  // Local 1 s ticker to smooth the progress bar between polls
  useEffect(() => {
    if (tickRef.current) clearInterval(tickRef.current);
    if (now?.is_playing) {
      tickRef.current = setInterval(() => {
        setLocalMs((p) => Math.min(p + 1000, now.duration_ms ?? p));
      }, 1000);
    }
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [now?.is_playing, now?.duration_ms]);

  const control = async (action: 'pause' | 'resume' | 'next') => {
    try {
      await api.spotifyControl(action);
      setTimeout(refresh, 400); // give Spotify a moment to update
    } catch (e: any) {
      setErr(String(e.message ?? e));
    }
  };

  if (err) {
    return (
      <div className="text-sm">
        <div className="text-red-400 mb-2">Spotify: {err}</div>
        <div className="text-gray-400 text-xs">
          Убедись, что в Настройках заданы{' '}
          <code>SPOTIFY_CLIENT_ID</code>, <code>SPOTIFY_CLIENT_SECRET</code> и{' '}
          <code>SPOTIFY_REFRESH_TOKEN</code>.
        </div>
      </div>
    );
  }

  if (!now) {
    return (
      <div className="text-sm text-gray-400 flex flex-col gap-2">
        <div>Ничего не играет</div>
        <button className="btn" onClick={refresh}>⟳ обновить</button>
      </div>
    );
  }

  const progress = now.duration_ms > 0 ? localMs / now.duration_ms : 0;

  return (
    <div className="flex flex-col gap-3 text-sm">
      {/* Album art + info */}
      <div className="flex gap-3">
        {now.image ? (
          <img src={now.image} className="w-20 h-20 rounded shadow-lg flex-shrink-0" alt="album" />
        ) : (
          <div className="w-20 h-20 rounded bg-[#1db954]/20 flex items-center justify-center text-3xl flex-shrink-0">
            🎵
          </div>
        )}
        <div className="flex flex-col justify-center min-w-0">
          <div className="font-semibold truncate">{now.title}</div>
          <div className="text-gray-400 truncate">{now.artists}</div>
          <div className="text-xs text-gray-500 truncate">{now.album}</div>
          {now.url && (
            <a
              href={now.url}
              target="_blank"
              rel="noreferrer"
              className="text-[#1db954] text-xs mt-1 hover:underline"
            >
              открыть в Spotify ↗
            </a>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {now.duration_ms > 0 && (
        <div className="flex flex-col gap-1">
          <div className="w-full h-1.5 bg-[#1f2637] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{ width: `${progress * 100}%`, background: '#1db954' }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500 font-mono">
            <span>{fmt(localMs)}</span>
            <span>{fmt(now.duration_ms)}</span>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2 items-center">
        <button
          className="btn"
          style={{ fontSize: 18, padding: '4px 12px' }}
          onClick={() => control(now.is_playing ? 'pause' : 'resume')}
          title={now.is_playing ? 'Пауза' : 'Воспроизведение'}
        >
          {now.is_playing ? '⏸' : '▶'}
        </button>
        <button
          className="btn"
          style={{ fontSize: 18, padding: '4px 12px' }}
          onClick={() => control('next')}
          title="Следующий трек"
        >
          ⏭
        </button>
        <button className="btn ml-auto" onClick={refresh} title="Обновить">
          ⟳
        </button>
        <div
          className="w-2 h-2 rounded-full ml-1 flex-shrink-0"
          style={{ background: now.is_playing ? '#1db954' : '#6b7488' }}
          title={now.is_playing ? 'играет' : 'пауза'}
        />
      </div>
    </div>
  );
}
