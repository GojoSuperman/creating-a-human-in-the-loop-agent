// 렌더러 — 바닥·벽·가구·캐릭터·서류. 스프라이트 로딩·잘라내기·바닥 굽기는 Deep-research-agent 에서 가져왔다.
import { GRID, PROPS, STATIONS, WALL, ASSETS, ASSET_V, FURN, FACE, LAYER, TONE, TILE, PROP_SCALE, ACTOR_SCALE } from "./config.js";
import { foot, spriteTopLeft, depth, sceneBox } from "./iso.js";
import { allParts, drawActor, CAST } from "./actors.js";

const cache = new Map();
function load(name, dir) {
  const key = `${dir}/${name}`;
  if (cache.has(key)) return cache.get(key);
  const img = new Image();
  const p = new Promise(ok => { img.onload = () => ok(img); img.onerror = () => ok(null); })
    .then(v => (cache.set(key, v), v));
  cache.set(key, p);
  img.src = `${ASSETS}/${dir}/${name}.png?v=${ASSET_V}`;
  return p;
}
const got = (name, dir) => { const v = cache.get(`${dir}/${name}`); return v && !(v instanceof Promise) ? v : null; };

function wallItems() {
  const pick = i => (i === WALL.doorAt ? WALL.door : i === WALL.winAt ? WALL.win : WALL.wall);
  const out = [];
  for (let row = 0; row < GRID.rows; row++) out.push({ col: -1, row, layer: LAYER.WALL, flip: true, sprite: pick(row) });
  for (let col = 0; col < GRID.cols; col++) out.push({ col, row: -1, layer: LAYER.WALL, sprite: pick(col) });
  return out;
}
const propItems = () => PROPS.map(p => ({ ...p, layer: p.layer ?? LAYER.PROP, sprite: p.sprite + (p.face || FACE),
                                         scale: (p.scale ?? 1) * PROP_SCALE,
                                         dy: (p.dy || 0) * PROP_SCALE, dx: (p.dx || 0) * PROP_SCALE }));

export async function preload() {
  const names = new Set(["floorFull" + FACE, ...propItems().map(i => i.sprite), ...wallItems().map(w => w.sprite)]);
  const jobs = [...names].map(n => load(n, FURN)).concat(allParts().map(n => load(n, "characters")));
  const done = await Promise.all(jobs);
  return { total: jobs.length, missing: done.filter(x => !x).length };
}

const level = res => Math.min(1, 2 ** (Math.ceil(Math.log2(res) * 2) / 2));
const trims = new Map(), bakes = new Map();
function trimOf(img) {
  let t = trims.get(img); if (t) return t;
  const c = document.createElement("canvas"); c.width = img.width; c.height = img.height;
  const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0);
  const a = g.getImageData(0, 0, c.width, c.height).data;
  let x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++)
    if (a[(y * c.width + x) * 4 + 3]) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  t = x1 < 0 ? { x: 0, y: 0, w: 1, h: 1 } : { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
  trims.set(img, t); return t;
}
function spriteOf(img, lvl) {
  let m = bakes.get(img); if (!m) bakes.set(img, (m = new Map()));
  let c = m.get(lvl); if (c) return c;
  const t = trimOf(img);
  c = document.createElement("canvas");
  c.width = Math.max(1, Math.ceil(t.w * lvl)); c.height = Math.max(1, Math.ceil(t.h * lvl));
  const g = c.getContext("2d"); g.imageSmoothingQuality = "high";
  g.drawImage(img, t.x, t.y, t.w, t.h, 0, 0, c.width, c.height);
  m.set(lvl, c); return c;
}
let floorBake = null;
function floorLayer(res, origin, img) {
  const lvl = level(res);
  if (floorBake && floorBake.res === lvl) return floorBake;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity; const spots = [];
  for (let row = 0; row < GRID.rows; row++) for (let col = 0; col < GRID.cols; col++) {
    const p = spriteTopLeft(col, row, origin); spots.push(p);
    x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x + img.width); y1 = Math.max(y1, p.y + img.height);
  }
  const c = document.createElement("canvas");
  c.width = Math.ceil((x1 - x0) * lvl); c.height = Math.ceil((y1 - y0) * lvl);
  const g = c.getContext("2d"); g.imageSmoothingQuality = "high";
  for (const p of spots) g.drawImage(img, (p.x - x0) * lvl, (p.y - y0) * lvl, img.width * lvl, img.height * lvl);
  return (floorBake = { res: lvl, x: x0, y: y0, w: x1 - x0, h: y1 - y0, canvas: c });
}

