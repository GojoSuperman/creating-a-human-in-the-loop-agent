"""LLM 발주 판단 — 입력은 과거 8주뿐. 실제 다음 주 판매는 여기에 오지 않는다."""
from typing import Literal, Protocol

import openai
from pydantic import BaseModel, Field, ValidationError

from agent.settings import DEFAULT_MODEL, EDIT_MAX_MULT


class Judgment(BaseModel):
    qty: int = Field(ge=0)
    reason_ko: str
    demand_signal: Literal["평소", "증가", "급증", "감소"]
    name_ko: str


class QuotaExceeded(RuntimeError):
    pass


class AuthFailed(RuntimeError):
    """키가 틀림 — 건별 실패가 아니라 실행 전체의 문제라 캐시하지 않고 멈춘다."""


SYSTEM = (
    "너는 영국 온라인 선물 도매점의 재고 발주 담당자다. 상품의 최근 8주 주간 판매량을 보고 "
    "다음 주에 들여올 수량 qty 를 정수로 정한다. 과잉 재고와 품절은 둘 다 손해다. "
    "reason_ko 는 팀장이 10초 안에 읽을 한두 문장의 한국어로, 판매 추세를 숫자로 근거 삼는다. "
    "demand_signal 은 다음 주 수요가 평소와 비교해 어떤지 평소/증가/급증/감소 중 하나다. "
    "name_ko 는 상품명의 자연스러운 한국어 번역이다."
)


def build_prompt(item, instruction=None, prev=None):
    lines = [
        f"상품 코드: {item['code']}",
        f"상품명: {item['name_en']}",
        f"단가: £{item['price_gbp']:.2f}",
        f"최근 8주 판매량(오래된 주 → 지난주): {item['hist8']}",
        f"8주 평균 {item['mean8']}, 표준편차 {item['std8']}, 변동계수 {item['cv8']}",
        f"지난주 판매: {item['last_week']}",
    ]
    if prev and "qty" in prev:
        lines.append(f"이전 판단: {prev['qty']}개 — {prev['reason_ko']}")
    if instruction:
        lines.append(f"팀장 지시: {instruction}")
    return "\n".join(lines)


class LLM(Protocol):
    def judge(self, system: str, user: str) -> dict: ...


class OpenAILLM:
    def __init__(self, api_key, model=DEFAULT_MODEL):
        self.client = openai.OpenAI(api_key=api_key, max_retries=2, timeout=60)
        self.model = model
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def judge(self, system, user):
        r = self.client.chat.completions.parse(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=Judgment,
        )
        self.usage["calls"] += 1
        if r.usage:
            self.usage["input_tokens"] += r.usage.prompt_tokens
            self.usage["output_tokens"] += r.usage.completion_tokens
        msg = r.choices[0].message
        if msg.parsed is None:
            raise ValueError(f"응답 파싱 실패: {msg.refusal or msg.content}")
        return msg.parsed.model_dump()


def validate(raw, item):
    j = Judgment.model_validate(raw).model_dump()
    if j["qty"] > EDIT_MAX_MULT * item["mean8"]:
        raise ValueError(f"발주량 {j['qty']}개가 8주 평균의 {EDIT_MAX_MULT}배를 넘음")
    return j


def judge_item(item, llm, instruction=None, prev=None, retries=1):
    user = build_prompt(item, instruction, prev)
    last = None
    for _ in range(retries + 1):
        try:
            return validate(llm.judge(SYSTEM, user), item)
        except openai.AuthenticationError as e:
            raise AuthFailed(str(e)[:200]) from e
        except openai.RateLimitError as e:
            if getattr(e, "code", None) == "insufficient_quota":
                raise QuotaExceeded(str(e)) from e
            last = e
        except (openai.OpenAIError, ValidationError, ValueError) as e:
            last = e
    return {"error": f"{type(last).__name__}: {str(last)[:200]}"}
