// 말풍선 배치 — 겹치면 위로 비켜 쌓는다 (node tests/web/bubbles.test.mjs)
import assert from "node:assert/strict";
import { layoutBubbles } from "../../web/src/bubbles.js";

const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.top < b.top + b.h && b.top < a.top + a.h;
// 가까이 선 두 캐릭터의 말풍선이 원래 자리에서는 겹친다
const items = [{ x: 100, w: 300, h: 120, bottom: 400 }, { x: 180, w: 300, h: 150, bottom: 430 }, { x: 900, w: 200, h: 80, bottom: 420 }];
const out = layoutBubbles(items, 8);
for (let i = 0; i < out.length; i++) for (let j = i + 1; j < out.length; j++) assert.ok(!overlap(out[i], out[j]), `${i}·${j} 가 겹친다`);
assert.equal(out[2].top, 420 - 80, "안 겹치는 말풍선은 제자리");
assert.ok(out.every((b, i) => b.top <= items[i].bottom - items[i].h), "비켜도 위로만 간다 (캐릭터를 가리지 않게)");
console.log("ok — 말풍선 겹침 없음");
// 2) 위로만 쌓으면 화면 밖으로 나간다 — 옆으로도 비키고, 위쪽 한계(minTop)를 넘지 않는다
{
  const items = [0, 1, 2, 3].map(i => ({ x: 400 + i * 60, w: 300, h: 200, bottom: 500 - i * 40 }));
  const out = layoutBubbles(items, 8, { minTop: 0 });
  for (let i = 0; i < out.length; i++) for (let j = i + 1; j < out.length; j++) assert.ok(!overlap(out[i], out[j]), `2) ${i}·${j} 겹침`);
  assert.ok(out.every(b => b.top >= 0), `화면 위로 나가면 안 된다 (${out.map(b => b.top)})`);
  console.log("ok 2 — 옆으로도 비키고 화면 안에 둔다");
}
// 3) 이름표·몸(고정 영역)은 가리지 않는다
{
  const blocked = [{ x: 150, w: 120, h: 30, top: 330 }];
  const out = layoutBubbles([{ x: 100, w: 300, h: 100, bottom: 400 }], 8, { blocked });
  assert.ok(!overlap(out[0], blocked[0]), "이름표를 가린다");
  console.log("ok 3 — 이름표를 피한다");
}
