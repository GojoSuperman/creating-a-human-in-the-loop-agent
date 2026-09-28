# 📦 재고 발주 결재실 — 사람이 승인하는 발주 에이전트

LLM이 상품별 다음 주 **발주량**을 정하고, **위험한 발주만** 거래처로 발주서를 보내기 직전에 멈춰
팀장(= 화면 앞의 나)의 결재를 받은 뒤 이어서 실행하는 LangGraph 에이전트입니다.
나머지는 사람을 거치지 않고 자동으로 발송합니다. 그 과정을 아이소메트릭 사무실에서 캐릭터들이 서류를 들고
걸어 다니는 모습으로 보여 줍니다.

> 모두의연구소 10강 「사람이 승인하는 에이전트 만들기 [프로젝트]」 과제.
> **제출 보고서는 [REPORT.md](REPORT.md)** — 주제, 구조도, 승인 기준과 이유, 실행 결과, 화면 설계, 회고.

![결재 창](docs/captures/text-v3.png)

---

## 무엇을 하는가

```
 실데이터(UCI Online Retail II) — 이번 주 발주 후보 200건
      ▼
 ① 입고      5건씩 문 앞에 도착
 ② AI 판단   분석가 3명(LLM, 병렬) — 발주량·이유·수요 신호
 ③ 기준 검사  검사관 — 발주액 > £200  또는  발주량 > 8주 평균의 2배
      ├─ 통과 → ④ 자동 발송 (팩스 → 거래처, 사람 없이)
      └─ 걸림 → ⑤ 멈춤(interrupt) → 결재함 → 팀장(나)이 결재 → 이어서 실행(resume)
                    승인 · 수량 수정 후 승인 · 반려(사유) · 다시 판정(지시, 최대 2회)
```

