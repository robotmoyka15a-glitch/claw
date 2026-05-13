import { useEffect, useRef } from 'react';
import {
  Application, Container, Graphics, Text, TextStyle, Ticker,
  BlurFilter
} from 'pixi.js';
import type { Agent, AgentState, SystemSnapshot } from '../api';

/* ═══════════════════════════════════════════════════════════════════
   Изометрическая комната — полный редизайн
   • Ковёр в центре зала
   • Книжная полка на левой стене
   • Пара растений в углах
   • Свечение от каждой лампы (glow-halo)
   • CPU-живопись на задней стене с рамкой
   • Улучшенные аватары агентов с тенями
   • Плавающие частицы пыли
═══════════════════════════════════════════════════════════════════ */

const TILE_W = 100;
const TILE_H = 50;

const iso = (gx: number, gy: number) => ({
  x: (gx - gy) * (TILE_W / 2),
  y: (gx + gy) * (TILE_H / 2),
});

const COLS = 8;
const ROWS = 8;
const WALL_H = 140;

const DESK_SLOTS: Record<string, { gx: number; gy: number; kind: 'boss' | 'side' }> = {
  center:      { gx: 4, gy: 4, kind: 'boss' },
  left:        { gx: 1, gy: 4, kind: 'side' },
  right:       { gx: 7, gy: 4, kind: 'side' },
  back_left:   { gx: 2, gy: 1, kind: 'side' },
  back_right:  { gx: 6, gy: 1, kind: 'side' },
  spare:       { gx: 4, gy: 7, kind: 'side' },
};

// ── цветовая палитра ──────────────────────────────────────────────
const C = {
  bg:          0x060910,
  floor1:      0x0e1520,
  floor2:      0x121c2c,
  floorEdge:   0x060910,
  wall_left:   0x111827,
  wall_right:  0x0d1421,
  wallEdge:    0x060910,
  carpet:      0x1a0d2e,
  carpetBorder:0x2d1a4a,
  deskTop:     0x1e2d42,
  deskSide:    0x16222f,
  deskLeg:     0x0f1a26,
  monBorder:   0x0a0d14,
  monGlow:     0x00e5ff,
  chairBack:   0x1a2840,
  chairSeat:   0x162030,
  shelfWood:   0x2a1f0e,
  shelfBook1:  0x7c1d1d,
  shelfBook2:  0x1d4e7c,
  shelfBook3:  0x1d7c3b,
  shelfBook4:  0x7c6a1d,
  plant1:      0x16532a,
  plant2:      0x1c6e35,
  plantPot:    0x5a3a1a,
  lamp_pole:   0x2a3548,
  lamp_shade:  0x1e2e42,
  shadow:      0x000000,
  skinLight:   0xf1d5b0,
  hairDark:    0x1a1208,
  particleCol: 0xffffff,
};

// ═══════════════════════ draw helpers ═══════════════════════════════

function drawFloor(c: Container) {
  const g = new Graphics();
  for (let gy = 0; gy < ROWS; gy++) {
    for (let gx = 0; gx < COLS; gx++) {
      const { x, y } = iso(gx, gy);
      const col = (gx + gy) % 2 === 0 ? C.floor1 : C.floor2;
      g.poly([
        x,            y,
        x + TILE_W/2, y + TILE_H/2,
        x,            y + TILE_H,
        x - TILE_W/2, y + TILE_H/2,
      ]).fill({ color: col });
      g.stroke({ color: C.floorEdge, width: 1, alpha: 0.6 });
    }
  }
  c.addChild(g);
}

function drawWalls(c: Container) {
  const g = new Graphics();
  // ── левая стена (вдоль x=0, вверх) ──
  for (let gy = 0; gy < ROWS; gy++) {
    const { x, y } = iso(0, gy);
    g.poly([
      x,            y,
      x + TILE_W/2, y + TILE_H/2,
      x + TILE_W/2, y + TILE_H/2 - WALL_H,
      x,            y - WALL_H,
    ]).fill({ color: C.wall_right });
    g.stroke({ color: C.wallEdge, width: 1, alpha: 0.7 });
  }
  // ── задняя стена (вдоль gy=0, вверх) ──
  for (let gx = 0; gx < COLS; gx++) {
    const { x, y } = iso(gx, 0);
    g.poly([
      x - TILE_W/2, y + TILE_H/2,
      x,            y,
      x,            y - WALL_H,
      x - TILE_W/2, y + TILE_H/2 - WALL_H,
    ]).fill({ color: C.wall_left });
    g.stroke({ color: C.wallEdge, width: 1, alpha: 0.7 });
  }
  c.addChild(g);
}

