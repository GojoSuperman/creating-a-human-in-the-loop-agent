"""runs/ 의 판단으로 기준 비교표를 만들고 사전 등록 규칙으로 기준을 고른다."""
import sys

from eval.compare import NeedMoreSamples, evaluate_all


def fmt(rows):
    out = ["| 기준 | 개입률 | 놓침 | 놓친 손해(£) | 헛멈춤 | 헛멈춤 비율 |", "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['name']} | {r['rate']:.1%} | {r['missed']} | {r['missed_loss']:,.0f} | "
                   f"{r['false_stop']} | {r['false_ratio']:.0%} |")
    return "\n".join(out)


def main():
    try:
        doc = evaluate_all()
    except NeedMoreSamples as e:
        print(f"⚠ {e}")
        return 2
    d = doc["dev"]
    print(f"## 개발 주 {d['week']} (샘플 1) — 판단 실패 {d['tables'][0]['failed']}건, 멈춰야 할 건 {d['tables'][0]['positives']}건")
    print(fmt(d["tables"][0]["rows"]))
    print(f"\n사전 등록 규칙의 선택: {doc['preregistered']['name']}")
    print(f"보정 후 선택: {doc['selected']['name']} (fallback={doc['selected']['fallback']}) — {doc['amendment']}")
    for t in doc["tests"]:
        print(f"\n## 검증 주 {t['week']} — 멈춰야 할 건 {t['table']['positives']}건")
        print(fmt(t["table"]["rows"]))
        print(f"기준선: LLM 손해 £{t['baseline']['llm_loss']:,.0f} vs 단순 평균 £{t['baseline']['naive_loss']:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
