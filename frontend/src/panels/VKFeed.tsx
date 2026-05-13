import { useEffect, useState } from 'react';
import { api } from '../api';

type Tab = 'feed' | 'search' | 'friends' | 'wall';

export function VKFeed() {
  const [me, setMe] = useState<any>(null);
  const [online, setOnline] = useState<any>(null);
  const [feed, setFeed] = useState<any>(null);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchQ, setSearchQ] = useState('');
  const [wall, setWall] = useState<any>(null);
  const [tab, setTab] = useState<Tab>('feed');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Message compose
  const [msgUserId, setMsgUserId] = useState('');
  const [msgText, setMsgText] = useState('');
  const [msgSending, setMsgSending] = useState(false);
  const [msgOk, setMsgOk] = useState(false);

  const refresh = async () => {
    setError(null);
    setLoading(true);
    try {
      const [m, o, f] = await Promise.all([api.vkMe(), api.vkFriends(), api.vkFeed(20)]);
      setMe(m);
      setOnline(o);
      setFeed(f);
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setLoading(false);
    }
  };

  const loadWall = async () => {
    setLoading(true);
    try {
      const w = await api.vkWall();
      setWall(w);
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setLoading(false);
    }
  };

  const doSearch = async () => {
    if (!searchQ.trim()) return;
    setLoading(true);
    try {
      const r = await api.vkSearch(searchQ, 20);
      setSearchResults(r?.items ?? []);
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!msgUserId || !msgText.trim()) return;
    if (!confirm(`Отправить сообщение пользователю ${msgUserId}?`)) return;
    setMsgSending(true);
    try {
      await api.vkSendMessage(parseInt(msgUserId), msgText);
      setMsgOk(true);
      setMsgText('');
      setTimeout(() => setMsgOk(false), 3000);
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setMsgSending(false);
    }
  };

  const likePost = async (item: any) => {
    try {
      await api.vkLike(item.source_id ?? item.from_id, item.post_id ?? item.id);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  };

  useEffect(() => { refresh(); }, []);
  useEffect(() => { if (tab === 'wall') loadWall(); }, [tab]);

  if (error) {
    return (
      <div className="text-sm">
        <div className="text-red-400 mb-2">VK: {error}</div>
        <div className="text-gray-400 text-xs">
          Проверь <code>VK_ACCESS_TOKEN</code> в Настройках.
          Scope должен включать: <code>friends,wall,messages,offline</code>.
        </div>
        <button className="btn mt-2" onClick={() => { setError(null); refresh(); }}>
          повторить
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 h-full">
      {/* Profile header */}
      {me && (
        <div className="flex items-center gap-3 bg-[#0f1420] rounded p-2 flex-shrink-0">
          {me.photo_200 && (
            <img src={me.photo_200} className="w-10 h-10 rounded-full" alt="avatar" />
          )}
          <div className="min-w-0">
            <div className="font-semibold truncate">
              {me.first_name} {me.last_name}
            </div>
            <div className="text-xs text-gray-400">
              {online?.count ?? 0} друзей онлайн
              {me.status && ` · ${me.status}`}
            </div>
          </div>
          <button
            className="btn ml-auto"
            onClick={refresh}
            disabled={loading}
            title="Обновить"
          >
            {loading ? '…' : '⟳'}
          </button>
        </div>
      )}

      {/* Online friends strip */}
      {online?.items?.length > 0 && (
        <div className="flex gap-2 overflow-x-auto py-1 flex-shrink-0">
          {online.items.map((u: any) => (
            <div
              key={u.id}
              className="flex flex-col items-center text-xs w-14 shrink-0"
              title={`${u.first_name} ${u.last_name || ''}`}
            >
              {u.photo_100 && (
                <div className="relative">
                  <img src={u.photo_100} className="w-10 h-10 rounded-full" alt={u.first_name} />
                  <div className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-green-400 border-2 border-[#0f1420]" />
                </div>
              )}
              <span className="truncate w-14 text-center text-gray-300">{u.first_name}</span>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 flex-shrink-0 border-b border-white/10">
        {(['feed', 'search', 'wall', 'friends'] as Tab[]).map((t) => (
          <button
            key={t}
            className="px-3 py-1 text-xs rounded-t"
            style={{
              background: tab === t ? '#1b2235' : 'transparent',
              color: tab === t ? '#e6e8ef' : '#6b7488',
            }}
            onClick={() => setTab(t)}
          >
            {{ feed: 'Лента', search: 'Поиск', wall: 'Стена', friends: 'Написать' }[t]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-auto">

        {/* Feed */}
        {tab === 'feed' && (
          <div className="space-y-2">
            {(feed?.items ?? []).map((item: any, i: number) => (
              <PostCard key={i} item={item} profiles={feed?.profiles} onLike={likePost} />
            ))}
            {!feed?.items?.length && <div className="text-gray-500 text-xs p-2">лента пуста</div>}
          </div>
        )}

        {/* Search */}
        {tab === 'search' && (
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && doSearch()}
                placeholder="поиск постов ВКонтакте…"
              />
              <button className="btn btn-primary" onClick={doSearch} disabled={loading}>
                {loading ? '…' : '→'}
              </button>
            </div>
            <div className="space-y-2">
              {searchResults.map((item: any, i: number) => (
                <PostCard key={i} item={item} onLike={likePost} />
              ))}
              {searchResults.length === 0 && searchQ && !loading && (
                <div className="text-gray-500 text-xs">нет результатов</div>
              )}
            </div>
          </div>
        )}

        {/* Wall */}
        {tab === 'wall' && (
          <div className="space-y-2">
            {(wall?.items ?? []).map((item: any, i: number) => (
              <PostCard key={i} item={item} profiles={wall?.profiles} onLike={likePost} />
            ))}
            {!wall?.items?.length && <div className="text-gray-500 text-xs p-2">стена пуста</div>}
          </div>
        )}

        {/* Send message */}
        {tab === 'friends' && (
          <div className="flex flex-col gap-3 p-1">
            <div className="text-xs text-gray-400 bg-[#0f1420] rounded p-2">
              Для отправки сообщений токен должен включать scope{' '}
              <code className="text-yellow-400">messages</code>.
            </div>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">User ID получателя</span>
              <input
                type="number"
                value={msgUserId}
                onChange={(e) => setMsgUserId(e.target.value)}
                placeholder="числовой id ВКонтакте"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">Сообщение</span>
              <textarea
                value={msgText}
                onChange={(e) => setMsgText(e.target.value)}
                placeholder="текст сообщения…"
                style={{ minHeight: 80 }}
              />
            </label>
            <button
              className="btn btn-primary"
              onClick={sendMessage}
              disabled={msgSending || !msgUserId || !msgText.trim()}
            >
              {msgSending ? 'отправляю…' : '📩 отправить'}
            </button>
            {msgOk && <div className="text-green-400 text-xs">✓ сообщение отправлено</div>}
          </div>
        )}
      </div>
    </div>
  );
}

function PostCard({
  item,
  profiles,
  onLike,
}: {
  item: any;
  profiles?: any[];
  onLike: (item: any) => void;
}) {
  const [liked, setLiked] = useState(false);

  const authorId = item.source_id ?? item.from_id;
  const author = profiles?.find((p: any) => p.id === Math.abs(authorId));
  const authorName = author
    ? `${author.first_name} ${author.last_name || ''}`.trim()
    : authorId > 0
    ? `id${authorId}`
    : `club${Math.abs(authorId)}`;

  const date = item.date ? new Date(item.date * 1000).toLocaleString('ru-RU', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '';

  return (
    <div className="bg-[#0f1420] rounded p-2 text-sm">
      <div className="flex items-center gap-2 mb-1">
        {author?.photo_100 && (
          <img src={author.photo_100} className="w-7 h-7 rounded-full" alt={authorName} />
        )}
        <div className="min-w-0">
          <div className="text-xs font-semibold text-gray-300 truncate">{authorName}</div>
          {date && <div className="text-[10px] text-gray-500">{date}</div>}
        </div>
      </div>
      <div className="whitespace-pre-wrap text-gray-200 text-xs leading-relaxed">
        {item.text?.slice(0, 500) || '(медиа или репост)'}
        {item.text?.length > 500 && <span className="text-gray-500">…</span>}
      </div>
      <div className="flex items-center gap-3 mt-1.5">
        <button
          className="text-xs flex items-center gap-1"
          style={{ color: liked ? '#ef4444' : '#6b7488', background: 'none', border: 'none', cursor: 'pointer' }}
          onClick={() => { setLiked(true); onLike(item); }}
          title="Поставить лайк"
        >
          {liked ? '❤️' : '🤍'} {item.likes?.count ?? 0}
        </button>
        {item.comments?.count > 0 && (
          <span className="text-[10px] text-gray-500">💬 {item.comments.count}</span>
        )}
        {item.reposts?.count > 0 && (
          <span className="text-[10px] text-gray-500">🔁 {item.reposts.count}</span>
        )}
      </div>
    </div>
  );
}
