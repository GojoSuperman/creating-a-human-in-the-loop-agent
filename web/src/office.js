// 사무실 장면 상태 — 캐릭터가 서류를 들고 걸어가 전달한다. 서류는 5건씩 순서대로 들어온다.
// SSE 이벤트는 '무엇이 일어났는지'만 알려 주고, 장면은 그 일을 사람 걸음 속도로 재연한다.
import { STATIONS, ACTORS, WALK, WAVE } from "./config.js";

const TILES_PER_S = 2.4;       // 걷는 속도 (1배속, 칸/초)
const SAY_MS = 1700;           // 말풍선을 보여 주며 서 있는 시간 (1배속)
const cut = (t, n) => (t && t.length > n ? t.slice(0, n - 1) + "…" : t || "");
const ANALYSTS = ["a0", "a1", "a2"];

class Actor {
  constructor(a) { this.role = a.role; this.home = { col: a.col, row: a.row }; this.pos = { ...this.home };
                   this.ops = []; this.carry = null; this.say = null; this.sayLeft = 0; this.state = "idle"; }
  busy() { return this.ops.length > 0; }
}

export class Office {
  constructor() {
    this.speed = 1;
    this.actors = Object.fromEntries(ACTORS.map(a => [a.role, new Actor(a)]));
    this.docs = new Map();        // code → { i, name, qty, signal, reason, branch, stage }
    this.order = [];              // 도착 순서
    this.wave = 0;                // 지금 들어와 있는 묶음 번호
    this.bossJobs = [];           // 팀장 결재 (승인·수정·반려·다시 판정)
    this.counts = { pending: 0, sent: 0, rejected: 0 };
  }
  setSpeed(n) { this.speed = n; }
  idle() { return this.order.every(c => this.docs.get(c).stage === "done") && !this.bossJobs.length
                  && Object.values(this.actors).every(a => !a.busy()); }
  setCounts(c) { if (this.idle()) Object.assign(this.counts, c); }   // 재연 중에는 장면 쪽 숫자를 믿는다

  push(e) {
    let d = this.docs.get(e.code);
    if (e.type === "judged") {
      if (d) return;
      d = { i: this.order.length, name: e.name, qty: e.qty, signal: e.signal, reason: e.reason, branch: null, stage: "door" };
      this.docs.set(e.code, d); this.order.push(e.code);
    } else if (!d) return;
    else if (e.type === "queued") d.branch = { kind: "stop", texts: e.texts || e.flags, failed: e.failed };
    else if (e.type === "sent" && e.by === "auto") d.branch = { kind: "auto" };
    else if (e.type === "sent") this.bossJobs.push({ code: e.code, to: "fax", say: e.action === "edit" ? `${e.qty}개로 수정해서 승인` : "승인! 보내 주세요" });
    else if (e.type === "rejected") this.bossJobs.push({ code: e.code, to: "trash", say: `반려\n${cut(e.reason, 18)}` });
    else if (e.type === "rejudged") this.bossJobs.push({ code: e.code, to: "inspHand", say: `다시 판정해 주세요\n${cut(e.instruction, 18)}` });
  }

