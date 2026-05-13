import { useEffect } from 'react';
import { useStore } from '../store';

/**
 * Floating toast bubbles in the top-right corner. Fed by
 *   * the agents' notify.toast tool calls (via /api/connectors/notify/pending), and
 *   * in-browser pushToast() from anywhere in the app.
 */
export function ToastLayer() {
  const toasts = useStore((s) => s.toasts);
  const dismissToast = useStore((s) => s.dismissToast);

  useEffect(() => {
    if (toasts.length === 0) return;
    const h = setTimeout(() => {
      dismissToast(toasts[0].id);
    }, 6000);
    return () => clearTimeout(h);
  }, [toasts, dismissToast]);

  return (
    <div className="absolute top-14 right-4 flex flex-col gap-2 w-72 z-50">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`panel p-3 border-l-4 cursor-pointer ${
            t.level === 'error' ? 'border-red-500' :
            t.level === 'warn' ? 'border-yellow-400' :
            'border-sky-400'
          }`}
          onClick={() => dismissToast(t.id)}
        >
          <div className="font-semibold text-sm">{t.title}</div>
          <div className="text-xs text-gray-300 whitespace-pre-wrap">{t.message}</div>
        </div>
      ))}
    </div>
  );
}