function drawSprite(ctx, it, origin, lvl, missing) {
  const img = got(it.sprite, FURN);
  if (!img) { missing.add(it.sprite); return; }
  const p = spriteTopLeft(it.col, it.row, origin);
  const t = trimOf(img), bake = spriteOf(img, lvl);
  const x = p.x + (it.dx || 0), y = p.y + (it.dy || 0);
  // 키워도 바닥 앵커(스프라이트 가로 중앙 · 타일 중심 높이)는 제자리
  const k = it.scale || 1, ax = x + img.width / 2, ay = y + img.height - TILE.H / 2;
  const left = ax - (img.width / 2) * k, top = ay - (img.height - TILE.H / 2) * k;
  const dx = left + t.x * k, dy = top + t.y * k, w = t.w * k, h = t.h * k;
  if (it.mirror) {        // 제자리 뒤집기 — 책상 위 모니터처럼 놓인 자리는 그대로 두고 방향만
    ctx.save(); ctx.translate(dx + w, dy); ctx.scale(-1, 1);
    ctx.drawImage(bake, 0, 0, w, h); ctx.restore();
  } else if (it.flip) {   // 캔버스 기준 뒤집기 — 벽처럼 반대편 벽선으로 옮겨 가는 것
    ctx.save(); ctx.translate(left + img.width * k, top); ctx.scale(-1, 1);
    ctx.drawImage(bake, t.x * k, t.y * k, w, h); ctx.restore();
  } else ctx.drawImage(bake, dx, dy, w, h);
}

function paper(ctx, x, y, tone) {
  ctx.save();
  ctx.fillStyle = "#fff"; ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = 2;
  ctx.fillRect(x - 22, y - 28, 44, 56); ctx.strokeRect(x - 22, y - 28, 44, 56);
  ctx.fillStyle = TONE[tone] || TONE.plain; ctx.fillRect(x - 22, y - 28, 44, 10);
  ctx.fillStyle = "rgba(0,0,0,.25)";
  for (let i = 0; i < 3; i++) ctx.fillRect(x - 14, y - 8 + i * 10, 28, 3);
  ctx.restore();
}

function tag(ctx, x, y, text, size = 23) {
  ctx.font = `bold ${size}px sans-serif`; ctx.textAlign = "center";
  ctx.lineWidth = 6; ctx.strokeStyle = "rgba(255,255,255,.92)"; ctx.strokeText(text, x, y);
  ctx.fillStyle = "#1a1a1a"; ctx.fillText(text, x, y);
}

// 말풍선 — 줄바꿈(\n)을 지키고, 가장 긴 줄에 폭을 맞춘다
function bubble(ctx, x, y, text) {
  ctx.save(); ctx.font = "22px sans-serif"; ctx.textAlign = "center";
  const lines = String(text).split("\n").slice(0, 4), lh = 28, pad = 12;
  const w = Math.max(...lines.map(l => ctx.measureText(l).width)) + pad * 2, h = lines.length * lh + 12;
  const top = y - h - 10;
  ctx.fillStyle = "rgba(255,255,255,.96)"; ctx.strokeStyle = "rgba(0,0,0,.22)"; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.roundRect(x - w / 2, top, w, h, 10); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x - 9, top + h); ctx.lineTo(x, top + h + 10); ctx.lineTo(x + 9, top + h); ctx.fill();  // 꼬리
  ctx.fillStyle = "#1a1a1a";
  lines.forEach((l, i) => { ctx.font = i === 0 ? "bold 22px sans-serif" : "22px sans-serif"; ctx.fillText(l, x, top + 8 + lh * (i + 0.75)); });
  ctx.restore();
}

