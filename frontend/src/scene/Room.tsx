import { useEffect, useRef } from 'react';
import { Application, Container, Graphics, Text, TextStyle, Ticker } from 'pixi.js';
import type { Agent, AgentState, SystemSnapshot } from '../api';

// ---------- isometric math ----------
const TILE_W = 96;
const TILE_H = 48;
const iso = (x: number, y: number) => ({
  x: (x - y) * (TILE_W / 2),
  y: (x + y) * (TILE_H / 2),
});

const COLS = 7;
const ROWS = 7;

// desk slots → isometric tile coords
const DESK_SLOTS: Record<string, { x: number; y: number; kind: 'center' | 'side' }> = {
  center:      { x: 3, y: 3, kind: 'center' },
  left:        { x: 0, y: 3, kind: 'side' },
  right:       { x: 6, y: 3, kind: 'side' },
  back_left:   { x: 1, y: 0, kind: 'side' },
  back_right:  { x: 5, y: 0, kind: 'side' },
  spare:       { x: 3, y: 6, kind: 'side' },
};

const WALL_H = 120;

// ---------- primitives ----------
function drawFloor(c: Container) {
  const g = new Graphics();
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const { x: px, y: py } = iso(x, y);
      const color = (x + y) % 2 === 0 ? 0x1b2030 : 0x232a3d;
      g.poly([
        px, py,
        px + TILE_W / 2, py + TILE_H / 2,
        px, py + TILE_H,
        px - TILE_W / 2, py + TILE_H / 2,
      ]).fill({ color });
      g.stroke({ color: 0x0a0d14, width: 1, alpha: 0.6 });
    }
  }
  c.addChild(g);
}

function drawWalls(c: Container) {
  const g = new Graphics();
  for (let x = 0; x < COLS; x++) {
    const { x: px, y: py } = iso(x, 0);
    g.poly([
      px - TILE_W / 2, py + TILE_H / 2,
      px, py,
      px, py - WALL_H,
      px - TILE_W / 2, py + TILE_H / 2 - WALL_H,
    ]).fill({ color: 0x2a3149 });
    g.stroke({ color: 0x141822, width: 1, alpha: 0.8 });
  }
  for (let y = 0; y < ROWS; y++) {
    const { x: px, y: py } = iso(0, y);
    g.poly([
      px, py,
      px + TILE_W / 2, py + TILE_H / 2,
      px + TILE_W / 2, py + TILE_H / 2 - WALL_H,
      px, py - WALL_H,
    ]).fill({ color: 0x242b3d });
    g.stroke({ color: 0x141822, width: 1, alpha: 0.8 });
  }
  c.addChild(g);
}

function drawDesk(
  c: Container,
  cx: number,
  cy: number,
  accent: number,
  isBoss: boolean,
) {
  const g = new Graphics();
  const w = isBoss ? 110 : 80;
  const h = isBoss ? 55 : 40;
  g.poly([cx, cy - h / 2, cx + w / 2, cy, cx, cy + h / 2, cx - w / 2, cy]).fill({
    color: 0x3a4156,
  });
  g.stroke({ color: 0x0a0d14, width: 1 });
  // monitor
  g.rect(cx - 14, cy - 26, 28, 18).fill({ color: 0x0a0d14 });
  g.rect(cx - 12, cy - 24, 24, 14).fill({ color: accent, alpha: 0.85 });
  g.rect(cx - 3, cy - 10, 6, 6).fill({ color: 0x0a0d14 });
  c.addChild(g);
}

function drawLamp(c: Container, cx: number, cy: number, color: number) {
  const g = new Graphics();
  // pole
  g.rect(cx + 16, cy - 40, 2, 30).fill({ color: 0x3a4156 });
  // shade
  g.poly([cx + 12, cy - 40, cx + 22, cy - 40, cx + 26, cy - 30, cx + 8, cy - 30]).fill({
    color: 0x3a4156,
  });
  // bulb (we animate its alpha/scale separately, so use a dedicated graphic)
  c.addChild(g);
  const bulb = new Graphics();
  bulb.circle(cx + 17, cy - 29, 3).fill({ color });
  c.addChild(bulb);
  return bulb;
}

