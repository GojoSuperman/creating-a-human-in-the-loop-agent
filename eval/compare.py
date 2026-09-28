"""기준 비교표 — 사전 등록 규칙(스펙 §3.4)대로 개발 주에서 고르고 검증 주에 적용한다."""
import json
from pathlib import Path

from agent.rules import COMBOS
from agent.rules import evaluate as apply_rules
from agent.settings import DATA_WEEKS, DEV_WEEK, LABEL_LOSS_GBP, MAX_RATE, RUNS, TEST_WEEKS
from eval.metrics import loss_gbp, measure, select

METRICS = ("rate", "missed", "missed_loss", "false_stop")


class NeedMoreSamples(Exception):
    pass


def cases(items, actual, samples_by_code, combo, idx=0):
    out, failed = [], 0
    for it in items:
        ss = samples_by_code[it["code"]]
        j = ss[idx] if idx < len(ss) else ss[0]
        if "error" in j:              # 안전장치로 항상 멈추는 건 — 표에서 따로 센다
            failed += 1
            continue
        loss = loss_gbp(j["qty"], actual[it["code"]], it["price_gbp"])
        out.append({"code": it["code"], "stopped": bool(apply_rules(it, j, ss, combo)),
                    "should_stop": loss > LABEL_LOSS_GBP, "loss": round(loss, 2)})
    return out, failed


def table(items, actual, samples_by_code, idx=0, combos=None):
    rows, failed, positives = [], 0, 0
    for name, combo in (combos if combos is not None else COMBOS):
        cs, failed = cases(items, actual, samples_by_code, combo, idx)
        positives = sum(1 for c in cs if c["should_stop"])
        rows.append({"name": name, "combo": combo, **measure(cs)})
    return {"rows": rows, "failed": failed, "positives": positives}


def baseline(items, actual, samples_by_code, idx=0):
    llm = naive = 0.0
    for it in items:
        ss = samples_by_code[it["code"]]
        j = ss[idx] if idx < len(ss) else ss[0]
        if "error" in j:
            continue
        llm += loss_gbp(j["qty"], actual[it["code"]], it["price_gbp"])
        naive += loss_gbp(round(it["mean8"]), actual[it["code"]], it["price_gbp"])
    return {"llm_loss": round(llm, 2), "naive_loss": round(naive, 2)}


def _load(weeks_dir, runs_dir, week):
    items = json.loads((Path(weeks_dir) / f"{week}.json").read_text(encoding="utf-8"))["items"]
    actual = json.loads((Path(weeks_dir) / f"{week}.answers.json").read_text(encoding="utf-8"))["actual"]
    doc = json.loads((Path(runs_dir) / week / "judgments.json").read_text(encoding="utf-8"))
    return items, actual, doc


def evaluate_all(weeks_dir=DATA_WEEKS, runs_dir=RUNS):
    items, actual, jd = _load(weeks_dir, runs_dir, DEV_WEEK)
    n = jd["samples"]
    tables = [table(items, actual, jd["items"], idx=i, combos=COMBOS) for i in range(n)]
    spread = {}
    for k, (name, _) in enumerate(COMBOS):
        spread[name] = {m: [min(t["rows"][k][m] for t in tables), max(t["rows"][k][m] for t in tables)]
                        for m in METRICS}
    picked = select(tables[0]["rows"], MAX_RATE)
    selected = {"name": picked["name"], "combo": picked["combo"], "fallback": picked["fallback"]}
    tests = []
    for week in TEST_WEEKS:
        ti, ta, td = _load(weeks_dir, runs_dir, week)
        if "C5" in selected["combo"] and td["samples"] < 3:
            raise NeedMoreSamples(f"{week}: C5 가 선택됐으니 --samples 3 으로 다시 판단해야 합니다")
        t = table(ti, ta, td["items"], combos=COMBOS)
        row = next(r for r in t["rows"] if r["name"] == selected["name"])
        tests.append({"week": week, "table": t, "selected_row": row, "baseline": baseline(ti, ta, td["items"])})
    doc = {"model": jd["model"], "label_loss_gbp": LABEL_LOSS_GBP, "max_rate": MAX_RATE,
           "dev": {"week": DEV_WEEK, "samples": n, "tables": tables, "spread": spread,
                   "baseline": baseline(items, actual, jd["items"])},
           "selected": selected, "tests": tests}
    Path(runs_dir).mkdir(parents=True, exist_ok=True)
    (Path(runs_dir) / "eval.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(runs_dir) / "selected.json").write_text(json.dumps(selected, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc
