from eval.metrics import label, loss_gbp, measure, select

# 교재 3강 — should_stop 은 교재가 준 정답
REQUESTS = [
    {"id": "R1", "amount": 12000, "should_stop": False, "text": "택배 박스가 찢어진 채로 왔어요. 환불해 주세요."},
    {"id": "R2", "amount": 28000, "should_stop": False, "text": "색상이 상세페이지 사진과 너무 달라요. 반품할게요."},
    {"id": "R3", "amount": 310000, "should_stop": True, "text": "코트를 한 달 입었는데 어깨 솔기가 터졌습니다."},
    {"id": "R4", "amount": 45000, "should_stop": True, "text": "사이즈 교환하려다가 그냥 환불로 바꿀게요."},
    {"id": "R5", "amount": 9000, "should_stop": True, "text": "그냥 마음에 안 들어요. 전액 환불해 주세요."},
]
TEXTBOOK = [   # (기준, limit, words, 개입, 놓침, 헛멈춤)
    ("기준 없음", 10**9, [], 0, 3, 0),
    ("10만 원 초과", 100000, [], 1, 2, 0),
    ("3만 원 초과", 30000, [], 2, 1, 0),
    ("3만 원 초과 + 표현", 30000, ["마음에 안", "단순 변심"], 3, 0, 0),
    ("5천 원 초과", 5000, [], 5, 0, 2),
    ("전부 멈춤", 0, [], 5, 0, 2),
]


def test_measure_reproduces_textbook_table():
    for name, limit, words, stopped, missed, false_stop in TEXTBOOK:
        cases = [{"stopped": r["amount"] > limit or any(w in r["text"] for w in words),
                  "should_stop": r["should_stop"], "loss": 0.0} for r in REQUESTS]
        m = measure(cases)
        assert (m["stopped"], m["missed"], m["false_stop"]) == (stopped, missed, false_stop), name


def test_loss_and_label_threshold_is_strict():
    assert loss_gbp(30, 10, 5.0) == 100.0
    assert label(30, 10, 5.0) is False          # 정확히 £100 은 멈춤 대상 아님 (> £100)
    assert label(31, 10, 5.0) is True


def test_measure_sums_missed_loss_and_ratios():
    cases = [
        {"stopped": False, "should_stop": True, "loss": 150.0},
        {"stopped": False, "should_stop": True, "loss": 250.5},
        {"stopped": True, "should_stop": False, "loss": 10.0},
        {"stopped": True, "should_stop": True, "loss": 400.0},
    ]
    m = measure(cases)
    assert m["missed"] == 2 and m["missed_loss"] == 400.5
    assert m["rate"] == 0.5 and m["false_ratio"] == 0.5


def test_measure_empty_is_zero_not_crash():
    assert measure([])["rate"] == 0.0


def test_select_rule_min_missed_loss_under_rate_cap_then_false_stop():
    rows = [
        {"name": "A", "rate": 0.10, "missed_loss": 900.0, "false_stop": 1},
        {"name": "B", "rate": 0.20, "missed_loss": 300.0, "false_stop": 9},
        {"name": "C", "rate": 0.25, "missed_loss": 300.0, "false_stop": 4},   # 동률 → 헛멈춤 적은 C
        {"name": "D", "rate": 0.40, "missed_loss": 0.0, "false_stop": 30},    # 상한 초과 → 제외
    ]
    s = select(rows)
    assert s["name"] == "C" and s["fallback"] is False


def test_select_fallback_when_nothing_under_cap():
    rows = [{"name": "X", "rate": 0.5, "missed_loss": 1.0, "false_stop": 0},
            {"name": "Y", "rate": 0.3, "missed_loss": 9.0, "false_stop": 0}]
    s = select(rows)
    assert s["name"] == "Y" and s["fallback"] is True
