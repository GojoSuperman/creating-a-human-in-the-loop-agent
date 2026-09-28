import pandas as pd

from data.prepare import build_week, candidates, clean, weekly

WEEKS = pd.date_range("2011-01-03", periods=10, freq="7D")   # 월요일 10주


def rows(code, qtys, price=2.0, desc="MUG"):
    out = []
    for wk, q in zip(WEEKS, qtys):
        if q:
            out.append({"Invoice": "1000", "StockCode": code, "Description": desc,
                        "Quantity": q, "InvoiceDate": wk + pd.Timedelta(hours=10),
                        "Price": price, "Customer ID": 1.0, "Country": "UK"})
    return out


def frame():
    r = []
    r += rows("10001", [5, 5, 5, 5, 5, 5, 5, 5, 987654, 1])      # 8주 모두 판매
    r += rows("10002", [0, 0, 3, 3, 3, 3, 3, 3, 7, 1])           # 6주 판매 → 후보
    r += rows("10003", [0, 0, 0, 3, 3, 3, 3, 3, 7, 1])           # 5주 → 탈락
    r += rows("POST", [1] * 10)                                  # 코드 규칙 위반
    df = pd.DataFrame(r)
    bad = pd.DataFrame([
        {**r[0], "Quantity": -3}, {**r[0], "Price": 0.0}, {**r[0], "Invoice": "C999"},
    ])
    return pd.concat([df, bad], ignore_index=True)


def test_clean_drops_returns_zero_price_and_nonproduct_codes():
    df = clean(frame())
    assert (df.Quantity > 0).all() and (df.Price > 0).all()
    assert not df.Invoice.str.startswith("C").any()
    assert set(df.StockCode) == {"10001", "10002", "10003"}


def test_candidates_need_6_of_8_prior_weeks():
    w, _, _ = weekly(clean(frame()))
    assert candidates(w, "2011-02-28") == ["10001", "10002"]   # 9번째 주가 "오늘"


def test_build_week_hides_actual_and_is_deterministic():
    w, price, names = weekly(clean(frame()))
    items1, ans1 = build_week(w, price, names, "2011-02-28", n=2, seed=42)
    items2, _ = build_week(w, price, names, "2011-02-28", n=2, seed=42)
    assert items1 == items2
    it = {i["code"]: i for i in items1["items"]}["10001"]
    assert it["hist8"] == [5] * 8 and it["mean8"] == 5.0 and it["last_week"] == 5
    assert ans1["actual"]["10001"] == 987654
    assert "987654" not in str(items1)          # 정답이 입력 쪽에 새지 않는다