/** Ковёр в центре зала */
function drawCarpet(c: Container) {
  const g = new Graphics();
  const corners = [
    iso(2, 2), iso(6, 2), iso(6, 6), iso(2, 6)
  ];
  g.poly([
    corners[0].x, corners[0].y,
    corners[1].x, corners[1].y,
    corners[2].x, corners[2].y,
    corners[3].x, corners[3].y,
  ]).fill({ color: C.carpet, alpha: 0.75 });
  // рамка ковра
  g.stroke({ color: C.carpetBorder, width: 3, alpha: 0.5 });
  c.addChild(g);
}

/** Книжная полка на левой стене */
function drawBookshelf(c: Container, baseX: number, baseY: number) {
  const g = new Graphics();
  const w = 80, h = 60, depth = 12;
  // задняя стенка
  g.rect(baseX - w/2, baseY - h, w, h).fill({ color: C.shelfWood });
  // полки
  for (let i = 0; i <= 2; i++) {
    const sy = baseY - (i * 20);
    g.rect(baseX - w/2, sy - 3, w, 3).fill({ color: C.shelfWood, alpha: 0.85 });
  }
  // книги на верхней полке
  const bookColors = [C.shelfBook1, C.shelfBook2, C.shelfBook3, C.shelfBook4, C.shelfBook2];
  let bx = baseX - w/2 + 4;
  for (const col of bookColors) {
    const bw = 10 + Math.random() * 6 | 0;
    g.rect(bx, baseY - 58, bw, 18).fill({ color: col });
    bx += bw + 2;
  }
  c.addChild(g);
}

/** Декоративное растение */
function drawPlant(c: Container, cx: number, cy: number, scale = 1) {
  const g = new Graphics();
  // горшок
  g.poly([cx - 8*scale, cy, cx + 8*scale, cy, cx + 6*scale, cy + 14*scale, cx - 6*scale, cy + 14*scale])
    .fill({ color: C.plantPot });
  // трава/листья
  for (let i = -2; i <= 2; i++) {
    const lx = cx + i * 6 * scale;
    const lh = (16 + Math.abs(i) * 2) * scale;
    g.poly([lx - 4*scale, cy, lx, cy - lh, lx + 4*scale, cy])
      .fill({ color: i % 2 === 0 ? C.plant2 : C.plant1, alpha: 0.9 });
  }
  c.addChild(g);
}

/** Рабочий стол + монитор */
function drawDesk(c: Container, cx: number, cy: number, accent: number, isBoss: boolean) {
  const g = new Graphics();
  const dw = isBoss ? 120 : 88;
  const dh = isBoss ? 56 : 42;

  // тень под столом
  const shadow = new Graphics();
  shadow.ellipse(cx, cy + 10, dw * 0.55, dh * 0.3).fill({ color: C.shadow, alpha: 0.35 });
  c.addChild(shadow);

  // столешница
  g.poly([cx, cy - dh/2, cx + dw/2, cy, cx, cy + dh/2, cx - dw/2, cy])
    .fill({ color: C.deskTop });
  g.stroke({ color: C.deskSide, width: 1 });

  // ноги стола (2 передних)
  const legH = 16;
  g.rect(cx - dw/2 + 8, cy + dh/2 - 2, 5, legH).fill({ color: C.deskLeg });
  g.rect(cx + dw/2 - 13, cy + dh/2 - 2, 5, legH).fill({ color: C.deskLeg });

  // монитор — рамка
  const mw = isBoss ? 32 : 24;
  const mh = isBoss ? 22 : 18;
  g.rect(cx - mw/2, cy - dh/2 - mh - 10, mw, mh).fill({ color: C.monBorder });
  g.stroke({ color: accent, width: 1, alpha: 0.6 });
  // экран с лёгким свечением акцентного цвета
  g.rect(cx - mw/2 + 2, cy - dh/2 - mh - 8, mw - 4, mh - 4).fill({ color: accent, alpha: 0.75 });
  // подставка
  g.rect(cx - 4, cy - dh/2 - 10, 8, 8).fill({ color: C.deskLeg });

  c.addChild(g);
}

