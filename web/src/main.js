import { preload, draw, fitView } from "./renderer.js";
import { Office } from "./office.js";
import { api, ensureSession, openEvents, setKey, S } from "./api.js";
import { renderSummary, renderInbox, renderDetail, renderFax, renderEval } from "./panels.js";

const $ = s => document.querySelector(s);
const canvas = $("#scene"), office = new Office();
let week = null, evalDoc = null, grid = false, selected = null, pendingItems = [];

// ── 카메라: 휠 확대·축소(커서 기준), 드래그 이동, 더블클릭·'전체' 로 되돌리기 ──
let cam = null;                                   // null 이면 방 전체에 맞춤
const view = () => cam || fitView(canvas);
function zoomAt(px, py, factor) {
  const v = view(), fit = fitView(canvas).scale;
  const scale = Math.min(Math.max(v.scale * factor, fit * 0.5), fit * 6);
  const k = scale / v.scale;                      // 커서 아래 점이 제자리에 있도록 이동량 보정
  cam = { scale, pan: { x: px - (px - v.pan.x) * k, y: py - (py - v.pan.y) * k } };
}
function setupCamera() {
  const pt = e => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  canvas.addEventListener("wheel", e => { e.preventDefault(); const [x, y] = pt(e); zoomAt(x, y, Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  let drag = null;
  canvas.addEventListener("pointerdown", e => { const v = view(); drag = { x: e.clientX, y: e.clientY, pan: { ...v.pan }, scale: v.scale };
                                                canvas.setPointerCapture(e.pointerId); canvas.style.cursor = "grabbing"; });
  canvas.addEventListener("pointermove", e => { if (!drag) return;
    cam = { scale: drag.scale, pan: { x: drag.pan.x + e.clientX - drag.x, y: drag.pan.y + e.clientY - drag.y } }; });
  const end = () => { drag = null; canvas.style.cursor = "grab"; };
  canvas.addEventListener("pointerup", end); canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("dblclick", () => (cam = null));
  canvas.style.cursor = "grab"; canvas.style.touchAction = "none";
  $("#fit").onclick = () => (cam = null);
  $("#zin").onclick = () => zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 1.25);
  $("#zout").onclick = () => zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 0.8);
}

// 오른쪽 패널 — 팀장이 결재함 앞에 도착하면 열린다 (office.onOpen), 비면 닫힌다 (office.onClose)
function renderPanel() {
  const open = office.reviewing;
  $("#panel-closed").hidden = open; $("#panel-open").hidden = !open;
  $("#aside").classList.toggle("wide", open);
  $("#wait-n").textContent = pendingItems.length;
  $("#review-n").textContent = pendingItems.length;
  if (!open) return;
  if (!pendingItems.some(p => p.thread_id === selected)) selected = null;
  renderInbox($("#inbox"), pendingItems, selected, tid => { selected = tid; renderPanel(); openDetail(tid); });
}

// 가운데 결재 창 — 다섯 칸 + 네 가지 응답. 결재하면 닫히고 팀장이 서류를 나른다.
function openDetail(tid) {
  const dlg = $("#modal");
  renderDetail($("#detail"), tid, () => { dlg.close(); refresh(); });
  if (!dlg.open) dlg.showModal();
}

async function refresh() {
  if (!week) return;
  const [sm, pend] = await Promise.all([api(`/api/summary?week=${week}`), api(`/api/pending?week=${week}`)]);
  renderSummary($("#summary"), sm); lastTotal = sm.total;
  pendingItems = pend.items;
  office.setCounts({ pending: sm.pending, sent: (sm.counts.auto_sent || 0) + (sm.counts.approved || 0) + (sm.counts.edited || 0),
                     rejected: sm.counts.rejected || 0, auto: sm.counts.auto_sent || 0 });
  renderPanel();
  if ($("#tab-fax").classList.contains("on")) renderFax($("#fax"), (await api("/api/faxlog")).items);
}

// 설명란 — 에이전트의 다섯 단계와 지금 하는 일 (교재 개념과 함께)
let ruleText = "", lastTotal = 0;
const RULE_KO = { C2: "평균의 2배 초과", C3: "판매 변동 큼", C4: "AI 신호 급증·감소", C5: "판단 흔들림", ALL: "전부" };
const ruleKo = r => (r.startsWith("C1:") ? `발주액 > £${r.split(":")[1]}` : RULE_KO[r] || r);
function renderStatus() {
  const st = office.status(), on = k => (st.active.includes(k) ? "on" : "");
  $("#st-wave").textContent = st.waves ? `묶음 ${st.wave} / ${st.waves} (5건씩)`
    : lastTotal ? `— 이번 주 처리 완료 (${lastTotal}건)` : "— ▶ 이번 주 처리를 누르세요";
  const row = (k, no, name, desc, n) => `<li class="${on(k)}"><span class="no">${no}</span><b>${name}</b><span>${desc}</span><span class="n">${n}</span></li>`;
  $("#st-body").innerHTML = `<ol>
    ${row("door", "1", "입고", "문 앞에 묶음 도착", st.stage.door ? `${st.stage.door}건` : "")}
    ${row("judge", "2", "AI 판단", "분석가(LLM)가 발주량·이유 결정", st.stage.judge ? `${st.stage.judge}건` : "")}
    ${row("check", "3", "기준 검사", ruleText, st.stage.check ? `${st.stage.check}건` : "")}
    ${row("auto", "4", "자동 발송", "기준 통과 → 팩스 (사람 없이)", `${st.stage.auto}건`)}
    ${row("human", "5", "사람 결재", "interrupt → 나의 결재 → resume", `대기 ${st.stage.human}건`)}
  </ol>${st.doing.length || st.last ? `<div class="doing">${st.doing.map(d => `<p>▶ ${d}</p>`).join("")}${st.last ? `<p class="last">방금: ${st.last}</p>` : ""}</div>` : ""}`;
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
  ruleText = (info.combo || []).map(ruleKo).join(" 또는 ");
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
  setupCamera();
  office.onOpen = () => { selected = null; renderPanel(); };
  office.onClose = () => { if ($("#modal").open) $("#modal").close(); renderPanel(); };
  $("#go-review").onclick = () => office.openNow();
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
  if (location.hash.includes("open") && pendingItems[0]) openDetail(pendingItems[0].thread_id);   // 캡처용
  if (location.hash.includes("eval")) tab("eval");
  if (location.hash.includes("fax")) tab("fax");
  renderStatus(); setInterval(renderStatus, 250);
  let last = performance.now();
  (function loop(t) { office.tick(t - last); last = t; draw(canvas, { ...view(), frame: office.frame(), grid }); requestAnimationFrame(loop); })(last);
}
main().catch(e => { document.body.insertAdjacentHTML("afterbegin", `<p class="fatal">${e.message}</p>`); });
