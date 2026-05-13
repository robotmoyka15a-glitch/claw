import { useEffect, useRef } from 'react';
import { wsUrl } from '../api';

export function useWS<T>(
  path: string,
  onMessage: (data: T) => void,
  enabled = true,
) {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let closed = false;
    let retry = 0;

    const connect = () => {
      const ws = new WebSocket(wsUrl(path));
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          onMessage(JSON.parse(ev.data) as T);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (closed) return;
        retry = Math.min(retry + 1, 6);
        setTimeout(connect, 500 * retry);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      closed = true;
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, enabled]);

  return wsRef;
}
