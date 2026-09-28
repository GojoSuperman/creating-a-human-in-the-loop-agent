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
  // 결재함에 남은 건이 있으면 팀장은 결재함 앞에서 사람을 기다린다 — 흐름이 끝나고 모두 멈추면 종료
  const settled = () => o.flowDone() && !o.bossJobs.length && Object.values(o.actors).every(a => !a.busy());
  while (!settled() && t < 3_600_000) { o.tick(50); t += 50; }
  return { o, started, t };
}

// 1) 12건 중 4건(0,3,6,9) 멈춤 → 결재함 4 · 팩스 8, 5건 묶음 순서 지킴
{
  const { o, started, t } = run(12, 3);
  assert.equal(o.counts.pending, 4); assert.equal(o.counts.sent, 8);
  assert.ok(o.flowDone(), "흐름이 끝나야 한다"); assert.ok(o.reviewing, "결재함에 4건 남음 → 팀장이 열고 기다린다");
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
// 4) 결재함이 5건 쌓이면 팀장이 가서 연다 → 결재하면 나르고 돌아온다 → 비면 자리로 가며 닫는다
{
  const o = new Office(), log = [];
  o.onOpen = () => log.push("open"); o.onClose = () => log.push("close");
  for (let i = 0; i < 10; i++) {                  // 10건 중 짝수 5건이 멈춤
    const code = "B" + i;
    o.push({ type: "judged", code, name: "x", qty: 1 });
    o.push(i % 2 === 0 ? { type: "queued", code, flags: ["C2"], texts: ["t"] } : { type: "sent", code, by: "auto" });
  }
  let t = 0;
  while (!o.reviewing && t < 3_600_000) { o.tick(50); t += 50; }
  assert.equal(log[0], "open", "5건 쌓이면 연다");
  while (o.actors.boss.busy() && t < 3_600_000) { o.tick(50); t += 50; }
  const home = p => Math.hypot(o.actors.boss.pos.col - 11.2, o.actors.boss.pos.row - 2.65) < 0.01;
  assert.ok(home(), "패널을 연 뒤 팀장은 자리로 돌아간다");
  for (let i = 0; i < 10; i += 2) { o.fetch("B" + i); o.push({ type: "sent", code: "B" + i, by: "human", action: "approve" }); }
  while (!o.idle() && t < 3_600_000) { o.tick(50); t += 50; }
  assert.deepEqual(log, ["open", "close"]); assert.equal(o.counts.pending, 0); assert.equal(o.counts.sent, 10);
  assert.ok(Math.hypot(o.actors.boss.pos.col - 11.2, o.actors.boss.pos.row - 2.65) < 0.01, "다 끝나면 자리로");
  console.log("ok 4 — 팀장이 5건에서 결재함을 열고, 비면 닫고 돌아감");
}
// 5) 5건 미만이어도 '지금 보러 가기'(openNow) 하면 연다
{
  const o = new Office(); let opened = false; o.onOpen = () => (opened = true);
  o.push({ type: "judged", code: "N0", name: "x", qty: 1 }); o.push({ type: "queued", code: "N0", flags: ["C2"], texts: ["t"] });
  for (let t = 0; t < 120_000 && !o.counts.pending; t += 50) o.tick(50);
  o.openNow();
  for (let t = 0; t < 120_000 && !opened; t += 50) o.tick(50);
  assert.ok(opened); console.log("ok 5 — 지금 보러 가기");
}
// 6) 설명란용 상태 — 묶음 번호, 단계별 건수, 지금 하는 일, 방금 일어난 일
{
  const o = new Office();
  for (let i = 0; i < 12; i++) {
    const code = "P" + i;
    o.push({ type: "judged", code, name: "상품" + i, qty: 1 });
    o.push(i === 0 ? { type: "queued", code, flags: ["C2"], texts: ["발주량 > 2배"] } : { type: "sent", code, by: "auto" });
  }
  let st = o.status();
  assert.equal(st.wave, 1); assert.equal(st.waves, 3); assert.equal(st.stage.door, 5);
  for (let t = 0; t < 4000; t += 50) o.tick(50);
  st = o.status();
  assert.ok(st.active.includes("judge"), `판단 단계가 진행 중이어야 (${st.active})`);
  assert.ok(st.doing.some(d => d.includes("분석가")), "누가 무엇을 하는지");
  while (!o.flowDone()) o.tick(50);
  for (let t = 0; t < 20000; t += 50) o.tick(50);
  st = o.status();
  assert.equal(st.stage.auto, 11); assert.equal(st.stage.human, 1);
  assert.ok(st.last && st.last.length > 0, "방금 일어난 일");
  console.log("ok 6 — 설명란 상태");
}
// 7) 새로고침한 세션 — 이벤트 없이 서버 집계만 받아도 설명란 숫자가 맞는다
{
  const o = new Office();
  o.setCounts({ pending: 15, sent: 184, rejected: 1, auto: 182 });
  const st = o.status();
  assert.equal(st.stage.auto, 182); assert.equal(st.stage.human, 15);
  console.log("ok 7 — 서버 집계로 설명란");
}
// 8) 패널에는 결재함 탁자에 '실제로 놓인' 서류만 — 서버가 앞서가도 장면 숫자와 같게
{
  const o = new Office();
  for (let i = 0; i < 10; i++) {
    const code = "T" + i;
    o.push({ type: "judged", code, name: "x", qty: 1 });
    o.push({ type: "queued", code, flags: ["C2"], texts: ["t"] });   // 서버는 10건 모두 대기
  }
  for (let t = 0; t < 20000; t += 50) o.tick(50);                   // 장면은 아직 일부만 도착
  const inTray = ["T0","T1","T2","T3","T4","T5","T6","T7","T8","T9"].filter(c => o.inTray(c));
  assert.equal(inTray.length, o.status().stage.human, "패널 건수 = 설명란 사람 결재 건수");
  assert.ok(inTray.length < 10, `아직 다 도착하지 않았다 (${inTray.length})`);
  assert.ok(o.inTray("UNKNOWN"), "재연 기록이 없는 서류(새로고침)는 결재함에 있다고 본다");
  console.log(`ok 8 — 결재함 ${inTray.length}건 = 설명란`);
}
// 9) 서류를 누르면 팀장이 가서 집어 오고(자리로), 결재 없이 닫으면 도로 갖다 놓는다
{
  const o = new Office();
  o.push({ type: "judged", code: "F0", name: "x", qty: 1 }); o.push({ type: "queued", code: "F0", flags: ["C2"], texts: ["t"] });
  let t = 0;
  while (!o.inTray("F0") && t < 600_000) { o.tick(50); t += 50; }
  while (!o.reviewing && t < 600_000) { o.tick(50); t += 50; }
  const boss = o.actors.boss, atHome = () => Math.hypot(boss.pos.col - 11.2, boss.pos.row - 2.65) < 0.01;
  while (boss.busy()) o.tick(50);
  o.fetch("F0"); o.tick(50);            // 요청은 다음 틱에 움직이기 시작한다
  let visitedTray = false;
  while (boss.busy()) { o.tick(50); if (Math.hypot(boss.pos.col - 8.1, boss.pos.row - 4.9) < 0.01) visitedTray = true; }
  assert.ok(visitedTray && atHome() && boss.carry === "F0" && !o.inTray("F0"), "집어서 자리로 돌아와 들고 있다");
  o.cancel("F0"); o.tick(50);
  while (boss.busy()) o.tick(50);
  assert.ok(o.inTray("F0") && boss.carry === null && atHome(), "도로 갖다 놓고 자리로");
  o.fetch("F0"); o.tick(50); while (boss.busy()) o.tick(50);
  o.push({ type: "rejected", code: "F0", reason: "재고 충분" });
  for (let k = 0; k < 4000 && (boss.busy() || o.bossJobs.length); k++) o.tick(50);
  assert.equal(o.counts.rejected, 1); assert.ok(atHome());
  console.log("ok 9 — 누르면 집어 오고, 닫으면 도로 두고, 결재하면 나르고 자리로");
}
