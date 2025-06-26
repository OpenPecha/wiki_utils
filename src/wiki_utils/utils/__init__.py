import json
import random
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import networkx as nx
from pyvis.network import Network


def write_json(data: dict | list, output_path: str | Path):
    with open(output_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(file_path: str | Path):
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    return data


def visualize_graph(graph_data: list[dict]):
    """
    Visualize data in Graph.
        data should be list of dictionary containg 'from', 'to' and 'relationship'.
    """

    # Create a directed graph
    G = nx.DiGraph()

    # Add edges and relationships as edge labels
    for entry in graph_data:
        from_node = entry["from"]
        to_node = entry["to"]
        relationship = entry["relationship"]
        G.add_edge(from_node, to_node, label=relationship)

    pos = nx.spring_layout(G, k=2.0, iterations=100)

    plt.figure(figsize=(16, 10))
    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color="lightblue",
        edge_color="gray",
        node_size=2000,
        font_size=10,
        arrows=True,
    )

    # Draw edge labels
    edge_labels = nx.get_edge_attributes(G, "label")
    nx.draw_networkx_edge_labels(
        G, pos, edge_labels=edge_labels, font_color="red", font_size=8
    )

    plt.title("Heart Sutra Walk Graph")
    plt.axis("off")
    plt.show()


def visualize_graph_interactive(
    graph_data: list[dict[str, str]],
    metadata: dict[str, dict],
    output_html: str = "graph.html",
):
    net = Network(height="800px", width="100%", directed=True)

    # Configure physics for more compact layout
    net.set_options(
        """
    var options = {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -800,
          "centralGravity": 0.1,
          "springLength": 200,
          "springConstant": 0.08,
          "damping": 0.15
        },
        "maxVelocity": 50,
        "minVelocity": 0.1,
        "solver": "barnesHut",
        "timestep": 0.35
      },
      "layout": {
        "improvedLayout": true
      }
    }
    """
    )

    # Collect unique node ids and edge types
    node_ids = set()
    edge_types = set()
    for entry in graph_data:
        node_ids.add(entry["from"])
        node_ids.add(entry["to"])
        edge_types.add(entry["relationship"])

    # Assign a color for each relationship type
    relationship_colors = {
        rel: f"#{random.randint(0, 0xFFFFFF):06x}" for rel in edge_types
    }

    # Add nodes with metadata (dictionary) as tooltip and large font
    for node_id in node_ids:
        label = node_id
        meta = metadata.get(node_id, {})
        # Convert dictionary to a string tooltip
        title = json.dumps(meta, indent=2) if meta else "No metadata available"
        net.add_node(
            node_id,
            label=label,
            title=title,
            font={"size": 20, "color": "black"},
            shape="dot",
            size=25,
        )

    # Add edges with color based on relationship type and shorter arrows
    for entry in graph_data:
        from_node = entry["from"]
        to_node = entry["to"]
        rel = entry["relationship"]
        color = relationship_colors.get(rel, "#999999")
        net.add_edge(
            from_node,
            to_node,
            label=rel,
            color=color,
            arrows="to",
            length=1000,  # Increased edge length for more spacing
            width=3,  # Thicker edges for better visibility
            smooth={"type": "curvedCW", "roundness": 0.2},  # Curved edges
        )

    # Generate HTML
    net.show(output_html, notebook=False)
    print(f"Graph saved to {output_html}")


# Example usage:
if __name__ == "__main__":
    from wiki_utils.utils import read_json

    graph_data = read_json("heart_sutra_walk.json")
    metadatas = read_json("qids_metadata.json")

    metadata_with_title = {}
    for qid, metadata in metadatas.items():
        title = metadata["labels"].get("en", {})
        descriptions = metadata["descriptions"].get("en", {})
        aliases = metadata["aliases"].get("en", {})

        metadata_with_title[qid] = {
            "qid": qid,
            "title": title,
            "descriptions": descriptions,
            "aliases": aliases,
        }

    visualize_graph_interactive(graph_data, metadata_with_title)
