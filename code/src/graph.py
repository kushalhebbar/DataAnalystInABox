from __future__ import annotations
from langgraph.graph import StateGraph, END
from .state import RunState
from .nodes.intake import intake_node
from .nodes.profile import profile_node
from .nodes.target import target_detect_node
from .logging_config import setup_logging
from langgraph.graph.state import CompiledStateGraph

logger = setup_logging(name="graph")


def build_graph() -> CompiledStateGraph:
    logger.info("Building graph...")
    g = StateGraph(RunState)
    g.add_node("profile", profile_node)
    g.add_node("target_detect", target_detect_node)
    g.add_node("intake", intake_node)

    g.set_entry_point("profile")
    g.add_edge("profile", "target_detect")
    g.add_edge("target_detect", "intake")
    g.add_edge("intake", END)
    logger.info("Graph built successfully: profile -> target_detect -> intake")
    return g.compile()


def visualize_graph(output_path: str = "graph_visualization.png") -> str | None:
    """
    Generate a visualization of the graph and save to file.
    
    Args:
        output_path: Path to save the visualization (png, svg, etc.)
    
    Returns:
        str | None: Path to saved visualization, or None if failed
    """
    try:
        app = build_graph()
        
        # Check if mermaid output is available
        if hasattr(app, 'get_graph'):
            graph = app.get_graph()
            
            # Try mermaid representation
            if hasattr(graph, 'draw_mermaid_png'):
                logger.info(f"Generating mermaid PNG visualization...")
                png_data = graph.draw_mermaid_png()
                with open(output_path, "wb") as f:
                    f.write(png_data)
                logger.info(f"Graph saved to: {output_path}")
                return output_path
            
            # Fallback to ASCII representation
            elif hasattr(graph, 'draw_ascii'):
                logger.info("Generating ASCII visualization...")
                ascii_repr = graph.draw_ascii()
                txt_path = output_path.replace(".png", ".txt")
                with open(txt_path, "w") as f:
                    f.write(ascii_repr)
                logger.info(f"ASCII graph saved to: {txt_path}")
                return txt_path
        
        logger.warning("Graph visualization not available - LangGraph version may not support it")
        return None
        
    except Exception as e:
        logger.error(f"Failed to visualize graph: {str(e)}", exc_info=True)
        return None


def print_graph_structure() -> None:
    """
    Print the graph structure to console and logs.
    """
    logger.info("=" * 60)
    logger.info("GRAPH STRUCTURE")
    logger.info("=" * 60)
    
    structure = """
    Entry Point: profile
    
    Nodes:
    ├─ profile_node
    │  └─ Reads CSV, computes profile stats, checks for PII
    ├─ target_detect_node
    │  └─ Identifies candidate target columns (if not user-provided)
    └─ intake_node
       └─ Calls LLM to generate improved statement and clarification questions
    
    Edges:
    profile → target_detect → intake → END
    """
    
    logger.info(structure)
    print(structure)


def main() -> None:
    """Main entry point for graph visualization."""
    logger.info("Starting graph visualization...")
    print_graph_structure()
    
    # Try to generate visual representation
    result = visualize_graph("graph_visualization.png")
    if result:
        logger.info(f"✓ Graph visualization saved to: {result}")
        print(f"\n✓ Graph visualization saved to: {result}")
    else:
        logger.warning("Could not generate visual graph. Try installing graphviz:")
        logger.warning("  brew install graphviz")
        logger.warning("  pip install pillow")
        print("\n⚠ Could not generate visual graph. Try installing:")
        print("  brew install graphviz")
        print("  pip install pillow")


if __name__ == "__main__":
    main()
