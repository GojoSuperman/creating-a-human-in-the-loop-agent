// 캐릭터 조립 — 계획서 5.8. 오프셋은 조립해 보고 맞춘 실측값이다.
//
// 완성 얼굴 face_a~l 은 쓰지 않는다. 이름으로 표정을 알 수 없어 상태와 이어 붙일 수 없다.
// 부품(facial_part_*)은 이름이 곧 의미라 대응표를 만들 수 있다.

export const BODY = 80;              // 몸통 80×80
export const SCALE = 1.0;            // 가구 크기에 맞춰 화면 보며 조정한다

// 얼굴·손 배치 — 몸통 좌상단 기준. 부품마다 크기가 달라(입 20~40px) 중앙 정렬로 놓는다.
const FACE = { cx: 40, cy: 33, eyeGap: 24, mouthCy: 54 };
const HAND = { y: 34, gap: -2 };     // 몸통에 살짝 붙인다. 띄우면 떨어져 보인다.

// 배역 — 수요 분석가 셋, 검사관, 팀장(= 화면 앞의 사용자)
export const CAST = {
  a0:   { color: "blue",   shape: "circle",   label: "김 분석가" },
  a1:   { color: "green",  shape: "circle",   label: "이 분석가" },
  a2:   { color: "pink",   shape: "circle",   label: "박 분석가" },
  insp: { color: "red",    shape: "square",   label: "최 검사관" },
  boss: { color: "purple", shape: "squircle", label: "팀장 (나)" },
};

export const name = (r) => CAST[r]?.label || r;

// 상태 → 부품. 부품 파일명이 곧 표정이다.
export const STATES = {
  idle:    { eye: "open",        mouth: null,    hand: "open"   },
  reading: { eye: "half_top",    mouth: null,    hand: "closed" },
  done:    { eye: "open",        mouth: "happy", hand: "thumb"  },
  alarm:   { eye: "open",        mouth: "angry", hand: "point"  },
  waiting: { eye: "half_top",    mouth: "sad",   hand: "open"   },
};

/** 한 캐릭터를 그리는 데 필요한 스프라이트 이름들 */
export function partsOf(role, state) {
  const c = CAST[role], s = STATES[state] || STATES.idle;
  const hand = c.color === "yellow" ? `hand_yellow_${s.hand}` : `${c.color}_hand_${s.hand}`;
  return {
    shadow: "shadow",
    body: `${c.color}_body_${c.shape}`,
    eye: s.eye ? `facial_part_eye_${s.eye}` : null,
    mouth: s.mouth ? `facial_part_mouth_${s.mouth}` : null,
    hand: s.hand ? hand : null,
  };
}

/** 미리 읽어 둘 캐릭터 스프라이트 전부 */
export function allParts() {
  const out = new Set(["shadow"]);
  for (const role of Object.keys(CAST))
    for (const state of Object.keys(STATES))
      for (const v of Object.values(partsOf(role, state))) if (v) out.add(v);
  return [...out];
}

/**
 * (x, y) 는 캐릭터가 서 있는 바닥 지점. 발끝이 거기에 닿고 몸이 위로 선다.
 * get(name) 은 로드된 이미지를 돌려주는 함수 (없으면 null).
 */
export function drawActor(ctx, get, role, state, x, y, scale = SCALE) {
  const p = partsOf(role, state);
  const s = scale;
  const left = x - (BODY / 2) * s;     // 몸통 좌상단
  const top = y - BODY * s;

  const img = n => (n ? get(n) : null);
  const put = (n, dx, dy) => {
    const i = img(n);
    if (i) ctx.drawImage(i, left + dx * s, top + dy * s, i.width * s, i.height * s);
  };
  const center = (n, cx, cy) => {
    const i = img(n);
    if (i) put(n, cx - i.width / 2, cy - i.height / 2);
  };

  const sh = img(p.shadow);
  if (sh) ctx.drawImage(sh, x - (sh.width / 2) * s, y - (sh.height * 0.6) * s,
                        sh.width * s, sh.height * s);
  put(p.body, 0, 0);
  if (p.eye) {
    center(p.eye, FACE.cx - FACE.eyeGap / 2, FACE.cy);
    center(p.eye, FACE.cx + FACE.eyeGap / 2, FACE.cy);
  }
  if (p.mouth) center(p.mouth, FACE.cx, FACE.mouthCy);
  if (p.hand) {
    const h = img(p.hand);
    if (h) {
      // 왼손은 좌우를 뒤집는다
      ctx.save();
      ctx.translate(left + (-HAND.gap) * s, top + HAND.y * s);
      ctx.scale(-1, 1);
      ctx.drawImage(h, 0, 0, h.width * s, h.height * s);
      ctx.restore();
      put(p.hand, BODY + HAND.gap, HAND.y);
    }
  }
}
