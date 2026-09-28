"""배치 그래프 — 이번 주 200건을 Send 로 나눠 동시에 판단한다 (스펙 §2.1, 병렬화 패턴)."""
import json
import operator
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send

from agent.judge import judge_item
from agent.settings import LLM_CONCURRENCY


class BatchState(TypedDict):
    week: str
    items: list
    results: Annotated[list, operator.add]


@dataclass
class BatchCtx:
    judge_fn: Callable[[dict], list]
    on_judged: Callable[[dict, list], None] = lambda item, samples: None
    emit: Callable[[dict], None] = lambda e: None


def analyst_of(code):
    return sum(map(ord, code)) % 3


def prepare_week(state):
    return {}


def fan_out(state):
    return [Send("judge_item", {"item": it, "week": state["week"]}) for it in state["items"]]


def judge_item_node(state, runtime: Runtime[BatchCtx]):
    item, ctx = state["item"], runtime.context
    ev = {"code": item["code"], "analyst": analyst_of(item["code"]), "week": state["week"]}
    ctx.emit({"type": "judging", **ev})
    samples = ctx.judge_fn(item)
    ctx.emit({"type": "judged", **ev})
    ctx.on_judged(item, samples)          # 판단이 끝난 건부터 바로 발주 건 스레드로
    return {"results": [{"code": item["code"], "samples": samples}]}


def collect(state):
    return {}


def build_batch_graph():
    g = StateGraph(BatchState, context_schema=BatchCtx)
    g.add_node("prepare_week", prepare_week)
    g.add_node("judge_item", judge_item_node)
    g.add_node("collect", collect)
    g.add_edge(START, "prepare_week")
    g.add_conditional_edges("prepare_week", fan_out, ["judge_item"])
    g.add_edge("judge_item", "collect")
    g.add_edge("collect", END)
    return g.compile()


def run_batch(week, items, ctx, concurrency=LLM_CONCURRENCY):
    out = build_batch_graph().invoke({"week": week, "items": items, "results": []},
                                     {"max_concurrency": concurrency}, context=ctx)
    return {r["code"]: r["samples"] for r in out["results"]}


class JudgmentCache:
    """runs/<주>/judgments.json — 건 단위로 바로 저장해 중간에 끊겨도 이어서 돈다."""

    def __init__(self, path, week, model, samples):
        self.path, self.samples, self.lock = Path(path), samples, threading.Lock()
        if self.path.exists():
            self.doc = json.loads(self.path.read_text(encoding="utf-8"))
            if self.doc["model"] != model:
                raise ValueError(f"캐시 모델({self.doc['model']})과 요청 모델({model})이 다릅니다")
            self.doc["samples"] = max(self.doc["samples"], samples)
        else:
            self.doc = {"week": week, "model": model, "samples": samples, "items": {}}

    def get(self, code):
        v = self.doc["items"].get(code)
        return v if v and len(v) >= self.samples else None

    def put(self, code, samples):
        with self.lock:
            self.doc["items"][code] = samples
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.doc, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)


def live_judge_fn(llm, cache, samples_n):
    def fn(item):
        hit = cache.get(item["code"])
        if hit:
            return hit
        have = list(cache.doc["items"].get(item["code"], []))
        while len(have) < samples_n:
            have.append(judge_item(item, llm))     # QuotaExceeded 는 위로 — 이 건은 저장 안 됨
        cache.put(item["code"], have)
        return have
    return fn


def cached_judge_fn(doc):
    return lambda item: doc["items"][item["code"]]