/** Лампа → возвращает объект bulb для анимации */
function drawLamp(c: Container, cx: number, cy: number, color: number) {
  const g = new Graphics();
  const px = cx + 20, py = cy - 8;
  // штанга
  g.rect(px, py - 42, 3, 38).fill({ color: C.lamp_pole });
  // абажур
  g.poly([px - 10, py - 44, px + 13, py - 44, px + 17, py - 34, px - 14, py - 34])
    .fill({ color: C.lamp_shade });
  c.addChild(g);

  // glow halo (большой полупрозрачный круг = свечение)
  const halo = new Graphics();
  halo.circle(px + 1, py - 30, 22).fill({ color, alpha: 0.07 });
  c.addChild(halo);

  // bulb
  const bulb = new Graphics();
  bulb.circle(px + 1, py - 32, 4).fill({ color, alpha: 0.9 });
  c.addChild(bulb);

  return { bulb, halo };
}

/** Персонаж-агент */
function drawAvatar(c: Container, cx: number, cy: number, color: number, name: string) {
  const body = new Graphics();
  // напольная тень
  body.ellipse(cx, cy + 28, 20, 7).fill({ color: C.shadow, alpha: 0.4 });
  // стул — спинка
  body.roundRect(cx - 12, cy - 4, 24, 28, 4).fill({ color: C.chairBack });
  // стул — сиденье
  body.rect(cx - 13, cy + 16, 26, 6).fill({ color: C.chairSeat });
  // тело персонажа
  body.roundRect(cx - 11, cy - 10, 22, 26, 5).fill({ color });
  body.stroke({ color: C.monBorder, width: 1, alpha: 0.5 });
  // голова
  body.circle(cx, cy - 20, 11).fill({ color: C.skinLight });
  body.stroke({ color: C.monBorder, width: 1, alpha: 0.4 });
  // волосы
  body.arc(cx, cy - 24, 11, Math.PI + 0.1, Math.PI * 2 - 0.1).fill({ color: C.hairDark });
  c.addChild(body);

  const label = new Text({
    text: name,
    style: new TextStyle({
      fontFamily: 'Inter, system-ui',
      fontSize: 10,
      fontWeight: '600',
      fill: 0xdde4f0,
      align: 'center',
      stroke: { color: 0x000000, width: 3 },
      dropShadow: { distance: 0, blur: 4, color: 0x000000, alpha: 0.8 },
    }),
  });
  label.anchor.set(0.5, 1);
  label.x = cx;
  label.y = cy - 34;
  c.addChild(label);

  return { body };
}

/** Пузырь над агентом */
function createBubble(cx: number, cy: number) {
  const ct = new Container();
  ct.x = cx; ct.y = cy - 60;
  ct.visible = false;

  const bg = new Graphics();
  ct.addChild(bg);

  const txt = new Text({
    text: '',
    style: new TextStyle({
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 9,
      fill: 0x0a0d14,
      align: 'center',
    }),
  });
  txt.anchor.set(0.5, 0.5);
  ct.addChild(txt);

  const redraw = (msg: string, color: number) => {
    txt.text = msg;
    const p = 5, w = txt.width + p * 2, h = txt.height + p * 2;
    bg.clear();
    bg.roundRect(-w/2, -h/2, w, h, 5).fill({ color });
    bg.stroke({ color: 0x000000, width: 1, alpha: 0.4 });
    bg.poly([-4, h/2, 4, h/2, 0, h/2 + 5]).fill({ color });
  };

  return { ct, redraw };
}