- 되돌릴 수 없는 순간 = **발주서 팩스 발송**. 그 바로 앞에서만 멈춥니다.
- 멈춘 건은 **체크포인터**(로컬 SQLite / 배포 Postgres)에 저장되어, 서버를 껐다 켜도 결재함에 그대로 남습니다.
- 승인 기준은 **실행 전에 정한 규칙**으로, 실제 LLM 판단 1,000회를 **실제 다음 주 판매량**과 비교해 골랐습니다([REPORT §3](REPORT.md#3-승인-기준과-그-이유)).

## 빠른 시작 (로컬)

Python 3.12 · [uv](https://docs.astral.sh/uv/) 가 필요합니다. **API 키 없이** 녹화된 실제 LLM 판단으로 돌아갑니다.

```bash
uv sync
uv run uvicorn server.app:create_app --factory --port 8801
```

브라우저에서 **http://127.0.0.1:8801/** 을 엽니다.

1. 위에서 주(예: `2011-06-06`)를 고르고 **▶ 이번 주 처리** — 빠르게 보려면 **4× / 10×**, 한 번에 끝내려면 **⏭ 건너뛰기**
2. 결재함 탁자에 5건이 쌓이면 팀장이 확인하러 가고 **오른쪽 패널에 결재 중 서류 목록**이 뜹니다
3. 서류를 누르면 팀장이 가서 집어 오고 **가운데 결재 창**이 열립니다 — 다섯 칸을 보고 승인·수정·반려
4. **📠 발송 기록**(실제로 나간 발주서) · **📊 기준 검증**(기준을 왜 이렇게 정했나) 탭

| 조작 | |
|---|---|
| 휠 · 드래그 · 더블클릭 | 사무실 확대·축소 · 이동 · 전체 보기 (왼쪽 아래 ＋ − ⤢ 버튼도 같음) |
| `G` 키 | 칸 번호 격자 + 가구 발자국(빨간 네모) 표시 |
| ↺ 처음부터 | 이 브라우저의 결재함 초기화 |
| 🔑 내 키 → 🟢 라이브 | 내 OpenAI 키로 200건을 **지금 새로** 판단(약 200회 호출 · 약 $0.05), 🔁 다시 판정도 켜짐. 키는 브라우저에만 저장 |

`.env`(선택): `cp .env.example .env` — `OPENAI_API_KEY`(판단을 다시 돌릴 때), `DATABASE_URL`(Postgres 체크포인터).

## 데이터와 판단 다시 만들기

```bash
uv run python -m data.prepare                                   # 원본 내려받기(약 45MB) → data/weeks/*.json (주당 200건)
uv run python -m scripts.judge_week --week 2011-06-06 --samples 3   # LLM 판단 → runs/<주>/judgments.json (비용 안내 후 확인)
uv run python -m scripts.evaluate                               # 기준 비교표 → runs/eval.json, runs/selected.json
uv run python -m scripts.graph_mermaid                          # 구조도(Mermaid)를 코드에서 뽑기
```

- `judge_week` 는 실행 전에 예상 호출 수·토큰을 보여 주고 확인을 받습니다. 끊겨도 다시 실행하면 이어서 돕니다.
  키가 틀리거나(401) 지출 한도·잔액이 부족하면(`insufficient_quota`) **첫 호출에서 멈추고 아무것도 저장하지 않습니다.**
- 녹화된 주: 개발 `2011-06-06`(3회 반복) · 검증 `2011-09-05`, `2011-10-03` · 재생용 `2011-07-04`, `2011-11-07`.
  기준 검증에는 개발·검증 주만 씁니다.

## 테스트

```bash
uv run pytest -q          # 94 passed
```

| 파일 | 확인하는 것 |
|---|---|
| `test_metrics.py` | 채점 함수 — **교재 3강 비교표를 그대로 재현** |
| `test_order_graph.py` | 기준에 안 걸리면 사람 없이 발송 · 걸리면 `review` 에서 멈춤 · 네 가지 응답 · 다시 판정 2회 상한 · **동시 승인 → 팩스 1건** · **다른 프로세스로 재시작해도 대기 건 유지** · resume 때 알림이 두 번 나가지 않음(교재 2강 함정) |
| `test_judge.py` · `test_batch_graph.py` | 정답(다음 주 판매)이 프롬프트에 새지 않음 · 재시도 · 401·쿼터에서 즉시 중단 · 이어하기 캐시 |
| `test_server.py` | 세션 격리(401/403) · 결재 400/409 · 72시간 기한 초과 · 라이브(방문자 키) |
| `test_compare.py` | 사전 등록 선택 규칙 · 흔들림 폭 · C5 선택 시 샘플 부족 감지 |
| `tests/web/*.mjs` (node) | 사무실 재연 — 5건 묶음 · 팀장 흐름 · 숫자 일치 · **가구를 피한 경로** · 캐릭터 겹침 · 말풍선 배치 |

## 폴더 구조

```
agent/     settings(스펙 고정값) · rules(승인 기준) · judge(LLM) · store(색인·팩스 로그) ·
           order_graph(발주 건 HITL) · batch_graph(Send 병렬 판단)
data/      prepare.py · weeks/<주>.json (+ .answers.json = 정답, eval/ 만 읽음)
eval/      metrics(라벨·세는 값·선택 규칙) · compare(비교표)
server/    app.py(FastAPI · SSE) · events.py
web/       index.html · src/(renderer·office·path·bubbles·panels·main …) · assets/(Kenney CC0)
runs/      LLM 판단 캐시 · eval.json · selected.json
scripts/   judge_week · evaluate · graph_mermaid · export_props · shot.sh
tests/     pytest + tests/web(node)
docs/      superpowers/specs(설계 스펙) · plans(구현 계획) · captures(화면) · 소품(배치용 PNG)
```

## API

모든 요청은 `X-Session` 헤더(세션 ID)가 필요합니다. `X-OpenAI-Key` 는 라이브·다시 판정 때만 보내며 서버에 저장하지 않습니다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/api/session` · GET `/api/session-info` | 세션 만들기 / 확인 |
| POST | `/api/run` `{week, live?}` | 주 처리 시작 (녹화 재생 또는 라이브) |
| GET | `/api/events?session=` | SSE — 판단·멈춤·발송 이벤트 |
| GET | `/api/summary?week=` · `/api/pending?week=` | 현황 · 대기 목록 (`next == ('review',)`) |
| GET | `/api/orders/{tid}` | 결재 화면 내용(다섯 칸) |
| POST | `/api/orders/{tid}/decision` | `approve` · `edit{qty}` · `reject{reason}` · `redo{instruction}` → `Command(resume)` |
| GET | `/api/faxlog?week=` · `/api/eval` | 발송 기록 · 기준 검증 |
| POST | `/api/reset` | 세션 초기화 |

## 알려진 한계

- **라벨 단순화**: "사람이 봤어야 할 건" = |AI 발주량 − 실제 판매| × 단가 > £100. 과잉 재고와 품절을 같은 무게로 봅니다.
- 발주서 발송은 **목(가짜) 팩스 로그**입니다. 실제 거래처 연동은 없습니다.
- 사무실 재연은 서버보다 느려(캐릭터가 걸어서 5건씩) 서버의 대기 건이 장면보다 먼저 늘 수 있습니다. 결재 패널·현황판·설명란은 장면 기준으로 맞춰 두었습니다.
- 캐릭터끼리는 좁은 통로에서 드물게 겹칩니다(시뮬레이션 실측 1.2%의 시간).

## 출처

- 데이터: [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) (CC BY 4.0)
- 그림: [Kenney](https://kenney.nl) Furniture Kit · Shape Characters (CC0) — [web/assets/CREDITS.md](web/assets/CREDITS.md)
- 설계·계획: [스펙](docs/superpowers/specs/2026-09-28-재고발주-hitl-design.md) · [구현 계획](docs/superpowers/plans/2026-09-28-재고발주-hitl.md)