function drawAvatar(c: Container, cx: number, cy: number, color: number, name: string) {
  const body = new Graphics();
  body.ellipse(cx, cy + 30, 22, 7).fill({ color: 0x000000, alpha: 0.35 });
  body.roundRect(cx - 14, cy - 8, 28, 32, 6).fill({ color });
  body.stroke({ color: 0x0a0d14, width: 1 });
  body.circle(cx, cy - 18, 12).fill({ color: 0xf1d5b0 });
  body.stroke({ color: 0x0a0d14, width: 1 });
  body.arc(cx, cy - 22, 12, Math.PI, Math.PI * 2).fill({ color: 0x2a1f1a });
  c.addChild(body);

  const label = new Text({
    text: name,
    style: new TextStyle({
      fontFamily: 'Inter, system-ui',
      fontSize: 11,
      fill: 0xe6e8ef,
      align: 'center',
      stroke: { color: 0x0a0d14, width: 3 },
    }),
  });
  label.anchor.set(0.5, 1);
  label.x = cx;
  label.y = cy - 34;
  c.addChild(label);

  return { body };
}

// A small speech-bubble that appears above an agent showing its current tool
// or "thinking" indicator.
function createStatusBubble(cx: number, cy: number) {
  const container = new Container();
  container.x = cx;
  container.y = cy - 56;
  container.visible = false;

  const bg = new Graphics();
  container.addChild(bg);

  const text = new Text({
    text: '',
    style: new TextStyle({
      fontFamily: 'JetBrains Mono, Consolas, monospace',
      fontSize: 10,
      fill: 0x0a0d14,
      align: 'center',
    }),
  });
  text.anchor.set(0.5, 0.5);
  container.addChild(text);

  const redraw = (msg: string, color: number) => {
    text.text = msg;
    const pad = 6;
    const w = text.width + pad * 2;
    const h = text.height + pad * 2;
    bg.clear();
    bg.roundRect(-w / 2, -h / 2, w, h, 6).fill({ color });
    bg.stroke({ color: 0x0a0d14, width: 1 });
    // little triangle tail
    bg.poly([-4, h / 2, 4, h / 2, 0, h / 2 + 5]).fill({ color });
  };

  return { container, redraw };
}

// CPU-картина на стене: живая гистограмма последних сэмплов по CPU%.
function createCpuPainting(world: Container) {
  // position: roughly above desks on the back-left wall
  const { x: ax, y: ay } = iso(3, 0);
  const painting = new Container();
  painting.x = ax;
  painting.y = ay - WALL_H + 20;
  world.addChild(painting);

  const frame = new Graphics();
  const FW = 140;
  const FH = 66;
  frame.rect(-FW / 2 - 4, -FH / 2 - 4, FW + 8, FH + 8).fill({ color: 0x141822 });
  frame.stroke({ color: 0xf5b301, width: 2, alpha: 0.6 });
  painting.addChild(frame);

  const inner = new Graphics();
  painting.addChild(inner);

  const title = new Text({
    text: 'CPU',
    style: new TextStyle({
      fontFamily: 'JetBrains Mono',
      fontSize: 9,
      fill: 0xf5b301,
    }),
  });
  title.x = -FW / 2;
  title.y = -FH / 2 - 14;
  painting.addChild(title);

  let samples: number[] = [];
  const MAX = 32;

  const push = (cpu: number) => {
    samples = [...samples.slice(-MAX + 1), Math.max(0, Math.min(100, cpu))];
    inner.clear();
    const barW = FW / MAX;
    samples.forEach((v, i) => {
      const h = (v / 100) * (FH - 4);
      const x = -FW / 2 + i * barW;
      const y = FH / 2 - h;
      const col =
        v > 85 ? 0xef4444 : v > 55 ? 0xf5b301 : 0x4ade80;
      inner.rect(x + 1, y, barW - 2, h).fill({ color: col, alpha: 0.9 });
    });
  };

  return { push };
}

// ---------- component ----------
interface Props {
  agents: Agent[];
  states: Record<string, AgentState>;
  snapshot: SystemSnapshot | null;
  onSelect: (agentId: string) => void;
}

interface AgentVisual {
  group: Container;
  body: Graphics;
  bulb: Graphics;
  bubble: ReturnType<typeof createStatusBubble>;
  baseY: number;
  agentId: string;
}