function paint(ctx, frame, res, props = true) {
  const box = sceneBox(), o = box.origin, lvl = level(res), missing = new Set();
  const floorImg = got("floorFull" + FACE, FURN);
  if (floorImg) { const f = floorLayer(res, o, floorImg); ctx.drawImage(f.canvas, f.x, f.y, f.w, f.h); }
  else missing.add("floorFull" + FACE);
  const items = (props ? propItems() : []).concat(wallItems()).sort((a, b) => depth(a.col, a.row, a.layer) - depth(b.col, b.row, b.layer));
  for (const it of items) drawSprite(ctx, it, o, lvl, missing);

  if (!props) return { box, missing: [...missing] };   // 빈 방 — 배치 설계용
  // 쌓인 서류 — 결재함·팩스·휴지통
  const pile = (key, n, tone) => {
    const s = STATIONS[key], f = foot(s.col, s.row, o);
    for (let i = 0; i < Math.min(n, 10); i++) paper(ctx, f.x + (i % 2) * 3, f.y + s.lift - i * 6, tone);
    if (n) tag(ctx, f.x + 40, f.y + s.lift - 40, String(n), 26);
  };
  pile("tray", frame.piles.tray, "stop"); pile("fax", frame.piles.fax, "auto"); pile("trash", frame.piles.trash, "stop");
  if (frame.piles.inbox) pile("inbox", frame.piles.inbox, "plain");       // 문 앞에 들어온 이번 묶음
  if (frame.piles.inspect) pile("inspect", frame.piles.inspect, "plain"); // 검사관 앞에 건네진 서류

  const cast = [...frame.actors].sort((a, b) => a.col + a.row - (b.col + b.row));
  for (const a of cast) {
    const f = foot(a.col, a.row, o);
    drawActor(ctx, n => got(n, "characters"), a.role, a.state, f.x, f.y, ACTOR_SCALE);
    if (a.carry) paper(ctx, f.x, f.y - 118 * ACTOR_SCALE, "plain");      // 머리 위로 든 서류
  }
  for (const p of frame.papers) { const f = foot(p.col, p.row, o); paper(ctx, f.x, f.y + p.lift, p.tone); }

  for (const s of Object.values(STATIONS)) if (s.name) { const f = foot(s.col, s.row, o); tag(ctx, f.x, f.y - 150, s.name); }
  const cab = STATIONS.cabinet, cf = foot(cab.col, cab.row, o);
  tag(ctx, cf.x, cf.y - 120, `보관 중 ${frame.cabinet}건`, 21);
  for (const a of frame.actors) {
    const f = foot(a.col, a.row, o);
    tag(ctx, f.x, f.y - 122, CAST[a.role]?.label || a.role, 20);
    if (a.say) bubble(ctx, f.x, f.y - 140, a.say);
  }
  return { box, missing: [...missing] };
}

/** 격자 눈금 — 배치를 칸 좌표로 말하기 위한 자 (개발용, G 키) */
function drawGrid(ctx, origin) {
  ctx.save(); ctx.font = "bold 18px sans-serif"; ctx.textAlign = "center";
  for (let row = 0; row < GRID.rows; row++) for (let col = 0; col < GRID.cols; col++) {
    const f = foot(col, row, origin);
    ctx.beginPath();
    ctx.moveTo(f.x, f.y - TILE.H / 2); ctx.lineTo(f.x + TILE.W / 2, f.y);
    ctx.lineTo(f.x, f.y + TILE.H / 2); ctx.lineTo(f.x - TILE.W / 2, f.y); ctx.closePath();
    ctx.strokeStyle = "rgba(200,40,40,.5)"; ctx.lineWidth = 2; ctx.stroke();
    ctx.lineWidth = 4; ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.strokeText(`${col},${row}`, f.x, f.y + 6);
    ctx.fillStyle = "#b02020"; ctx.fillText(`${col},${row}`, f.x, f.y + 6);
  }
  ctx.restore();
}

export function draw(canvas, view) {
  const { scale = 0.45, pan = { x: 0, y: 0 }, frame, grid = false, props = true } = view;
  const ctx = canvas.getContext("2d"), dpr = window.devicePixelRatio || 1;
  const vw = canvas.clientWidth, vh = canvas.clientHeight;
  if (!vw || !vh) return { box: sceneBox(), missing: [] };   // 탭이 가려져 크기가 0 — 그리지 않는다
  if (canvas.width !== vw * dpr || canvas.height !== vh * dpr) { canvas.width = vw * dpr; canvas.height = vh * dpr; }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, vw, vh);
  ctx.save(); ctx.translate(pan.x, pan.y); ctx.scale(scale, scale);
  const r = paint(ctx, frame, scale * dpr, props);
  if (grid) drawGrid(ctx, sceneBox().origin);
  ctx.restore(); return r;
}

export function fitView(canvas) {
  const box = sceneBox(), vw = canvas.clientWidth, vh = canvas.clientHeight;
  const scale = Math.max(Math.min(vw / box.width, vh / box.height) * 0.995, 0.01);
  return { scale, pan: { x: (vw - box.width * scale) / 2, y: (vh - box.height * scale) / 2 } };
}
