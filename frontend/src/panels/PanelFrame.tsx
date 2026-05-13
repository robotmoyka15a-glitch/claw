import { useEffect, useRef, useState, type ReactNode } from 'react';

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
  initial?: { x?: number; y?: number; w?: number; h?: number };
}

// Tiny draggable floating panel. Not pixel-perfect; just enough to keep the
// "workbench" feel without adding a heavy dependency.
export function PanelFrame({ title, onClose, children, initial }: Props) {
  const [pos, setPos] = useState({
    x: initial?.x ?? 80,
    y: initial?.y ?? 80,
  });
  const size = {
    w: initial?.w ?? 480,
    h: initial?.h ?? 360,
  };
  const dragRef = useRef<{ ox: number; oy: number } | null>(null);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current) return;
      setPos({ x: e.clientX - dragRef.current.ox, y: e.clientY - dragRef.current.oy });
    };
    const onUp = () => (dragRef.current = null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  return (
    <div
      className="panel absolute shadow-2xl flex flex-col"
      style={{ left: pos.x, top: pos.y, width: size.w, height: size.h }}
    >
      <div
        className="panel-header cursor-grab active:cursor-grabbing"
        onMouseDown={(e) => {
          dragRef.current = { ox: e.clientX - pos.x, oy: e.clientY - pos.y };
        }}
      >
        <span>{title}</span>
        <button className="btn" onClick={onClose} style={{ padding: '2px 8px' }}>
          ×
        </button>
      </div>
      <div className="panel-body flex-1 min-h-0">{children}</div>
    </div>
  );
}