/** CPU-картина на задней стене */
function createCpuPainting(world: Container) {
  const { x: ax, y: ay } = iso(4, 0);
  const painting = new Container();
  painting.x = ax;
  painting.y = ay - WALL_H + 18;
  world.addChild(painting);

  const FW = 150, FH = 70;

  // рамка с тенью
  const frame = new Graphics();
  frame.rect(-FW/2 - 6, -FH/2 - 20, FW + 12, FH + 14).fill({ color: 0x0e1a26 });
  frame.stroke({ color: 0xf5b301, width: 2, alpha: 0.5 });
  painting.addChild(frame);

  // матовый фон экрана
  const bg = new Graphics();
  bg.rect(-FW/2, -FH/2 - 14, FW, FH).fill({ color: 0x06090e });
  painting.addChild(bg);

  const inner = new Graphics();
  painting.addChild(inner);

  // заголовок
  const title = new Text({
    text: 'CPU MONITOR',
    style: new TextStyle({
      fontFamily: 'JetBrains Mono', fontSize: 8,
      fill: 0xf5b301, letterSpacing: 2,
    }),
  });
  title.x = -FW/2; title.y = -FH/2 - 26;
  painting.addChild(title);

  let samples: number[] = [];
  const MAX = 36;

  const push = (cpu: number) => {
    samples = [...samples.slice(-(MAX - 1)), Math.max(0, Math.min(100, cpu))];
    inner.clear();
    const barW = FW / MAX;
    samples.forEach((v, i) => {
      const bh = (v / 100) * (FH - 6);
      const bx = -FW/2 + i * barW;
      const by = FH/2 - 14 - bh;
      const col = v > 85 ? 0xef4444 : v > 55 ? 0xf5b301 : 0x00e5ff;
      inner.rect(bx + 1, by, barW - 2, bh).fill({ color: col, alpha: 0.85 });
    });
  };

  return { push };
}

/** Плавающие пылинки */
function createParticles(world: Container, count = 28) {
  const particles: { g: Graphics; x: number; y: number; vx: number; vy: number; life: number; maxLife: number }[] = [];

  const { x: cx, y: cy } = iso(4, 4);
  for (let i = 0; i < count; i++) {
    const g = new Graphics();
    g.circle(0, 0, 1).fill({ color: C.particleCol, alpha: 0.0 });
    world.addChild(g);
    particles.push({
      g,
      x: cx + (Math.random() - 0.5) * 500,
      y: cy + (Math.random() - 0.5) * 300,
      vx: (Math.random() - 0.5) * 0.25,
      vy: -Math.random() * 0.18 - 0.05,
      life: Math.random() * 200,
      maxLife: 180 + Math.random() * 120,
    });
  }

  const tick = () => {
    for (const p of particles) {
      p.life++;
      p.x += p.vx;
      p.y += p.vy;
      if (p.life > p.maxLife) {
        p.life = 0;
        const { x: ox, y: oy } = iso(4, 4);
        p.x = ox + (Math.random() - 0.5) * 500;
        p.y = oy + 100 + Math.random() * 100;
      }
      const t = p.life / p.maxLife;
      const alpha = Math.sin(t * Math.PI) * 0.22;
      p.g.x = p.x;
      p.g.y = p.y;
      p.g.clear().circle(0, 0, 1).fill({ color: C.particleCol, alpha });
    }
  };

  return { tick };
}

// ═══════════════════════ Component ══════════════════════════════════

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
  halo: Graphics;
  bubble: ReturnType<typeof createBubble>;
  agentId: string;
}

