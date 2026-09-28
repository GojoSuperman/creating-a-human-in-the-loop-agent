"""LLM 판단 실행 — 비용을 먼저 알리고 동의를 받는다. 끊기면 다시 실행해 이어 간다."""
import argparse
import json
import os
import sys

from agent.batch_graph import BatchCtx, JudgmentCache, live_judge_fn, run_batch
from agent.judge import OpenAILLM, QuotaExceeded
from agent.settings import DATA_WEEKS, DEFAULT_MODEL, EST_IN_TOKENS, EST_OUT_TOKENS, RUNS, load_env


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--week", required=True)
    p.add_argument("--samples", type=int, default=1)
    p.add_argument("--model", default=None)
    p.add_argument("--yes", action="store_true")
    a = p.parse_args(argv)
    load_env()
    model = a.model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    items = json.loads((DATA_WEEKS / f"{a.week}.json").read_text(encoding="utf-8"))["items"]
    cache = JudgmentCache(RUNS / a.week / "judgments.json", a.week, model, a.samples)
    todo = [it for it in items if cache.get(it["code"]) is None]
    calls = sum(a.samples - len(cache.doc["items"].get(it["code"], [])) for it in todo)
    print(f"[{a.week}] 모델 {model} · 남은 {len(todo)}건 · 예상 호출 {calls}회 · "
          f"예상 토큰 입력 {calls * EST_IN_TOKENS:,} / 출력 {calls * EST_OUT_TOKENS:,}")
    if calls == 0:
        return 0
    if not a.yes and input("진행할까요? [y/N] ").strip().lower() != "y":
        return 1
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY 가 없습니다 (.env 확인)")
    llm = OpenAILLM(key, model)
    code = 0
    try:
        run_batch(a.week, todo, BatchCtx(judge_fn=live_judge_fn(llm, cache, a.samples)))
    except QuotaExceeded:
        print("⛔ OpenAI 사용 한도 초과 — 중단했습니다. 끝난 건은 캐시에 남았으니 다시 실행하면 이어집니다.")
        code = 3
    errors = sum(1 for v in cache.doc["items"].values() for j in v if "error" in j)
    print(f"사용량: {llm.usage} · 판단 실패 {errors}건 · 캐시 {len(cache.doc['items'])}/{len(items)}건")
    return code


if __name__ == "__main__":
    sys.exit(main())
