# 에셋 출처 및 라이선스

> Deep-research-agent 프로젝트에서 가져왔다(같은 작성자). 재렌더 방법은 그 저장소의 tools/render_iso.py 참고.

이 디렉터리의 모든 이미지는 **Kenney** (https://kenney.nl) 제작이며 **CC0 1.0 (Public Domain Dedication)** 으로 배포됩니다.

> License: Creative Commons Zero, CC0
> https://creativecommons.org/publicdomain/zero/1.0/
>
> This content is free to use in personal, educational and commercial projects.
> Support us by crediting Kenney or www.kenney.nl (this is not mandatory)

CC0는 **저작자 표시 의무가 없지만**, 제작자의 요청에 따라 자발적으로 표기합니다.

## 사용한 팩

| 디렉터리 | 팩 | 원본 개수 | 사용 | 출처 |
|---|---|---|---|---|
| `characters/` | Shape Characters (1.0) | 100 | 104 파일 | https://kenney.nl/assets/shape-characters |
| `furniture/` | Furniture Kit (2.0) | 140 모델 | 27종 × 4방향 = 108 파일 (**직접 렌더**) | https://kenney.nl/assets/furniture-kit |

## 직접 렌더한 에셋 — `furniture/`

Furniture Kit 은 3D 모델 팩이고 2D Isometric PNG 도 들어 있지만, 그 PNG 는 오브젝트마다
다르게 크롭돼 있어 **타일 격자에 맞출 기준점이 없다**(투영비도 2.81:1 로 다르다).
그래서 3D 원본을 **Isometric Miniature 규격**(2:1 · 타일 256×128)으로 다시 렌더했다.

- 캔버스 384×768 — 타일(256×128)보다 크게 잡아야 책장처럼 타일을 넘는 오브젝트가 안 잘린다
- `ortho_scale = 2√2 × (H/512)`, `shift_y = 0.4267` — 기존 Miniature 타일과 대조해 역산
- 검증: `floorFull` 불투명 (0,382,256,512) · 허리 y=704 · 폭 256

Workbench STUDIO 렌더는 면별 음영을 남기지만 전체가 어두워져서(바닥 `#99816c`, 원본 `#ffcb81`)
밝기·채도를 원본에 맞춰 보정한다. 바닥만은 채도를 더 낮춰 가구가 묻히지 않게 한다.

재현: `blender -b -P tools/render_iso.py -- <models> <out>` → `python tools/보정.py <out> web/assets/furniture`

## 규격## 규격

- **characters** — 80×80px 몸통, 부품 조립식 (몸통 + 얼굴 + 손)
- **library / floor** — 256×512px, 4방향(`_N` `_E` `_W` `_S`), 정투영(Isometric) 버전

## 검토했으나 채택하지 않은 것

| 팩 | 사유 |
|---|---|
| Kenney Toon Characters | 측면 뷰 플랫포머용 — 아이소메트릭 부적합 |
| Kenney Robot Pack | 측면·상단 뷰만 제공, 4방향 없음 |
| Kenney Animal Pack | 정면 단일 방향 — 이동 방향 표현 불가 |
| Kenney Mini/Blocky Characters | 3D 모델(.obj/.glb) — 스프라이트 렌더링 공정 필요 |
| itch.io 8-Directional Character Pack | 유료 ($5) |
| OpenGameArt 아이소메트릭 캐릭터 | 판타지 테마 — 연구소 컨셉과 불일치 |