export function Room({ agents, states, snapshot, onSelect }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const agentsLayerRef = useRef<Container | null>(null);
  const visualsRef = useRef<Map<string, AgentVisual>>(new Map());
  const cpuPaintingRef = useRef<{ push: (v: number) => void } | null>(null);
  const tickerRef = useRef<((t: Ticker) => void) | null>(null);

  // актуальные состояния без stale-closure
  const statesRef = useRef<Record<string, AgentState>>(states);
  useEffect(() => { statesRef.current = states; }, [states]);

  // Pixi init
  useEffect(() => {
    let cancelled = false;
    const el = hostRef.current!;
    const app = new Application();

    app.init({ resizeTo: el, background: C.bg, antialias: true, resolution: window.devicePixelRatio ?? 1 })
      .then(() => {
        if (cancelled) return;
        el.appendChild(app.canvas);
        appRef.current = app;

        const world = new Container();
        app.stage.addChild(world);

        const recenter = () => {
          world.x = app.renderer.width / 2;
          world.y = app.renderer.height * 0.42;
        };
        recenter();
        window.addEventListener('resize', recenter);

        // ── строим сцену ──
        drawWalls(world);
        drawFloor(world);
        drawCarpet(world);

        // книжная полка на левой стене
        const { x: shX, y: shY } = iso(0, 3);
        drawBookshelf(world, shX + TILE_W/2, shY - WALL_H + 80);

        // растения
        const plantSlots = [iso(0, 7), iso(7, 0)];
        for (const s of plantSlots) {
          drawPlant(world, s.x, s.y - 20, 1.1);
        }

        cpuPaintingRef.current = createCpuPainting(world);

        const agentsLayer = new Container();
        agentsLayer.sortableChildren = true;
        world.addChild(agentsLayer);
        agentsLayerRef.current = agentsLayer;

        // частицы сверху
        const { tick: particleTick } = createParticles(world, 30);

        // тикер
        const tick = (_t: Ticker) => {
          particleTick();
          const time = performance.now() / 1000;
          visualsRef.current.forEach((v, agentId) => {
            const st = statesRef.current[agentId];
            const status = st?.status ?? 'idle';
            if (status === 'thinking') {
              v.body.y = Math.sin(time * 3.2) * 1.8;
              v.bulb.alpha = 0.65 + 0.35 * Math.abs(Math.sin(time * 3));
              v.halo.alpha = 0.06 + 0.1 * Math.abs(Math.sin(time * 1.5));
              v.bulb.scale.set(1 + 0.25 * Math.abs(Math.sin(time * 3)));
            } else if (status === 'tool') {
              v.body.y = Math.sin(time * 9) * 2.2;
              v.bulb.alpha = 0.4 + 0.6 * Math.abs(Math.sin(time * 6));
              v.halo.alpha = 0.08 + 0.14 * Math.abs(Math.sin(time * 4));
              v.bulb.scale.set(1 + 0.4 * Math.abs(Math.sin(time * 6)));
            } else {
              v.body.y = 0;
              v.bulb.alpha = 0.4;
              v.halo.alpha = 0.04;
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
  }, []); // eslint-disable-line

  // Перерисовка агентов
  useEffect(() => {
    const layer = agentsLayerRef.current;
    if (!layer) return;
    layer.removeChildren();
    visualsRef.current.clear();

    for (const agent of agents) {
      const slot = DESK_SLOTS[agent.desk] ?? DESK_SLOTS.spare;
      const { x, y } = iso(slot.gx, slot.gy);
      const cy = y + TILE_H / 2;
      const accent = parseInt(agent.color.replace('#', ''), 16);

      const group = new Container();
      group.zIndex = y;
      group.eventMode = 'static';
      group.cursor = 'pointer';
      group.on('pointerover', () => { group.alpha = 0.88; });
      group.on('pointerout',  () => { group.alpha = 1; });
      group.on('pointerdown', () => onSelect(agent.id));

      drawDesk(group, x, cy, accent, slot.kind === 'boss');
      const { bulb, halo } = drawLamp(group, x, cy, accent);
      const { body } = drawAvatar(group, x, cy - 8, accent, agent.name);
      const { ct, redraw } = createBubble(x, cy - 8);
      group.addChild(ct);

      layer.addChild(group);
      visualsRef.current.set(agent.id, { group, body, bulb, halo, bubble: { ct, redraw }, agentId: agent.id });
    }
  }, [agents, onSelect]);

  // Пузыри статуса
  useEffect(() => {
    visualsRef.current.forEach((v, agentId) => {
      const st = states[agentId];
      if (!st || st.status === 'idle') { v.bubble.ct.visible = false; return; }
      v.bubble.ct.visible = true;
      if (st.status === 'thinking') v.bubble.redraw('думает…', 0xf5b301);
      else if (st.status === 'tool') v.bubble.redraw(st.last_tool ?? 'инструмент…', 0x00e5ff);
    });
  }, [states]);

  // CPU в картину
  useEffect(() => {
    if (snapshot && cpuPaintingRef.current) cpuPaintingRef.current.push(snapshot.cpu_percent);
  }, [snapshot]);

  return <div ref={hostRef} className="absolute inset-0" />;
}
