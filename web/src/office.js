// 사무실 장면 상태 — SSE 이벤트를 서류 이동으로 바꾼다. 그리기는 renderer.js 가 한다.
import { STATIONS, ACTORS } from "./config.js";

const HOP_MS = 600;            // 정거장 한 칸 이동 시간 (1배속)
const GAP_MS = 900;            // 다음 서류가 출발하는 간격 (1배속) — 말풍선을 읽을 수 있게
const SAY_MS = 2600;           // 말풍선이 떠 있는 시간 (1배속)
const cut = (t, n) => (t && t.length > n ? t.slice(0, n - 1) + "…" : t || "");

export class Office {
  constructor() {
    this.speed = 1;
    this.waiting = [];          // 출발 전 작업
    this.flying = [];           // 이동 중 작업
    this.byCode = new Map();    // code → 작업 (같은 건의 다음 이벤트를 이어 붙인다)
    this.clock = 0; this.nextStart = 0;
    this.counts = { pending: 0, sent: 0, rejected: 0 };
    this.mood = {}; this.says = {};
  }
  setSpeed(n) { this.speed = n; }
  setCounts(c) { Object.assign(this.counts, c); }

  // 이벤트 → 서류 경로. 각 구간 끝(서류 도착)에 그 자리 캐릭터가 말한다.
  push(e) {
    const hop = (route, tone, effects) => this.extend(e.code, route, tone, effects);
    const a = `a${e.analyst}`;
    if (e.type === "judged") hop(["inbox", a, "inspect"], "plain", [
      () => this.act(a, "reading", `📦 ${cut(e.name, 16)}\n${e.qty ?? "?"}개 · ${e.signal ?? "판단 실패"}\n${cut(e.reason, 24)}`),
      () => this.act(a, "done"),
    ]);
    else if (e.type === "queued") hop(["inspect", "tray"], e.failed ? "fail" : "stop", [() => {
      this.counts.pending++;
      this.act("insp", "alarm", e.failed ? "판단 실패 — 사람이 정해야 해요\n→ 결재함" : `${(e.texts || e.flags).map(t => cut(t, 22)).join("\n")}\n→ 결재함`);
    }]);
    else if (e.type === "sent") {
      if (e.by === "auto") hop(["inspect", "fax"], "auto", [() => { this.counts.sent++; this.act("insp", "done", "기준 통과 ✓\n→ 팩스"); }]);
      else hop(["tray", "fax"], "auto", [() => {
        this.counts.sent++; this.counts.pending = Math.max(0, this.counts.pending - 1);
        this.act("boss", "done", e.action === "edit" ? `${e.qty}개로 수정해서 승인` : "승인! 보내 주세요");
      }]);
    }
    else if (e.type === "rejected") hop(["tray", "trash"], "stop", [() => {
      this.counts.rejected++; this.counts.pending = Math.max(0, this.counts.pending - 1);
      this.act("boss", "waiting", `반려\n${cut(e.reason, 20)}`);
    }]);
    else if (e.type === "rejudged") hop(["tray", "inspect"], "plain", [() => {
      this.counts.pending = Math.max(0, this.counts.pending - 1);
      this.act("boss", "reading", `다시 판정해 주세요\n${cut(e.instruction, 20)}`);
    }]);
  }

  extend(code, route, tone, effects = []) {
    let job = this.byCode.get(code);
    if (!job || job.done) {
      job = { code, legs: [], leg: 0, t: 0, done: false };
      this.byCode.set(code, job); this.waiting.push(job);
    }
    for (let i = 0; i + 1 < route.length; i++)
      job.legs.push({ from: route[i], to: route[i + 1], tone, effect: effects[i] || null });
  }

  act(role, state, say) {
    this.mood[role] = { state, until: this.clock + SAY_MS / this.speed };
    if (say) this.says[role] = { text: say, until: this.clock + SAY_MS / this.speed };
  }

  tick(dt) {
    this.clock += dt;
    if (this.waiting.length && this.clock >= this.nextStart) {
      this.flying.push(this.waiting.shift());
      this.nextStart = this.clock + GAP_MS / this.speed;
    }
    for (const job of this.flying) {
      job.t += (dt * this.speed) / HOP_MS;
      while (job.t >= 1 && job.leg < job.legs.length) {
        const leg = job.legs[job.leg];
        leg.effect?.();
        job.leg++; job.t -= 1;
      }
      if (job.leg >= job.legs.length) job.done = true;
    }
    this.flying = this.flying.filter(j => !j.done);
  }

  skip() {
    for (const job of [...this.flying, ...this.waiting])
      for (const leg of job.legs.slice(job.leg)) leg.effect?.();
    for (const job of [...this.flying, ...this.waiting]) job.done = true;
    this.flying = []; this.waiting = [];
  }

  frame() {
    const papers = [];
    for (const job of this.flying) {
      const leg = job.legs[job.leg];
      if (!leg) continue;
      const a = STATIONS[leg.from], b = STATIONS[leg.to], t = Math.min(job.t, 1);
      papers.push({ col: a.col + (b.col - a.col) * t, row: a.row + (b.row - a.row) * t,
                    lift: a.lift + (b.lift - a.lift) * t - Math.sin(Math.PI * t) * 90, tone: leg.tone });
    }
    const actors = ACTORS.map(a => {
      const m = this.mood[a.role], s = this.says[a.role];
      return { ...a, state: m && m.until > this.clock ? m.state : "idle",
               say: s && s.until > this.clock ? s.text : null };
    });
    return { papers, actors, piles: { tray: this.counts.pending, fax: this.counts.sent, trash: this.counts.rejected },
             cabinet: this.counts.pending };
  }
}
