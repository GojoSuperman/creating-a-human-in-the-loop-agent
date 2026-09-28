"""스펙에서 고정한 값 — 여기서만 정의하고 나머지는 가져다 쓴다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_WEEKS = ROOT / "data" / "weeks"
RUNS = ROOT / "runs"
STATE = ROOT / "state"

N_ITEMS = 200
SEED = 42
DEV_WEEK = "2011-06-06"
TEST_WEEKS = ("2011-09-05", "2011-10-03")

LABEL_LOSS_GBP = 100.0     # 사전 등록 — 변경 금지 (스펙 §1.5)
GBP_KRW = 1800
MAX_RATE = 0.25            # 사전 등록 — 변경 금지 (스펙 §3.4)

REDO_MAX = 2
EDIT_MAX_MULT = 10
LLM_CONCURRENCY = 8
STALE_HOURS = 72
SESSION_TTL_HOURS = 24

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
EST_IN_TOKENS = 600        # 호출당 추정치 — 비용 안내용
EST_OUT_TOKENS = 150


def load_env(path: Path = ROOT / ".env") -> None:
    """KEY=VALUE 줄을 읽어 아직 없는 환경 변수만 채운다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def store_url() -> str:
    return os.getenv("DATABASE_URL") or f"sqlite:///{STATE / 'app.sqlite'}"


def checkpoint_url() -> str:
    # SQLite는 연결 두 개가 한 파일을 동시에 쓰면 잠기므로 파일을 나눈다
    return os.getenv("DATABASE_URL") or f"sqlite:///{STATE / 'checkpoints.sqlite'}"
