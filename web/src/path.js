// 길찾기 — 가구 발자국을 피해 걷는 경로 (A*, 0.25칸 격자, 꺾이는 곳만 남김)
import { GRID } from "./config.js";

const RES = 0.25, PAD = 0.2;                 // 격자 간격, 캐릭터 몸 반폭(가구에서 띄울 거리)

export function blockedAt(obs, p, pad = PAD) {
  return obs.some(o => p.col > o.c0 - pad && p.col < o.c1 + pad && p.row > o.r0 - pad && p.row < o.r1 + pad);
}

export function makeNav(obs) {
  const c0 = -0.5, r0 = -0.5, W = Math.round((GRID.cols) / RES) + 1, H = Math.round((GRID.rows) / RES) + 1;
  const at = (i, j) => ({ col: c0 + i * RES, row: r0 + j * RES });
  const free = new Uint8Array(W * H);
  for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) free[j * W + i] = blockedAt(obs, at(i, j)) ? 0 : 1;
  const cellOf = p => [Math.min(W - 1, Math.max(0, Math.round((p.col - c0) / RES))), Math.min(H - 1, Math.max(0, Math.round((p.row - r0) / RES)))];
  const nearestFree = ([i, j]) => {
    if (free[j * W + i]) return [i, j];
    for (let d = 1; d < Math.max(W, H); d++)
      for (let dj = -d; dj <= d; dj++) for (let di = -d; di <= d; di++) {
        const x = i + di, y = j + dj;
        if (x >= 0 && y >= 0 && x < W && y < H && free[y * W + x]) return [x, y];
      }
    return [i, j];
  };
  const clear = (a, b) => {                 // 두 점 사이가 가구(여유 포함)에 막히지 않는가
    const n = Math.ceil(Math.hypot(b.col - a.col, b.row - a.row) / (RES / 3));
    for (let k = 1; k < n; k++) if (blockedAt(obs, { col: a.col + (b.col - a.col) * k / n, row: a.row + (b.row - a.row) * k / n })) return false;
    return true;
  };

  function path(from, to) {
    if (clear(from, to)) return [{ ...to }];
    const [si, sj] = nearestFree(cellOf(from)), [gi, gj] = nearestFree(cellOf(to));
    const key = (i, j) => j * W + i, g = new Float32Array(W * H).fill(Infinity), prev = new Int32Array(W * H).fill(-1);
    const open = [[0, si, sj]]; g[key(si, sj)] = 0;
    const h = (i, j) => Math.hypot(i - gi, j - gj);
    while (open.length) {
      let bi = 0; for (let k = 1; k < open.length; k++) if (open[k][0] < open[bi][0]) bi = k;
      const [, i, j] = open.splice(bi, 1)[0];
      if (i === gi && j === gj) break;
      for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
        if (!di && !dj) continue;
        const x = i + di, y = j + dj;
        if (x < 0 || y < 0 || x >= W || y >= H || !free[key(x, y)]) continue;
        if (di && dj && (!free[key(i + di, j)] || !free[key(i, j + dj)])) continue;   // 모서리를 비스듬히 자르지 않는다
        const ng = g[key(i, j)] + Math.hypot(di, dj);
        if (ng < g[key(x, y)]) { g[key(x, y)] = ng; prev[key(x, y)] = key(i, j); open.push([ng + h(x, y), x, y]); }
      }
    }
    const cells = [];
    for (let k = key(gi, gj); k !== -1; k = prev[k]) cells.unshift(at(k % W, Math.floor(k / W)));
    if (!cells.length || prev[key(gi, gj)] === -1 && (gi !== si || gj !== sj)) return [{ ...to }];   // 길이 없으면 직선
    // 꺾이는 곳만 남긴다 (앞에서 보이는 가장 먼 점으로 건너뛰기)
    const pts = [from, ...cells, to], out = [];
    let a = 0;
    while (a < pts.length - 1) {
      let b = pts.length - 1;
      while (b > a + 1 && !clear(pts[a], pts[b])) b--;
      out.push({ col: pts[b].col, row: pts[b].row }); a = b;
    }
    return out;
  }
  return { path };
}
