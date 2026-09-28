"""소품·캐릭터 스프라이트를 한 장씩 투명 PNG 로 뽑는다 — 배치를 사람이 직접 짜 볼 수 있게."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FURN = ROOT / "web" / "assets" / "furniture"
CHAR = ROOT / "web" / "assets" / "characters"
OUT = ROOT / "docs" / "소품"

USED = {  # 장면에 쓰는 것 (config.js PROPS·WALL) → 한국어 이름
    "sideTable": "보조탁자(입고함·팩스대·결재함)", "desk": "책상(분석가·검사관)",
    "computerScreen": "모니터(책상 위)", "laptop": "노트북(검사관 책상 위)",
    "kitchenCoffeeMachine": "커피머신(팩스기 대용)", "deskCorner": "코너책상(팀장)",
    "bookcaseClosed": "책장(캐비닛)", "trashcan": "휴지통(반려)", "pottedPlant": "화분",
    "wall": "벽", "wallDoorway": "벽-문", "wallWindow": "벽-창문", "floorFull": "바닥타일",
}
DIRS = {"SE": "남동", "SW": "남서", "NE": "북동", "NW": "북서"}
CAST = {"a0": ("blue", "circle", "김분석가"), "a1": ("green", "circle", "이분석가"),
        "a2": ("pink", "circle", "박분석가"), "insp": ("red", "square", "최검사관"),
        "boss": ("purple", "squircle", "팀장")}
FACE = {"cx": 40, "cy": 33, "gap": 24, "mouth": 54}   # actors.js 와 같은 실측값
HAND = {"y": 34, "gap": -2}


def trimmed(path):
    im = Image.open(path).convert("RGBA")
    box = im.getbbox()
    return im.crop(box) if box else im


def actor(color, shape):
    body = Image.open(CHAR / f"{color}_body_{shape}.png").convert("RGBA")
    eye = Image.open(CHAR / "facial_part_eye_open.png").convert("RGBA")
    hand = Image.open(CHAR / f"{color}_hand_open.png").convert("RGBA")
    pad = hand.width + 4
    W, H = body.width + pad * 2, body.height + 10
    c = Image.new("RGBA", (W, H))
    bx = pad
    c.alpha_composite(body, (bx, 0))
    for dx in (-FACE["gap"] / 2, FACE["gap"] / 2):
        c.alpha_composite(eye, (int(bx + FACE["cx"] + dx - eye.width / 2), int(FACE["cy"] - eye.height / 2)))
    c.alpha_composite(hand.transpose(Image.FLIP_LEFT_RIGHT), (int(bx - HAND["gap"] - hand.width), HAND["y"]))
    c.alpha_composite(hand, (int(bx + body.width + HAND["gap"]), HAND["y"]))
    return c.crop(c.getbbox())


def main():
    n = 0
    (OUT / "1-사용중").mkdir(parents=True, exist_ok=True)
    for key, ko in USED.items():
        trimmed(FURN / f"{key}_SE.png").save(OUT / "1-사용중" / f"{ko}__{key}.png"); n += 1
    (OUT / "2-캐릭터").mkdir(parents=True, exist_ok=True)
    for role, (color, shape, ko) in CAST.items():
        actor(color, shape).save(OUT / "2-캐릭터" / f"{ko}__{role}.png"); n += 1
    (OUT / "3-예비-전체4방향").mkdir(parents=True, exist_ok=True)
    for p in sorted(FURN.glob("*_*.png")):
        key, d = p.stem.rsplit("_", 1)
        trimmed(p).save(OUT / "3-예비-전체4방향" / f"{key}__{DIRS.get(d, d)}.png"); n += 1
    print(f"{n}장 저장 → {OUT}")


if __name__ == "__main__":
    main()
