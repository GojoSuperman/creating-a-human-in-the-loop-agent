// 서버 호출 — 세션은 localStorage, 방문자 키(BYOK)는 이 브라우저에만 둔다.
export const S = { session: null, key: null };
const get = k => { try { return localStorage.getItem(k); } catch { return null; } };
const set = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} };
S.key = get("hitl-openai-key");

export function setKey(k) { S.key = k || null; set("hitl-openai-key", S.key); }

export async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(S.session ? { "X-Session": S.session } : {}),
                    ...(S.key ? { "X-OpenAI-Key": S.key } : {}) };
  const r = await fetch(path, { ...opts, headers });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(body.detail || r.statusText), { status: r.status });
  return body;
}

export async function ensureSession() {
  // ?session= 으로 세션을 넘겨받을 수 있다 (캡처·시연용). 받은 세션은 이 브라우저에 저장한다.
  const fromUrl = new URLSearchParams(location.search).get("session");
  if (fromUrl) set("hitl-session", fromUrl);
  S.session = get("hitl-session");
  if (S.session) {
    try { return await api("/api/session-info"); }
    catch (e) { if (e.status !== 401) throw e; }
  }
  S.session = null;
  const info = await api("/api/session", { method: "POST" });
  S.session = info.session; set("hitl-session", S.session);
  return info;
}

export function openEvents(onEvent) {
  const es = new EventSource(`/api/events?session=${S.session}`);
  for (const t of ["judging", "judged", "queued", "sent", "rejected", "rejudged", "batch_done", "batch_error"])
    es.addEventListener(t, m => onEvent(JSON.parse(m.data)));
  return es;
}