export function Room({ agents, states, snapshot, onSelect }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const agentsLayerRef = useRef<Container | null>(null);
  const visualsRef = useRef<Map<string, AgentVisual>>(new Map());
  const cpuPaintingRef = useRef<{ push: (v: number) => void } | null>(null);
  const tickerRef = useRef<((t: Ticker) => void) | null>(null);

  // FIX #1: stale closure — держим states в ref, который тикер читает каждый кадр.
  // Без этого ticker захватывал бы начальный пустой {} и анимации никогда не работали.
  const statesRef = useRef<Record<string, AgentState>>(states);
  useEffect(() => { statesRef.current = states; }, [states]);

  // init pixi once
  useEffect(() => {
    let cancelled = false;
    const el = hostRef.current!;
    const app = new Application();
    app
      .init({ resizeTo: el, background: 0x0a0d14, antialias: true })
      .then(() => {
        if (cancelled) return;
        el.appendChild(app.canvas);
        appRef.current = app;

        const world = new Container();
        app.stage.addChild(world);
        const recenter = () => {
          world.x = app.renderer.width / 2;
          world.y = app.renderer.height / 2 - 120;
        };
        recenter();
        window.addEventListener('resize', recenter);

        drawWalls(world);
        drawFloor(world);
        cpuPaintingRef.current = createCpuPainting(world);

        const agentsLayer = new Container();
        agentsLayer.sortableChildren = true;
        world.addChild(agentsLayer);
        agentsLayerRef.current = agentsLayer;

        // Ticker читает statesRef.current — всегда свежие данные без лишних ре-рендеров.
        const tick = (_t: Ticker) => {
          const time = performance.now() / 1000;
          visualsRef.current.forEach((v, agentId) => {
            const st = statesRef.current[agentId];
            const status = st?.status ?? 'idle';
            if (status === 'thinking') {
              v.body.y = Math.sin(time * 3) * 1.5;
              v.bulb.alpha = 0.6 + 0.4 * Math.abs(Math.sin(time * 3));
              v.bulb.scale.set(1 + 0.2 * Math.abs(Math.sin(time * 3)));
            } else if (status === 'tool') {
              v.body.y = Math.sin(time * 8) * 2;
              v.bulb.alpha = 0.4 + 0.6 * Math.abs(Math.sin(time * 6));
              v.bulb.scale.set(1 + 0.35 * Math.abs(Math.sin(time * 6)));
            } else {
              v.body.y = 0;
              v.bulb.alpha = 0.35;
              v.bulb.scale.set(1);
            }
          });
        };
        tickerRef.current = tick;
        app.ticker.add(tick);
      });

    return () => {
      cancelled = true;
      if (appRef.current && tickerRef.current) {
        appRef.current.ticker.remove(tickerRef.current);
      }
      app.destroy(true, { children: true });
      appRef.current = null;
    };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps -- намеренно: Pixi init только раз

  // redraw agents when the list changes (not state — that's handled by ticker)
  useEffect(() => {
    const layer = agentsLayerRef.current;
    if (!layer) return;
    layer.removeChildren();
    visualsRef.current.clear();

    for (const agent of agents) {
      const slot = DESK_SLOTS[agent.desk] ?? DESK_SLOTS.spare;
      const { x, y } = iso(slot.x, slot.y);
      const accent = parseInt(agent.color.replace('#', ''), 16);
      const group = new Container();
      group.zIndex = y;
      group.eventMode = 'static';
      group.cursor = 'pointer';
      group.on('pointerover', () => (group.alpha = 0.85));
      group.on('pointerout', () => (group.alpha = 1));
      group.on('pointerdown', () => onSelect(agent.id));

      drawDesk(group, x, y + TILE_H / 2, accent, slot.kind === 'center');
      const bulb = drawLamp(group, x, y + TILE_H / 2, accent);
      const { body } = drawAvatar(group, x, y + TILE_H / 2 - 6, accent, agent.name);
      const bubble = createStatusBubble(x, y + TILE_H / 2 - 6);
      group.addChild(bubble.container);

      layer.addChild(group);

      visualsRef.current.set(agent.id, {
        group,
        body,
        bulb,
        bubble,
        baseY: y + TILE_H / 2 - 6,
        agentId: agent.id,
      });
    }
  }, [agents, onSelect]);

  // react to state changes — update bubbles text / visibility
  useEffect(() => {
    visualsRef.current.forEach((v, agentId) => {
      const st = states[agentId];
      if (!st || st.status === 'idle') {
        v.bubble.container.visible = false;
        return;
      }
      v.bubble.container.visible = true;
      if (st.status === 'thinking') {
        v.bubble.redraw('думает…', 0xf5b301);
      } else if (st.status === 'tool') {
        v.bubble.redraw(st.last_tool ?? 'инструмент…', 0x60a5fa);
      }
    });
  }, [states]);

  // feed CPU snapshots into the wall painting
  useEffect(() => {
    if (snapshot && cpuPaintingRef.current) {
      cpuPaintingRef.current.push(snapshot.cpu_percent);
    }
  }, [snapshot]);

  return <div ref={hostRef} className="absolute inset-0" />;
}
