from __future__ import annotations
from langgraph.graph import StateGraph, END
from .state import RunState
from .nodes.intake import intake_node
from .nodes.profile import profile_node
from .nodes.target import target_detect_node
from .nodes.eda import eda_node
from .nodes.insights import insights_node
from .logging_config import setup_logging
from langgraph.graph.state import CompiledStateGraph

logger = setup_logging(name="graph")


def build_graph() -> CompiledStateGraph:
    logger.info("Building graph...")
    g = StateGraph(RunState)
    g.add_node("profile", profile_node)
    g.add_node("target_detect", target_detect_node)
    g.add_node("intake", intake_node)
    g.add_node("eda", eda_node)
    g.add_node("insights", insights_node)

    g.set_entry_point("profile")
    g.add_edge("profile", "target_detect")
    g.add_edge("target_detect", "intake")
    g.add_edge("intake", "eda")
    g.add_edge("eda", "insights")
    g.add_edge("insights", END)
    logger.info("Graph built: profile -> target_detect -> intake -> eda -> insights")
    return g.compile()


def visualize_graph(output_path: str = "graph_visualization.png") -> str | None:
    """Render the compiled graph to a PNG. Returns the path, or None if unavailable."""
    try:
        graph = build_graph().get_graph()
        png = graph.draw_mermaid_png()
        with open(output_path, "wb") as f:
            f.write(png)
        return output_path
    except Exception as e:
        logger.error(f"Failed to visualize graph: {e}")
        return None


if __name__ == "__main__":
    path = visualize_graph()
    print(f"Saved graph to {path}" if path else "Could not render graph (needs graphviz + pillow)")
