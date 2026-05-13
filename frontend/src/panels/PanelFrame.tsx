import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

interface Props {
  title: string;
  icon?: string;
  accentColor?: string;   // hex без #, например 'f5b301'
  onClose: () => void;
  children: ReactNode;
  initial?: { x?: number; y?: number; w?: number; h?: number };
  resizable?: boolean;
}

/**
 * Floating glassmorphism panel.
 * Drag by header. Resize from bottom-right corner.
 * Title bar has a subtle gradient tinted by accentColor.
 */
export function PanelFrame({
  title, icon, accentColor = 'f5b301', onClose, children, initial, resizable = true,
}: Props) {
  const [pos, setPos] = useState({ x: initial?.x ?? 80, y: initial?.y ?? 80 });
  const [size, setSize] = useState({ w: initial?.w ?? 480, h: initial?.h ?? 360 });
  const [maximized, setMaximized] = useState(false);
  const [prevBox, setPrevBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  const dragRef = useRef<{ ox: number; oy: number } | null>(null);
  const resizeRef = useRef<{ ox: number; oy: number; ow: number; oh: number } | null>(null);

  // ── drag ──────────────────────────────────────────────────────────
  const onDragMove = useCallback((e: MouseEvent) => {
    if (!dragRef.current || maximized) return;
    const nx = e.clientX - dragRef.current.ox;
    const ny = e.clientY - dragRef.current.oy;
    setPos({ x: Math.max(0, nx), y: Math.max(0, ny) });
  }, [maximized]);

  const onDragUp = useCallback(() => { dragRef.current = null; }, []);

  // ── resize ────────────────────────────────────────────────────────
  const onResizeMove = useCallback((e: MouseEvent) => {
    if (!resizeRef.current || maximized) return;
    const dw = e.clientX - resizeRef.current.ox;
    const dh = e.clientY - resizeRef.current.oy;
    setSize({
      w: Math.max(280, resizeRef.current.ow + dw),
      h: Math.max(180, resizeRef.current.oh + dh),
    });
  }, [maximized]);

  const onResizeUp = useCallback(() => { resizeRef.current = null; }, []);

  useEffect(() => {
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('mouseup', onDragUp);
    window.addEventListener('mousemove', onResizeMove);
    window.addEventListener('mouseup', onResizeUp);
    return () => {
      window.removeEventListener('mousemove', onDragMove);
      window.removeEventListener('mouseup', onDragUp);
      window.removeEventListener('mousemove', onResizeMove);
      window.removeEventListener('mouseup', onResizeUp);
    };
  }, [onDragMove, onDragUp, onResizeMove, onResizeUp]);

  // ── maximize / restore ────────────────────────────────────────────
  const toggleMaximize = () => {
    if (maximized) {
      if (prevBox) { setPos({ x: prevBox.x, y: prevBox.y }); setSize({ w: prevBox.w, h: prevBox.h }); }
      setMaximized(false);
    } else {
      setPrevBox({ x: pos.x, y: pos.y, w: size.w, h: size.h });
      setPos({ x: 56, y: 0 });
      setSize({ w: window.innerWidth - 56, h: window.innerHeight - 26 });
      setMaximized(true);
    }
  };

  const r = parseInt(accentColor.slice(0, 2), 16);
  const g2 = parseInt(accentColor.slice(2, 4), 16);
  const b = parseInt(accentColor.slice(4, 6), 16);

  const containerStyle: React.CSSProperties = maximized
    ? { position: 'fixed', left: 56, top: 0, width: window.innerWidth - 56, height: window.innerHeight - 26, zIndex: 50 }
    : { position: 'fixed', left: pos.x, top: pos.y, width: size.w, height: size.h, zIndex: 50 };

  return (
    <div
      className="panel animate-in flex flex-col"
      style={{
        ...containerStyle,
        boxShadow: `0 8px 32px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.06), 0 0 40px rgba(${r},${g2},${b},0.06)`,
      }}
    >
      {/* ── заголовок ─────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-2 flex-shrink-0 select-none cursor-grab active:cursor-grabbing px-3"
        style={{
          height: 38,
          background: `linear-gradient(135deg, rgba(${r},${g2},${b},0.12) 0%, rgba(13,17,23,0.95) 70%)`,
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          borderRadius: '10px 10px 0 0',
        }}
        onMouseDown={(e) => {
          if (maximized) return;
          dragRef.current = { ox: e.clientX - pos.x, oy: e.clientY - pos.y };
        }}
        onDoubleClick={toggleMaximize}
      >
        {/* иконка акцента */}
        {icon && <span className="text-sm select-none" style={{ filter: 'drop-shadow(0 0 4px currentColor)' }}>{icon}</span>}

        {/* заголовок */}
        <span className="flex-1 text-xs font-semibold truncate panel-title">{title}</span>

        {/* кнопки окна — как в macOS но тёмные */}
        <div className="flex items-center gap-1.5 ml-2">
          {/* minimize/restore */}
          <button
            title={maximized ? 'Восстановить' : 'Развернуть'}
            onClick={toggleMaximize}
            style={{
              width: 12, height: 12, borderRadius: '50%', border: 'none', cursor: 'pointer',
              background: `rgba(${r},${g2},${b},0.7)`,
              boxShadow: `0 0 6px rgba(${r},${g2},${b},0.5)`,
            }}
          />
          {/* close */}
          <button
            title="Закрыть"
            onClick={onClose}
            style={{
              width: 12, height: 12, borderRadius: '50%', border: 'none', cursor: 'pointer',
              background: 'rgba(239,68,68,0.75)',
              boxShadow: '0 0 6px rgba(239,68,68,0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 8, fontWeight: 700, color: 'rgba(0,0,0,0.5)',
            }}
          >
            ×
          </button>
        </div>
      </div>

      {/* ── содержимое ────────────────────────────────────────────── */}
      <div className="panel-body flex-1 min-h-0 overflow-auto">
        {children}
      </div>

      {/* ── ресайз-ручка ─────────────────────────────────────────── */}
      {resizable && !maximized && (
        <div
          style={{
            position: 'absolute', right: 0, bottom: 0,
            width: 16, height: 16,
            cursor: 'nwse-resize',
            borderRadius: '0 0 10px 0',
            background: 'linear-gradient(135deg, transparent 50%, rgba(255,255,255,0.08) 100%)',
          }}
          onMouseDown={(e) => {
            e.preventDefault();
            resizeRef.current = { ox: e.clientX, oy: e.clientY, ow: size.w, oh: size.h };
          }}
        />
      )}
    </div>
  );
}
