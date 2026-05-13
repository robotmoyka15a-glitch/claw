import { useEffect, useState } from 'react';
import { api } from '../api';

export function SpotifyPanel() {
  const [now, setNow] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = async () => {
    try { setNow(await api.spotifyNow()); setErr(null); }
    catch (e: any) { setErr(String(e.message ?? e)); }
  };
  useEffect(() => {
    refresh();
    const h = setInterval(refresh, 5000);
    return () => clearInterval(h);
  }, []);

  const control = async (action: 'pause' | 'resume' | 'next') => {
    try { await api.spotifyControl(action); refresh(); }
    catch (e: any) { setErr(String(e.message ?? e)); }
  };

  if (err) return <div className="text-sm text-red-400">Spotify: {err}</div>;
  if (!now) return <div className="text-sm text-gray-400">ничего не играет</div>;

  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="flex gap-3">
        {now.image && <img src={now.image} className="w-20 h-20 rounded" />}
        <div className="flex flex-col justify-center">
          <div className="font-semibold">{now.title}</div>
          <div className="text-gray-400">{now.artists}</div>
          <div className="text-xs text-gray-500">{now.album}</div>
        </div>
      </div>
      <div className="flex gap-2">
        <button className="btn" onClick={() => control('pause')}>⏸</button>
        <button className="btn" onClick={() => control('resume')}>▶</button>
        <button className="btn" onClick={() => control('next')}>⏭</button>
      </div>
    </div>
  );
}
