"""그래프 구조를 코드에서 직접 Mermaid 로 뽑는다 — 문서의 그림이 코드와 어긋나지 않게."""
from langgraph.checkpoint.memory import InMemorySaver

from agent.batch_graph import build_batch_graph
from agent.order_graph import build_order_graph

print("```mermaid\n" + build_batch_graph().get_graph().draw_mermaid() + "```\n")
print("```mermaid\n" + build_order_graph(InMemorySaver()).get_graph().draw_mermaid() + "```")
