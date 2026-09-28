// 좌표계는 Deep-research-agent 에셋 실측값을 그대로 쓴다. 배치는 캡처를 보며 조정한다.
export const TILE = { W: 256, H: 128 };
export const STEP = { X: 128, Y: 64 };
export const SPRITE = { W: 384, H: 768 };
export const GRID = { cols: 14, rows: 9 };
export const DESK_TOP = -60;
export const LAYER = { FLOOR: 0, WALL: 0.5, PROP: 1, ON_DESK: 1.2, ACTOR: 2 };
export const WALL = { wall: "wall_SE", door: "wallDoorway_SE", win: "wallWindow_SE", doorAt: 2, winAt: 6 };
export const ASSETS = "assets";
export const ASSET_V = "1";
export const FURN = "furniture";
export const FACE = "_SE";

// 배치 v2 — 사용자가 그린 배치(소품/배치.png)를 칸 좌표로 옮긴 것. 소수점 좌표도 된다.
// flip: 좌우 뒤집기(남동 이미지를 뒤집어 방향을 맞춤), scale: 바닥 앵커 기준 확대
const DESK_X = [1.6, 3.6, 5.6, 7.6];
export const PROP_SCALE = 1.25;     // 사용자 배치 그림의 소품 크기 (실측 비율)
export const ACTOR_SCALE = 1.3;          // 분석가 셋 + 검사관 책상 (행 2.6)

// 서류가 오가는 정거장 — lift 는 서류가 놓이는 높이(책상·탁자 위 등)
export const STATIONS = {
  inbox:   { col: 0.3,  row: 1.3,  lift: -20,      name: "📥 입고(문)" },
  a0:      { col: DESK_X[0], row: 2.6, lift: DESK_TOP },
  a1:      { col: DESK_X[1], row: 2.6, lift: DESK_TOP },
  a2:      { col: DESK_X[2], row: 2.6, lift: DESK_TOP },
  inspect: { col: DESK_X[3], row: 2.6, lift: DESK_TOP, name: "🔍 검사" },
  tray:    { col: 7.98, row: 5.81, lift: -75,      name: "📥 결재함" },
  fax:     { col: 9.61, row: 5.78, lift: -75,      name: "📠 팩스 → 거래처" },
  cabinet: { col: -0.55, row: 3.97,  lift: -200,     name: "🗄️ 캐비닛" },
  trash:   { col: 11.75, row: 2.8,  lift: -20,      name: "🗑️ 반려" },
};

export const PROPS = [
  ...DESK_X.flatMap(c => [
    // 서랍 면이 캐릭터(오른쪽 아래)를 보게 제자리 뒤집기 — 사용자 배치안과 겹쳐 재서 맞춘 값
    { col: c + 0.57, row: 2.75, sprite: "desk", mirror: true },
    // 모니터는 책상과 **같은 칸**에 둔다 — 칸이 다르면 그리는 순서가 책상보다 앞서 상판에 가려진다
    { col: c + 0.57, row: 2.75, sprite: "computerScreen", layer: 1.2, dy: -54, dx: 38, mirror: true },
    { col: c + 0.8, row: 3.0, sprite: "trashcan" },
  ]),
  // 팀장 코너책상 + 모니터 + 작은 화분 + 휴지통
  { col: 10.2, row: 2.9, sprite: "deskCorner", flip: true },
  { col: 10.2, row: 2.9, sprite: "computerScreen", layer: 1.2, dy: -78, dx: 84, mirror: true },   // 코너책상과 같은 칸
  { col: 10.5, row: 2.6, sprite: "plantSmall1", layer: 1.2, dy: DESK_TOP },
  { col: 11.75, row: 2.8, sprite: "trashcan" },
  // 캐비닛 = 세탁기 3대 (왼쪽 벽)
  { col: -0.55, row: 3.47, sprite: "washerDryerStacked", flip: true },
  { col: -0.55, row: 3.97, sprite: "washerDryerStacked", flip: true },
  { col: -0.55, row: 4.47, sprite: "washerDryerStacked", flip: true },
  // 책장 5개 (오른쪽 벽)
  ...[7.47, 8.02, 8.57, 9.12, 9.67].map(c => ({ col: c, row: -0.9, sprite: "bookcaseClosed" })),
  // 긴 탁자 2개 — 결재함(화분) · 팩스대(커피머신)
  { col: 9.9, row: 5.4, sprite: "tableCoffee", scale: 1.85 },
  { col: 11.5, row: 5.3, sprite: "tableCoffee", scale: 1.85 },
  { col: 9.8, row: 5.8, sprite: "pottedPlant", layer: 1.2, dy: -60 },
  { col: 11.13, row: 5.97, sprite: "kitchenCoffeeMachine", layer: 1.2, dy: -60 },
];

export const ACTORS = [
  { role: "a0", col: 2.7, row: 3.1 }, { role: "a1", col: 4.7, row: 3.1 }, { role: "a2", col: 6.7, row: 3.1 },
  { role: "insp", col: 8.7, row: 3.1 }, { role: "boss", col: 11.2, row: 2.65 },
];

export const TONE = { plain: "#ffffff", auto: "#3fae6e", stop: "#d9566c", fail: "#9aa0a6" };

// 캐릭터가 서류를 들고 걸어가 서는 자리 (정거장 앞)
export const WALK = {
  door:     { col: 0.6,  row: 1.6 },    // 입고(문) 앞 — 분석가가 서류를 집는 곳
  inspHand: { col: 7.9,  row: 3.75 },   // 검사관 책상 앞 — 분석가가 서류를 건네는 곳
  tray:     { col: 8.1,  row: 4.9 },    // 결재함 탁자 옆
  fax:      { col: 9.7,  row: 4.8 },    // 팩스 탁자 옆
  trash:    { col: 11.6, row: 3.3 },    // 팀장 휴지통 옆
};
export const WAVE = 5;                  // 한 번에 들어오는 서류 수
export const REVIEW_AT = 5;             // 결재함에 이만큼 쌓이면 팀장이 보러 간다
