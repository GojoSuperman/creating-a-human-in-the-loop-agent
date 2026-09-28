"""승인 기준 — 스펙 §3.1. 계산 가능한 형태로만 적는다."""
from statistics import median

COMBOS = [
    ("기준 없음", []),
    ("C1(£100)", ["C1:100"]),
    ("C1(£200)", ["C1:200"]),
    ("C1(£300)", ["C1:300"]),
    ("C1(£200)+C2", ["C1:200", "C2"]),
    ("C1(£200)+C2+C3", ["C1:200", "C2", "C3"]),
    ("C1(£200)+C2+C4", ["C1:200", "C2", "C4"]),
    ("C1(£200)+C2+C4+C5", ["C1:200", "C2", "C4", "C5"]),
    ("전부 멈춤", ["ALL"]),
]


def _flag(rule, text, measured=None, threshold=None):
    return {"rule": rule, "text": text, "measured": measured, "threshold": threshold}


def spread(samples):
    qs = [s["qty"] for s in samples if "error" not in s]
    if len(qs) < 2:
        return None
    m = median(qs)
    if m == 0:
        return 1.0 if max(qs) > 0 else 0.0
    return (max(qs) - min(qs)) / m


def evaluate(item, judgment, samples, combo):
    if "error" in judgment:    # 안전장치 — 모르면 사람에게 (조합과 무관하게 항상)
        return [_flag("F", "AI 판단 실패 — 수량을 사람이 정해야 합니다")]
    qty, price, mean8 = judgment["qty"], item["price_gbp"], item["mean8"]
    out = []
    for r in combo:
        if r == "ALL":
            out.append(_flag("ALL", "전부 멈춤 설정"))
        elif r.startswith("C1:"):
            lim = float(r.split(":", 1)[1])
            amt = qty * price
            if amt > lim:
                out.append(_flag(r, f"발주액 £{amt:,.0f} > 기준 £{lim:,.0f}", round(amt, 2), lim))
        elif r == "C2":
            if qty > 2 * mean8:
                out.append(_flag("C2", f"발주량 {qty:,}개 = 8주 평균의 {qty / mean8:.1f}배 > 2배",
                                 round(qty / mean8, 2), 2))
        elif r == "C3":
            if item["cv8"] > 1.2:
                out.append(_flag("C3", f"판매 변동계수 {item['cv8']:.2f} > 1.2", item["cv8"], 1.2))
        elif r == "C4":
            if judgment["demand_signal"] in ("급증", "감소"):
                out.append(_flag("C4", f"AI 수요 신호 '{judgment['demand_signal']}'",
                                 judgment["demand_signal"], "급증/감소"))
        elif r == "C5":
            s = spread(samples)
            if s is not None and s > 0.3:
                out.append(_flag("C5", f"3회 판단 흔들림 {s:.0%} > 30%", round(s, 3), 0.3))
        else:
            raise ValueError(f"알 수 없는 기준: {r}")
    return out
