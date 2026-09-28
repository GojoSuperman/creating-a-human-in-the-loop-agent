// 말풍선 배치 — 원래 자리(캐릭터 머리 위)에 두되, 다른 말풍선·이름표·몸과 겹치면
// 옆(왼쪽·오른쪽)으로 비켜 보고, 그래도 안 되면 위로 올린다. 화면 위쪽(minTop) 밖으로는 나가지 않는다.
// 입력: [{ x, w, h, bottom }] (bottom = 원래 자리의 아래 끝). 출력: 같은 순서로 { x, w, h, top }.
const hit = (a, b, gap) => a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.top < b.top + b.h + gap && b.top < a.top + a.h + gap;

export function layoutBubbles(items, gap = 8, { blocked = [], minTop = -Infinity } = {}) {
  const placed = [], out = new Array(items.length);
  const order = items.map((b, i) => i).sort((i, j) => items[j].bottom - items[i].bottom);   // 화면 아래쪽부터
  for (const i of order) {
    const b = items[i], home = b.bottom - b.h;
    const free = r => r.top >= minTop && !placed.some(p => hit(r, p, gap)) && !blocked.some(p => hit(r, p, gap));
    // 후보: 제자리 → 옆으로 반·한 칸 → 조금씩 위로 올리며 다시 옆으로. 원래 자리에서 가까운 순.
    const cands = [];
    for (let up = 0; up <= 6; up++)
      for (const k of [0, -0.6, 0.6, -1.1, 1.1, -1.6, 1.6])
        cands.push({ x: b.x + k * b.w, w: b.w, h: b.h, top: Math.max(minTop, home - up * (b.h * 0.5 + gap)), cost: up * 2 + Math.abs(k) });
    cands.sort((p, q) => p.cost - q.cost);
    const pick = cands.find(free) || { ...cands[0] };      // 어디에도 못 두면 제자리 (겹쳐도 화면 안)
    out[i] = { x: pick.x, w: b.w, h: b.h, top: pick.top };
    placed.push(out[i]);
  }
  return out;
}
