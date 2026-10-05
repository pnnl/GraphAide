import json
import logging
import os
import socket
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import plotly.express as px
from pydantic import BaseModel, Field

from .. import globalconfig as gc
from ..state import KGGenerationState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.embeddingvisualizer")


class EmbeddingVisualizerToolSchema(BaseModel):
    """Input schema for EmbeddingVisualizerAgent tool."""

    embedding_file_path: Optional[str] = Field(
        default="umap_embeddings.npy",
        description="Path to the .npy file with 2D projections. Expects a matching .metadata.json file",
    )
    output_dir: Optional[str] = Field(
        default="./data",
        description="Directory to save visualization output",
    )
    display_in_notebook: Optional[bool] = Field(
        default=True,
        description="Display interactive figure in notebook",
    )
    save_png: Optional[bool] = Field(
        default=False,
        description="Save visualization as PNG file (True) or just launch interactive app (False)",
    )
    category_field: Optional[str] = Field(
        default="metadata_filter",
        description="Metadata field to use for coloring point categories (e.g., 'activities', 'capabilities')",
    )


class EmbeddingVisualizerAgent(GraphAideAgent):
    """Visualize 2D embedding projections using interactive Plotly/Dash.

    Loads UMAP-projected embeddings and creates an interactive scatter plot
    with hover labels and selection capabilities. Launches a local Dash web
    server for interactive exploration of the embedding space.

    Input state keys:
        embedding_file_path (str, optional): Path to the .npy file with 2D projections.
            Defaults to 'umap_embeddings.npy'. Expects a matching .metadata.json file.

    Output state keys:
        embedding_file_path (str): Path to the visualized embeddings file.
        messages (List[str]): Status messages about the visualization.

    Note: This agent launches a blocking Dash web server for visualization.
    """

    tool_schema = EmbeddingVisualizerToolSchema
    tool_description = "Visualize 2D embedding projections using interactive Plotly/Dash"
    tool_output_keys = ["embedding_file_path", "messages"]

    def __call__(self, state: KGGenerationState) -> dict:

        # 1. Access the Vector Store from the factory-injected settings
        umap_persist_file_path = state.get("embedding_file_path", "umap_embeddings.npy")
        display_in_notebook = state.get("display_in_notebook", True)
        save_png = state.get("save_png", False)
        reduced_embeddings = np.load(umap_persist_file_path)
        # print(reduced_embeddings.shape)
        # title = gc.PLOT_TITLE
        title = getattr(gc, "PLOT_TITLE", "Embedding Visualization")
        # Load the metadata from the file
        try:
            with open(
                umap_persist_file_path + ".metadata.json", "r", encoding="utf-8"
            ) as f:
                metadata = json.load(f)
        except Exception:
            # print("Metadata file does not exist")
            metadata = None

        dynamic_label = True
        category_field = "metadata_filter"  # Field in metadata to use for coloring categories. Default was "source", but "metadata_filter" is more flexible for user-defined categories in metadata.
        dot_size = 10
        font_size = 10
        width = 1200
        height = 800
        showlabel = True
        dot_color = "blue"

        # Annotate points with labels (metadata titles or ids)
        if dynamic_label is True:
            # Prepare data for Plotly
            categories = [meta.get(category_field, "Unknown") for meta in metadata]
            unique_categories = list(set(categories))
            colors = plt.cm.tab10(
                range(len(unique_categories))
            )  # Color map with enough colors for each unique category
            color_map = {
                category: colors[i] for i, category in enumerate(unique_categories)
            }

            labels = [
                meta.get(
                    "preview", meta.get("title", meta.get("id", meta.get("source", "")))
                )
                for meta in metadata
            ]
            # print(labels)
            data_for_plot = {
                "x": reduced_embeddings[:, 0],
                "y": reduced_embeddings[:, 1],
                "label": labels,
                "size": dot_size / 5,
                "category": categories,
            }

            # Create Plotly scatter plot
            if len(categories) > 1:
                fig = px.scatter(
                    data_for_plot,
                    x="x",
                    y="y",
                    hover_name="label",
                    title=title,
                    color="category",
                    size_max=20,
                )
            else:
                fig = px.scatter(
                    data_for_plot,
                    x="x",
                    y="y",
                    hover_name="label",
                    title=title,
                    size_max=20,
                    color_discrete_sequence=[dot_color],
                )

            fig.update_layout(
                width=width,
                height=height,
                dragmode="select",
                selectdirection="any",
                plot_bgcolor="white",
                paper_bgcolor="white",
                xaxis=dict(gridcolor="lightgray"),
                yaxis=dict(gridcolor="lightgray"),
                font=dict(size=14, family="Arial"),
                margin=dict(l=20, r=20, t=40, b=20),
            )

            # Create Dash app with selection callback (lazy import to avoid Jupyter issues)
            from dash import Dash, dcc, html, Input, Output

            app = Dash(__name__)

            app.layout = html.Div([
                dcc.Graph(id="scatter-plot", figure=fig),
                html.Hr(),
                html.H4("Selected Data Points"),
                html.Div(id="selected-data"),
            ])

            @app.callback(
                Output("selected-data", "children"),
                Input("scatter-plot", "selectedData"),
            )
            def display_selected_data(selectedData):
                if selectedData is None:
                    return "No points selected"
                points = selectedData["points"]
                headers = ["x", "y", "Content"]
                rows = [headers] + [[p["x"], p["y"], p["hovertext"]] for p in points]
                table = html.Table(
                    [html.Tr([html.Th(col) for col in rows[0]])]
                    + [html.Tr([html.Td(col) for col in row]) for row in rows[1:]]
                )
                return table

            def find_free_port():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(("", 0))
                port = sock.getsockname()[1]
                sock.close()
                return port

            port = find_free_port()
            logger.info(f"Launching Dash app on http://localhost:{port}")
            app.run(debug=False, port=port)

            # Save PNG if requested
            result_msg = f"Visualization launched on http://localhost:{port}"
            png_path = None
            if save_png:
                output_dir = state.get("output_dir", "./data")
                os.makedirs(output_dir, exist_ok=True)
                png_path = os.path.join(output_dir, "embedding_visualization.png")
                fig.write_image(png_path, scale=2)
                result_msg += f" and saved to {png_path}"

            return {
                "messages": [result_msg],
                "embedding_file_path": umap_persist_file_path,
                "visualization_path": png_path,
            }
        else:
            # Plot the reduced embeddings
            plt.figure(figsize=(10, 8))
            plt.scatter(
                reduced_embeddings[:, 0], reduced_embeddings[:, 1], s=dot_size
            )
            plt.title("Embeddings Visualization")
            plt.xlabel("Dimension 1")
            plt.ylabel("Dimension 2")

            output_dir = state.get("output_dir", "./data")
            os.makedirs(output_dir, exist_ok=True)
            png_path = os.path.join(output_dir, "embedding_visualization.png")
            plt.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close()

            return {
                "messages": [f"Visualization saved to {png_path}"],
                "embedding_file_path": umap_persist_file_path,
                "visualization_path": png_path,
            }
