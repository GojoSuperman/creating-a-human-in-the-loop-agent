import { preload, draw, fitView } from "./renderer.js";
import { Office } from "./office.js";
import { api, ensureSession, openEvents, setKey, S } from "./api.js";
import { renderSummary, renderInbox, openModal, renderFax, renderEval } from "./panels.js";

const $ = s => document.querySelector(s);
const canvas = $("#scene"), office = new Office();
let week = null, evalDoc = null, grid = false;

async function refresh() {
  if (!week) return;
  const [sm, pend] = await Promise.all([api(`/api/summary?week=${week}`), api(`/api/pending?week=${week}`)]);
  renderSummary($("#summary"), sm);
  renderInbox($("#inbox"), pend.items, tid => openModal(tid, refresh));
  office.setCounts({ pending: sm.pending, sent: (sm.counts.auto_sent || 0) + (sm.counts.approved || 0) + (sm.counts.edited || 0),
                     rejected: sm.counts.rejected || 0 });
  if ($("#tab-fax").classList.contains("on")) renderFax($("#fax"), (await api("/api/faxlog")).items);
}

let pending = null;
const soon = () => { clearTimeout(pending); pending = setTimeout(refresh, 400); };

function tab(name) {
  for (const t of ["office", "fax", "eval"]) {
    $(`#tab-${t}`).classList.toggle("on", t === name);
    $(`#view-${t}`).hidden = t !== name;
  }
  if (name === "fax") api("/api/faxlog").then(r => renderFax($("#fax"), r.items));
  if (name === "eval") renderEval($("#eval"), evalDoc);
}

async function main() {
  const info = await ensureSession();
  const sel = $("#week");
  sel.innerHTML = (info.weeks || []).map(w => `<option>${w}</option>`).join("");
  week = sel.value || null;
  sel.onchange = () => { week = sel.value; refresh(); };
  $("#combo").textContent = `승인 기준: ${(info.combo || []).join(" · ")}`;
  $("#run").onclick = async () => {
    try { await api("/api/run", { method: "POST", body: JSON.stringify({ week }) }); }
    catch (e) { alert(e.message); }
  };
  $("#reset").onclick = async () => { await api("/api/reset", { method: "POST" }); location.reload(); };
  const keyLabel = () => ($("#key").textContent = S.key ? "🔑 키 있음" : "🔑 내 키");
  $("#key").onclick = () => {
    const k = prompt("OpenAI 키 (이 브라우저에만 저장, 서버에 저장하지 않음). 비우면 삭제", S.key || "");
    if (k !== null) setKey(k.trim());
    keyLabel();
  };
  keyLabel();
  document.querySelectorAll("[data-speed]").forEach(b => b.onclick = () => {
    const v = b.dataset.speed;
    if (v === "skip") office.skip(); else office.setSpeed(Number(v));
    document.querySelectorAll("[data-speed]").forEach(x => x.classList.toggle("on", x === b && v !== "skip"));
  });
  for (const t of ["office", "fax", "eval"]) $(`#tab-${t}`).onclick = () => tab(t);
  addEventListener("keydown", e => { if ((e.key === "g" || e.key === "G") && e.target === document.body) grid = !grid; });
  evalDoc = await api("/api/eval").catch(() => null);

  // 캡처용(?shot): 헤드리스 크롬은 열린 SSE 때문에 로딩이 끝나지 않으므로 이벤트를 받지 않는다
  if (!new URLSearchParams(location.search).has("shot")) {
    const es = openEvents(e => {
      if (e.week && e.week !== week) return;
      if (e.type === "batch_error") alert(`실행 오류: ${e.message}`);
      office.push(e); soon();
    });
    es.onerror = () => soon();          // 재연결되면 서버 상태로 다시 맞춘다
  }
  await preload();
  await refresh();
  if (location.hash.includes("skip")) office.skip();
  if (location.hash.includes("open")) {          // 시연·캡처용: 결재함 첫 서류 열기
    const first = document.querySelector("#inbox .doc");
    if (first) first.click();
  }
  if (location.hash.includes("eval")) tab("eval");
  if (location.hash.includes("fax")) tab("fax");
  let last = performance.now();
  (function loop(t) { office.tick(t - last); last = t; draw(canvas, { ...fitView(canvas), frame: office.frame(), grid }); requestAnimationFrame(loop); })(last);
}
main().catch(e => { document.body.insertAdjacentHTML("afterbegin", `<p class="fatal">${e.message}</p>`); });
