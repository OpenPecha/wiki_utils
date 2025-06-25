"""
Utility functions for the wiki_utils package.
"""


import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx


def write_json(data: dict | list, output_path: str | Path):
    with open(output_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(file_path: str | Path):
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    return data


def visualize_graph(data: list[dict[str, str]]):

    # Create a directed graph
    G = nx.DiGraph()

    # Add edges and relationships as edge labels
    for entry in data:
        from_node = entry["from"]
        to_node = entry["to"]
        relationship = entry["relationship"]
        G.add_edge(from_node, to_node, label=relationship)

    # Draw the graph
    pos = nx.spring_layout(G, k=0.5, iterations=50)
    plt.figure(figsize=(12, 8))
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


if __name__ == "__main__":
    data = read_json("heart_sutra_walk.json")
    visualize_graph(data)
