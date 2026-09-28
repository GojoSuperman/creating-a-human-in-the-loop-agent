// 사무실 장면 상태 — SSE 이벤트를 서류 이동으로 바꾼다. 그리기는 renderer.js 가 한다.
import { STATIONS, ACTORS } from "./config.js";

const HOP_MS = 520;            // 정거장 한 칸 이동 시간 (1배속)
const GAP_MS = 260;            // 다음 서류가 출발하는 간격 (1배속)

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

  push(e) {
    const hop = (route, tone, effect) => this.extend(e.code, route, tone, effect);
    if (e.type === "judged") hop(["inbox", `a${e.analyst}`, "inspect"], "plain", () => this.act(`a${e.analyst}`, "done"));
    else if (e.type === "queued") hop(["inspect", "tray"], e.failed ? "fail" : "stop", () => {
      this.counts.pending++; this.act("insp", "alarm", e.failed ? "판단 실패!" : `기준 ${e.flags.join("·")} 걸림`);
    });
    else if (e.type === "sent") hop(e.by === "auto" ? ["inspect", "fax"] : ["tray", "fax"], "auto", () => {
      this.counts.sent++;
      if (e.by !== "auto") { this.counts.pending = Math.max(0, this.counts.pending - 1); this.act("boss", "done", "승인!"); }
    });
    else if (e.type === "rejected") hop(["tray", "trash"], "stop", () => {
      this.counts.rejected++; this.counts.pending = Math.max(0, this.counts.pending - 1); this.act("boss", "waiting", "반려");
    });
    else if (e.type === "rejudged") hop(["tray", "inspect"], "plain", () => {
      this.counts.pending = Math.max(0, this.counts.pending - 1); this.act("boss", "reading", "다시 판정해 줘요");
    });
  }

  extend(code, route, tone, effect) {
    let job = this.byCode.get(code);
    if (!job || job.done) {
      job = { code, legs: [], leg: 0, t: 0, done: false };
      this.byCode.set(code, job); this.waiting.push(job);
    }
    for (let i = 0; i + 1 < route.length; i++)
      job.legs.push({ from: route[i], to: route[i + 1], tone, effect: i + 2 === route.length ? effect : null });
  }

  act(role, state, say) {
    this.mood[role] = { state, until: this.clock + 1400 / this.speed };
    if (say) this.says[role] = { text: say, until: this.clock + 1600 / this.speed };
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