  // ── 할 일 배정 ──────────────────────────────────────────────
  inWave(d) { return Math.floor(d.i / WAVE) <= this.wave; }
  schedule() {
    // 이번 묶음이 모두 끝나면 다음 5건을 들인다
    const cur = this.order.filter(c => Math.floor(this.docs.get(c).i / WAVE) === this.wave);
    if (cur.length && cur.every(c => this.docs.get(c).stage === "done") && this.order.length > (this.wave + 1) * WAVE) this.wave++;

    for (const r of ANALYSTS) {
      const a = this.actors[r];
      if (a.busy()) continue;
      const code = this.order.find(c => { const d = this.docs.get(c); return d.stage === "door" && this.inWave(d); });
      if (!code) continue;
      const d = this.docs.get(code); d.stage = "judging";
      a.ops.push({ walk: WALK.door }, { pick: code, state: "reading" }, { walk: a.home },
                 { say: `📦 ${cut(d.name, 16)}\n${d.qty ?? "?"}개 · ${d.signal ?? "판단 실패"}\n${cut(d.reason, 24)}`, state: "done" },
                 { walk: WALK.inspHand }, { drop: () => (d.stage = "atInsp") }, { walk: a.home });
    }
    const insp = this.actors.insp;
    if (!insp.busy()) {
      const code = this.order.find(c => { const d = this.docs.get(c); return d.stage === "atInsp" && d.branch; });
      if (code) {
        const d = this.docs.get(code); d.stage = "inspecting";
        const stop = d.branch.kind === "stop";
        const text = stop ? (d.branch.failed ? "판단 실패 —\n사람이 정해야 해요" : d.branch.texts.map(t => cut(t, 22)).join("\n")) : "기준 통과 ✓";
        insp.ops.push({ pick: code, state: stop ? "alarm" : "done" }, { say: `${text}\n→ ${stop ? "결재함" : "팩스"}` },
                      { walk: stop ? WALK.tray : WALK.fax },
                      { drop: () => { d.stage = "done"; stop ? this.counts.pending++ : this.counts.sent++; } },
                      { walk: insp.home });
      }
    }
    const boss = this.actors.boss;
    if (!boss.busy()) {
      const k = this.bossJobs.findIndex(j => this.docs.get(j.code)?.stage === "done");
      if (k >= 0) {
        const j = this.bossJobs.splice(k, 1)[0], d = this.docs.get(j.code);
        boss.ops.push({ walk: WALK.tray }, { pick: j.code, state: "reading", fn: () => (this.counts.pending = Math.max(0, this.counts.pending - 1)) },
                      { say: j.say, state: j.to === "trash" ? "waiting" : "done" }, { walk: WALK[j.to] },
                      { drop: () => {
                          if (j.to === "fax") this.counts.sent++;
                          else if (j.to === "trash") this.counts.rejected++;
                          else { d.stage = "atInsp"; d.branch = null; }     // 다시 판정 — 검사관이 새 결과로 다시 본다
                        } },
                      { walk: boss.home });
      }
    }
  }

  // ── 한 걸음씩 진행 ───────────────────────────────────────────
  step(a, dt) {
    let t = dt;
    while (t > 0 && a.ops.length) {
      const op = a.ops[0];
      if (op.walk) {
        const dx = op.walk.col - a.pos.col, dy = op.walk.row - a.pos.row, dist = Math.hypot(dx, dy);
        const can = (TILES_PER_S * t) / 1000;
        if (dist <= can) { a.pos = { ...op.walk }; t -= (dist / TILES_PER_S) * 1000; a.ops.shift(); }
        else { a.pos.col += (dx / dist) * can; a.pos.row += (dy / dist) * can; t = 0; }
      } else if (op.say !== undefined) {
        if (op.left === undefined) { op.left = SAY_MS; a.say = op.say; if (op.state) a.state = op.state; }
        const use = Math.min(op.left, t); op.left -= use; t -= use;
        if (op.left <= 0) { a.ops.shift(); a.say = null; }
      } else if (op.pick) { a.carry = op.pick; if (op.state) a.state = op.state; op.fn?.(); a.ops.shift(); }
      else if (op.drop) { a.carry = null; op.drop(); a.ops.shift(); }
      else a.ops.shift();
    }
    if (!a.ops.length) a.state = "idle";
  }

  tick(dt) {
    this.schedule();
    const scaled = dt * this.speed;
    for (const a of Object.values(this.actors)) this.step(a, scaled);
  }

  skip() {                          // 남은 재연을 한 번에 끝낸다
    for (let n = 0; n < 20000 && !this.idle(); n++) { this.schedule(); for (const a of Object.values(this.actors)) this.step(a, 400); }
    for (const a of Object.values(this.actors)) { a.say = null; a.state = "idle"; }
  }

  frame() {
    const waiting = st => this.order.filter(c => this.docs.get(c).stage === st && (st !== "door" || this.inWave(this.docs.get(c)))).length;
    const actors = Object.values(this.actors).map(a => ({ role: a.role, col: a.pos.col, row: a.pos.row,
                                                          state: a.state, say: a.say, carry: !!a.carry }));
    return { papers: [], actors,
             piles: { inbox: waiting("door"), inspect: waiting("atInsp"), tray: this.counts.pending,
                      fax: this.counts.sent, trash: this.counts.rejected },
             cabinet: this.counts.pending };
  }
}
