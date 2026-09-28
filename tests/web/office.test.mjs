// 사무실 재연 로직 테스트 — 화면 없이 Office 만 돌린다 (node tests/web/office.test.mjs)
import assert from "node:assert/strict";
import { Office } from "../../web/src/office.js";

function run(n, stopEvery, human = []) {
  const o = new Office(), started = [];
  for (let i = 0; i < n; i++) {
    const code = "D" + i;
    o.push({ type: "judged", code, analyst: 0, name: "상품" + i, qty: 10, signal: "평소", reason: "이유" });
    o.push(i % stopEvery === 0 ? { type: "queued", code, flags: ["C2"], texts: ["발주량 > 2배"] } : { type: "sent", code, by: "auto" });
  }
  for (const e of human) o.push(e);
  const origSchedule = o.schedule.bind(o);
  o.schedule = () => { origSchedule(); for (const c of o.order) { const d = o.docs.get(c); if (d.stage !== "door" && !started.includes(c)) started.push(c); } };
  let t = 0;
  while (!o.idle() && t < 3_600_000) { o.tick(50); t += 50; }
  return { o, started, t };
}

// 1) 12건 중 4건(0,3,6,9) 멈춤 → 결재함 4 · 팩스 8, 5건 묶음 순서 지킴
{
  const { o, started, t } = run(12, 3);
  assert.equal(o.counts.pending, 4); assert.equal(o.counts.sent, 8);
  assert.ok(o.idle(), "끝나야 한다");
  const firstOfWave2 = started.indexOf("D5");
  assert.ok(started.slice(0, firstOfWave2).length >= 5, "두 번째 묶음은 첫 묶음 5건이 모두 시작된 뒤에");
  assert.ok(t < 600_000, `12건이 10분 안에 끝나야 한다 (실제 ${t / 1000}s)`);
  console.log(`ok 1 — 12건 ${Math.round(t / 1000)}초(1배속), 결재함 ${o.counts.pending}·팩스 ${o.counts.sent}`);
}
// 2) 팀장 승인·반려: 결재함에서 꺼내 팩스/휴지통으로
{
  const { o } = run(6, 3, [{ type: "sent", code: "D0", by: "human", action: "approve" }, { type: "rejected", code: "D3", reason: "재고 충분" }]);
  assert.equal(o.counts.pending, 0); assert.equal(o.counts.sent, 5); assert.equal(o.counts.rejected, 1);
  console.log("ok 2 — 팀장 승인 1·반려 1 반영");
}
// 3) skip 은 즉시 끝낸다
{
  const o = new Office();
  for (let i = 0; i < 20; i++) { o.push({ type: "judged", code: "S" + i, name: "x", qty: 1 }); o.push({ type: "sent", code: "S" + i, by: "auto" }); }
  o.skip(); assert.ok(o.idle()); assert.equal(o.counts.sent, 20);
  console.log("ok 3 — skip");
}
