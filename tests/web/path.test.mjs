// 길찾기 테스트 — 캐릭터 경로가 가구 발자국을 지나지 않는다 (node tests/web/path.test.mjs)
import assert from "node:assert/strict";
import { OBSTACLES, ACTORS, WALK } from "../../web/src/config.js";
import { makeNav, blockedAt } from "../../web/src/path.js";

const nav = makeNav(OBSTACLES);
const hits = (a, b) => {                       // 선분을 촘촘히 따라가며 가구 안에 들어가는지
  const n = Math.ceil(Math.hypot(b.col - a.col, b.row - a.row) / 0.05);
  for (let i = 1; i < n; i++) {
    const p = { col: a.col + (b.col - a.col) * i / n, row: a.row + (b.row - a.row) * i / n };
    if (blockedAt(OBSTACLES, p, 0)) return p;
  }
  return null;
};
const home = r => ACTORS.find(a => a.role === r);
const trips = [];
for (const r of ["a0", "a1", "a2"]) trips.push([home(r), WALK.door], [WALK.door, home(r)], [home(r), WALK.inspHand], [WALK.inspHand, home(r)]);
trips.push([home("insp"), WALK.fax], [home("insp"), WALK.tray], [WALK.tray, home("insp")], [WALK.fax, home("insp")]);
trips.push([home("boss"), WALK.tray], [WALK.tray, WALK.fax], [WALK.fax, home("boss")], [WALK.tray, WALK.trash], [WALK.trash, home("boss")]);

let straightHits = 0;
for (const [a, b] of trips) {
  if (hits(a, b)) straightHits++;
  const path = nav.path(a, b);
  assert.ok(path.length >= 1, "경로가 있어야 한다");
  const pts = [a, ...path];
  for (let i = 0; i + 1 < pts.length; i++) {
    const h = hits(pts[i], pts[i + 1]);
    assert.equal(h, null, `(${a.col},${a.row})→(${b.col},${b.row}) 경로가 가구를 지난다 at ${JSON.stringify(h)}`);
  }
  const end = path[path.length - 1];
  assert.ok(Math.hypot(end.col - b.col, end.row - b.row) < 0.01, "목적지에 도착");
}
assert.ok(straightHits > 0, "직선으로는 가구를 지나는 경로가 실제로 있어야 이 테스트가 의미 있다");
console.log(`ok — 경로 ${trips.length}개 모두 가구를 피함 (직선이면 ${straightHits}개가 통과)`);
