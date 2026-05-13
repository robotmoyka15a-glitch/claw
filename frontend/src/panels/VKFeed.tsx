import { useEffect, useState } from 'react';
import { api } from '../api';

export function VKFeed() {
  const [me, setMe] = useState<any>(null);
  const [online, setOnline] = useState<any>(null);
  const [feed, setFeed] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setError(null);
    try {
      const [m, o, f] = await Promise.all([api.vkMe(), api.vkFriends(), api.vkFeed(20)]);
      setMe(m);
      setOnline(o);
      setFeed(f);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  if (error) {
    return (
      <div className="text-sm">
        <div className="text-red-400 mb-2">VK: {error}</div>
        <div className="text-gray-400">
          Проверь <code>VK_ACCESS_TOKEN</code> в <code>backend/.env</code> — для получения
          токена используй Implicit Flow ВКонтакте со scope <code>friends,wall,offline</code>.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {me && (
        <div className="flex items-center gap-3 bg-[#0f1420] rounded p-2">
          {me.photo_200 && <img src={me.photo_200} className="w-12 h-12 rounded-full" />}
          <div>
            <div className="font-semibold">
              {me.first_name} {me.last_name}
            </div>
            <div className="text-xs text-gray-400">
              {online?.count ?? 0} друзей онлайн
            </div>
          </div>
          <button className="btn ml-auto" onClick={refresh}>
            ⟳
          </button>
        </div>
      )}

      {online?.items?.length ? (
        <div className="flex gap-2 overflow-x-auto py-1">
          {online.items.map((u: any) => (
            <div key={u.id} className="flex flex-col items-center text-xs w-14 shrink-0">
              {u.photo_100 && (
                <img src={u.photo_100} className="w-10 h-10 rounded-full" />
              )}
              <span className="truncate w-14 text-center">{u.first_name}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex-1 min-h-0 overflow-auto space-y-2">
        {feed?.items?.map((item: any, i: number) => (
          <div key={i} className="bg-[#0f1420] rounded p-2 text-sm">
            <div className="whitespace-pre-wrap">{item.text?.slice(0, 400) || '(медиа)'}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
