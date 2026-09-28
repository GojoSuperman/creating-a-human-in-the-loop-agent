import statistics as st


def mk_item(code, price=2.0, hist=(10, 12, 8, 11, 9, 10, 13, 7)):
    h = list(hist)
    m = sum(h) / len(h)
    s = st.stdev(h)
    return {"code": code, "name_en": f"ITEM {code}", "price_gbp": price, "hist8": h,
            "mean8": round(m, 2), "std8": round(s, 2), "cv8": round(s / m, 3),
            "last_week": h[-1]}


def mk_j(qty, signal="평소", name="상품"):
    return {"qty": qty, "reason_ko": "최근 판매가 일정함", "demand_signal": signal, "name_ko": name}


class FakeLLM:
    """responses 를 차례로 돌려준다. 마지막 것은 계속 반복. 예외면 raise."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def judge(self, system, user):
        self.calls.append(user)
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r
