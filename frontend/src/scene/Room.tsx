import { useEffect, useRef } from 'react';
import { Application, Container, Graphics, Text, TextStyle } from 'pixi.js';
import type { Agent } from '../api';

// ---------- isometric math ----------
const TILE_W = 96;
const TILE_H = 48;
const iso = (x: number, y: number) => ({
  x: (x - y) * (TILE_W / 2),
  y: (x + y) * (TILE_H / 2),
});

// desk slots → isometric tile coords
const DESK_SLOTS: Record<string, { x: number; y: number; kind: 'center' | 'side' }> = {
  center:      { x: 3, y: 3, kind: 'center' },
  left:        { x: 0, y: 3, kind: 'side' },
  right:       { x: 6, y: 3, kind: 'side' },
  back_left:   { x: 1, y: 0, kind: 'side' },
  back_right:  { x: 5, y: 0, kind: 'side' },
  spare:       { x: 3, y: 6, kind: 'side' },
};

// ---------- primitives ----------
function drawFloor(c: Container, cols = 7, rows = 7) {
  const g = new Graphics();
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
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

function drawWalls(c: Container, cols = 7, rows = 7) {
  const g = new Graphics();
  const wallH = 120;
  // back-left wall (y = 0, going along x)
  for (let x = 0; x < cols; x++) {
    const { x: px, y: py } = iso(x, 0);
    g.poly([
      px - TILE_W / 2, py + TILE_H / 2,
      px, py,
      px, py - wallH,
      px - TILE_W / 2, py + TILE_H / 2 - wallH,
    ]).fill({ color: 0x2a3149 });
    g.stroke({ color: 0x141822, width: 1, alpha: 0.8 });
  }
  // back-right wall (x = 0, going along y)
  for (let y = 0; y < rows; y++) {
    const { x: px, y: py } = iso(0, y);
    g.poly([
      px, py,
      px + TILE_W / 2, py + TILE_H / 2,
      px + TILE_W / 2, py + TILE_H / 2 - wallH,
      px, py - wallH,
    ]).fill({ color: 0x242b3d });
    g.stroke({ color: 0x141822, width: 1, alpha: 0.8 });
  }
  c.addChild(g);
}

function drawDesk(c: Container, cx: number, cy: number, accent: number, isBoss: boolean) {
  const g = new Graphics();
  const w = isBoss ? 110 : 80;
  const h = isBoss ? 55 : 40;
  // desk top
  g.poly([
    cx, cy - h / 2,
    cx + w / 2, cy,
    cx, cy + h / 2,
    cx - w / 2, cy,
  ]).fill({ color: 0x3a4156 });
  g.stroke({ color: 0x0a0d14, width: 1 });
  // monitor
  g.rect(cx - 14, cy - 26, 28, 18).fill({ color: 0x0a0d14 });
  g.rect(cx - 12, cy - 24, 24, 14).fill({ color: accent, alpha: 0.85 });
  // stand
  g.rect(cx - 3, cy - 10, 6, 6).fill({ color: 0x0a0d14 });
  c.addChild(g);
}

function drawAgent(c: Container, cx: number, cy: number, color: number, name: string) {
  const g = new Graphics();
  // shadow
  g.ellipse(cx, cy + 30, 22, 7).fill({ color: 0x000000, alpha: 0.35 });
  // body
  g.roundRect(cx - 14, cy - 8, 28, 32, 6).fill({ color });
  g.stroke({ color: 0x0a0d14, width: 1 });
  // head
  g.circle(cx, cy - 18, 12).fill({ color: 0xf1d5b0 });
  g.stroke({ color: 0x0a0d14, width: 1 });
  // hair
  g.arc(cx, cy - 22, 12, Math.PI, Math.PI * 2).fill({ color: 0x2a1f1a });
  c.addChild(g);

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
}

// ---------- component ----------
interface Props {
  agents: Agent[];
  onSelect: (agentId: string) => void;
}

export function Room({ agents, onSelect }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const agentsLayerRef = useRef<Container | null>(null);

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

        // center the room
        const recenter = () => {
          world.x = app.renderer.width / 2;
          world.y = app.renderer.height / 2 - 120;
        };
        recenter();
        window.addEventListener('resize', recenter);

        drawWalls(world);
        drawFloor(world);

        const agentsLayer = new Container();
        agentsLayer.sortableChildren = true;
        world.addChild(agentsLayer);
        agentsLayerRef.current = agentsLayer;
      });
    return () => {
      cancelled = true;
      app.destroy(true, { children: true });
      appRef.current = null;
    };
  }, []);

  // redraw agents when the list changes
  useEffect(() => {
    const app = appRef.current;
    const layer = agentsLayerRef.current;
    if (!app || !layer) return;
    layer.removeChildren();

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
      drawAgent(group, x, y + TILE_H / 2 - 6, accent, agent.name);
      layer.addChild(group);
    }
  }, [agents, onSelect]);

  return <div ref={hostRef} className="absolute inset-0" />;
}
