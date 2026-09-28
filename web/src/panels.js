// 결재함 목록 · 결재 모달(다섯 칸 + 네 가지 응답) · 현황판 · 발송 기록 · 기준 검증
import { api, S } from "./api.js";

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const won = n => n == null ? "-" : `₩${Math.round(n).toLocaleString()}`;
const gbp = n => n == null ? "-" : `£${Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
const STATUS = { auto_sent: "자동 발송", pending: "대기", failed_to_human: "판단 실패", approved: "승인",
                 edited: "수정 승인", rejected: "반려", running: "처리 중" };

export function renderSummary(el, sm) {
  const c = sm.counts || {};
  const chip = (k, label, n) => `<span class="chip ${k}"><b>${n ?? 0}</b> ${label}</span>`;
  el.innerHTML = chip("all", "전체", sm.total) + chip("auto", "자동 발송", c.auto_sent) + chip("wait", "대기", sm.pending)
    + chip("ok", "승인", c.approved) + chip("edit", "수정 승인", c.edited) + chip("no", "반려", c.rejected);
}

export function renderInbox(el, items, onOpen) {
  if (!items.length) { el.innerHTML = `<p class="empty">결재할 서류가 없습니다</p>`; return; }
  el.innerHTML = items.map(it => `
    <button class="doc ${it.error ? "fail" : ""}" data-tid="${esc(it.thread_id)}">
      <span class="nm">${esc(it.name_ko)}</span>
      <span class="meta">${it.qty == null ? "수량 없음" : `${it.qty.toLocaleString()}개 · ${won(it.amount_krw)}`}</span>
      <span class="fl">${it.flags.map(f => `<i>${esc(f)}</i>`).join("")}${it.stale ? `<i class="stale">기한 초과 · 상위 결재자에게 넘김</i>` : ""}</span>
    </button>`).join("");
  el.querySelectorAll(".doc").forEach(b => b.onclick = () => onOpen(b.dataset.tid));
}

function bars(hist, mean) {
  const max = Math.max(...hist, mean, 1);
  return `<div class="bars">${hist.map((v, i) => `<div title="${i - 8}주: ${v}"><span style="height:${(v / max) * 100}%"></span><em>${v}</em></div>`).join("")}
    <hr style="bottom:${(mean / max) * 100}%" title="8주 평균 ${mean}"></div>`;
}

export async function openModal(tid, onDone) {
  const dlg = document.getElementById("modal"), body = dlg.querySelector(".body");
  const o = await api(`/api/orders/${encodeURIComponent(tid)}`);
  const redoOk = o.options.includes("redo") && !!S.key;
  body.innerHTML = `
    <h2>${esc(o.name_ko)} <small>${esc(o.name_en)} · ${esc(o.code)}</small></h2>
    ${o.stale ? `<p class="warn">72시간 넘게 대기 — 상위 결재자에게 넘겨진 건입니다 (자동 승인하지 않음)</p>` : ""}
    <section><h3>① 원문</h3><p>${esc(o.name_en)} (단가 ${gbp(o.price_gbp)})</p></section>
    <section><h3>② 핵심 정보</h3>
      <p class="big">${o.qty == null ? "수량 없음" : `${o.qty.toLocaleString()}개 · ${gbp(o.amount_gbp)} (${won(o.amount_krw)})`}</p>
      <p>최근 8주 판매 (평균 ${o.mean8})</p>${bars(o.hist8, o.mean8)}</section>
    <section><h3>③ AI 판단과 근거</h3>
      ${o.error ? `<p class="warn">판단 실패: ${esc(o.error)}</p>` : `<p>${esc(o.reason_ko)}</p><p>수요 신호: <b>${esc(o.demand_signal)}</b></p>`}</section>
    <section><h3>④ 멈춘 이유</h3><ul>${o.flags.map(f => `<li>${esc(f.text)}</li>`).join("")}</ul></section>
    <section class="then"><h3>⑤ 통과시키면</h3><p><b>${esc(o.if_approved)}</b></p></section>
    <div class="actions">
      ${o.options.includes("approve") ? `<button data-a="approve" class="go">✅ 승인</button>` : ""}
      <span class="edit"><input type="number" min="0" step="1" value="${o.qty ?? ""}" aria-label="수정 수량">
        <button data-a="edit" class="blue">✏️ 수량 수정 후 승인</button></span>
      <span class="rej"><input type="text" placeholder="반려 사유 (필수)" aria-label="반려 사유">
        <button data-a="reject" class="no">🙅 반려</button></span>
      <span class="redo"><input type="text" placeholder="다시 판정 지시" aria-label="다시 판정 지시" ${redoOk ? "" : "disabled"}>
        <button data-a="redo" class="purple" ${redoOk ? "" : "disabled"}
          title="${S.key ? `남은 횟수 ${o.redo_left}` : "OpenAI 키를 넣으면 쓸 수 있습니다"}">🔁 다시 판정 (${o.redo_left})</button></span>
    </div><p class="err" role="alert"></p>`;
  body.querySelectorAll("[data-a]").forEach(b => b.onclick = async () => {
    const a = b.dataset.a, err = body.querySelector(".err");
    const d = { action: a };
    if (a === "edit") {
      const raw = body.querySelector(".edit input").value.trim();
      const n = raw === "" ? NaN : Number(raw);             // 빈칸이 0개로 바뀌지 않게
      d.qty = Number.isInteger(n) ? n : raw;                // 정수가 아니면 그대로 보내 서버가 사유를 돌려준다
    }
    if (a === "reject") d.reason = body.querySelector(".rej input").value;
    if (a === "redo") d.instruction = body.querySelector(".redo input").value;
    body.querySelectorAll("button").forEach(x => x.disabled = true);
    try { await api(`/api/orders/${encodeURIComponent(tid)}/decision`, { method: "POST", body: JSON.stringify(d) }); dlg.close(); onDone(); }
    catch (e) { err.textContent = e.message; body.querySelectorAll("button").forEach(x => x.disabled = false); if (e.status === 409) { dlg.close(); onDone(); } }
  });
  dlg.showModal();
}

export function renderFax(el, items) {
  el.innerHTML = `<table><tr><th>시각</th><th>상품</th><th>수량</th><th>금액</th><th>누가</th><th>상태</th></tr>${
    items.slice().reverse().map(f => `<tr><td>${new Date(f.sent_at * 1000).toLocaleTimeString()}</td>
      <td>${esc(f.po.name_ko || f.po.name_en)}</td>
      <td>${f.po.qty.toLocaleString()}${f.po.ai_qty !== f.po.qty ? ` <small>(AI ${f.po.ai_qty})</small>` : ""}</td>
      <td>${won(f.po.amount_krw)}</td><td>${f.po.by === "auto" ? "🤖 자동" : "👤 팀장"}</td>
      <td>${STATUS[f.po.status] || f.po.status}</td></tr>`).join("")}</table>`;
}

const pct = x => `${(x * 100).toFixed(1)}%`;
function evalTable(rows, sel, spread) {
  return `<table><tr><th>기준</th><th>개입률</th><th>놓침</th><th>놓친 손해</th><th>헛멈춤</th></tr>${rows.map(r => {
    const s = spread?.[r.name], rng = (k, f) => s && s[k][0] !== s[k][1] ? ` <small>(${f(s[k][0])}~${f(s[k][1])})</small>` : "";
    return `<tr class="${r.name === sel ? "sel" : ""}"><td>${esc(r.name)}</td><td>${pct(r.rate)}${rng("rate", pct)}</td>
      <td>${r.missed}건${rng("missed", x => x)}</td><td>${gbp(r.missed_loss)}${rng("missed_loss", gbp)}</td>
      <td>${r.false_stop}건${rng("false_stop", x => x)}</td></tr>`; }).join("")}</table>`;
}

export function renderEval(el, doc) {
  if (!doc) { el.innerHTML = `<p class="empty">아직 기준 검증 결과가 없습니다</p>`; return; }
  const d = doc.dev, sel = doc.selected.name;
  el.innerHTML = `
    <p>정답 라벨: <b>|AI 발주량 − 실제 다음 주 판매| × 단가 > £${doc.label_loss_gbp}</b> 이면 "사람이 봤어야 할 건".
       선택 규칙: 개발 주에서 개입률 ≤ ${pct(doc.max_rate)} 중 놓친 손해 최소 (실행 전에 정해 둠).</p>
    <h3>개발 주 ${d.week} — 멈춰야 할 건 ${d.tables[0].positives}건, 판단 실패 ${d.tables[0].failed}건
      <small>(괄호: LLM ${d.samples}회 반복의 흔들림 폭)</small></h3>
    ${evalTable(d.tables[0].rows, sel, d.spread)}
    <p class="pick">선택된 기준: <b>${esc(sel)}</b>${doc.selected.fallback ? " (상한을 만족하는 조합이 없어 개입률 최소를 고름)" : ""}</p>
    ${doc.preregistered && doc.preregistered.name !== sel ? `<p class="note">사전 등록 규칙만으로는 <b>${esc(doc.preregistered.name)}</b> 이 뽑혔다. ${esc(doc.amendment)}.</p>` : ""}
    ${doc.tests.map(t => `<h3>검증 주 ${t.week} — 멈춰야 할 건 ${t.table.positives}건</h3>${evalTable(t.table.rows, sel)}
      <p>기준선: LLM 발주 총손해 ${gbp(t.baseline.llm_loss)} vs 단순 평균 발주 ${gbp(t.baseline.naive_loss)}</p>`).join("")}`;
}
