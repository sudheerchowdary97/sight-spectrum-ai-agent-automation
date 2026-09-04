"""Assemble the node logic into a compiled LangGraph app and run it.

LangGraph is imported lazily (heavy dependency, Python ≤3.12), so importing this
module is safe everywhere; only building/running the graph needs LangGraph.
"""

from __future__ import annotations

from invoice_agent.config import Settings
from invoice_agent.ingestion.models import IngestedDocument
from invoice_agent.orchestration.nodes import AgentDeps, AgentNodes, route_after_match
from invoice_agent.orchestration.state import AgentState


def build_agent_graph(deps: AgentDeps):  # type: ignore[no-untyped-def]
    """Build and compile the agent StateGraph."""
    from langgraph.graph import END, START, StateGraph

    nodes = AgentNodes(deps)
    graph: StateGraph = StateGraph(AgentState)
    graph.add_node("extract", nodes.extract)
    graph.add_node("match", nodes.match)
    graph.add_node("post", nodes.post)
    graph.add_node("escalate", nodes.escalate)

    graph.add_edge(START, "extract")
    graph.add_edge("extract", "match")
    graph.add_conditional_edges(
        "match", route_after_match, {"post": "post", "escalate": "escalate"}
    )
    graph.add_edge("post", END)
    graph.add_edge("escalate", END)
    return graph.compile()


class AgentRunner:
    """Runs the compiled agent graph over a single ingested document."""

    def __init__(self, deps: AgentDeps) -> None:
        self._app = build_agent_graph(deps)

    def run(self, ingested: IngestedDocument) -> AgentState:
        initial: AgentState = {
            "ingested": ingested,
            "correlation_id": ingested.email_id or ingested.document_id,
            "audit": [],
        }
        return self._app.invoke(initial)


def build_agent_runner(settings: Settings) -> AgentRunner:
    """Build the real agent runner (Docling+Ollama extract, match, ERP posting)."""
    from invoice_agent.erp_client import ErpClient
    from invoice_agent.extraction.service import build_extraction_service
    from invoice_agent.matching.service import build_match_service
    from invoice_agent.posting import ErpPaymentPoster

    deps = AgentDeps(
        extractor=build_extraction_service(settings),
        matcher=build_match_service(settings),
        poster=ErpPaymentPoster(ErpClient(settings.erp_base_url)),
    )
    return AgentRunner(deps)
