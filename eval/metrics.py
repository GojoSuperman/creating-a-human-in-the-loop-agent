"""채점 — 스펙 §1.5 라벨, §3.3 세는 값, §3.4 선택 규칙. 이 모듈만 정답을 다룬다."""
from agent.settings import LABEL_LOSS_GBP, MAX_RATE


def loss_gbp(qty, actual, price):
    return abs(qty - actual) * price


def label(qty, actual, price, threshold=LABEL_LOSS_GBP):
    return loss_gbp(qty, actual, price) > threshold


def measure(cases):
    n = len(cases)
    stopped = sum(1 for c in cases if c["stopped"])
    missed = [c for c in cases if c["should_stop"] and not c["stopped"]]
    false_stop = [c for c in cases if c["stopped"] and not c["should_stop"]]
    return {
        "n": n,
        "stopped": stopped,
        "rate": stopped / n if n else 0.0,
        "missed": len(missed),
        "missed_loss": round(sum(c["loss"] for c in missed), 2),
        "false_stop": len(false_stop),
        "false_ratio": len(false_stop) / stopped if stopped else 0.0,
    }


def select(rows, max_rate=MAX_RATE):
    """개입률 상한 안에서 놓친 손해 최소, 동률이면 헛멈춤 최소. 없으면 개입률 최소(fallback)."""
    ok = [r for r in rows if r["rate"] <= max_rate]
    if not ok:
        return {**min(rows, key=lambda r: (r["rate"], r["missed_loss"])), "fallback": True}
    return {**min(ok, key=lambda r: (r["missed_loss"], r["false_stop"])), "fallback": False}
