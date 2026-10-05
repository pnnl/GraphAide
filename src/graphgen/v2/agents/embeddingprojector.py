import json
import logging
import os
from typing import Optional

import numpy as np
import umap
from pydantic import BaseModel, Field

from .. import globalconfig as gc
from ..state import KGGenerationState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.embeddingprojector")


class EmbeddingProjectorToolSchema(BaseModel):
    """Input schema for EmbeddingProjectorAgent tool."""

    embedding_file_path: Optional[str] = Field(
        default="umap_embeddings.npy", description="Path to save/load projections"
    )
    reuse_embedding_file_path: Optional[bool] = Field(
        default=False, description="Whether to reuse existing projection if available"
    )


class EmbeddingProjectorAgent(GraphAideAgent):
    """Project high-dimensional embeddings to 2D using UMAP for visualization.

    Retrieves embeddings from the vector store and applies UMAP dimensionality
    reduction to create 2D projections. Saves projections and metadata to files
    for subsequent visualization. Can reuse existing projections if available.

    Input state keys:
        embedding_file_path (str, optional): Path to save/load projections.
            Defaults to 'umap_embeddings.npy'.
        reuse_embedding_file_path (bool, optional): Whether to reuse existing projection.

    Output state keys:
        embedding_file_path (str): Path where projections were saved.
        messages (List[str]): Status messages about the projection operation.

    Requires settings:
        vector_store: ChromaDB vector store to retrieve embeddings from.
    """

    tool_schema = EmbeddingProjectorToolSchema
    tool_description = "Project high-dimensional embeddings to 2D using UMAP for visualization"
    tool_output_keys = ["embedding_file_path", "messages"]

    def __call__(self, state: KGGenerationState) -> dict:
        import time

        # 1. Access the Vector Store from the factory-injected settings
        vector_store = self.settings.get("vector_store")
        umap_persist_file_path = state.get("embedding_file_path", "umap_embeddings.npy")

        """EmbeddingProjectorAgent is responsible for taking high-dimensional embeddings from the vector store, applying UMAP dimensionality reduction, and saving the 2D projections to a file.
        It checks if a projection already exists and can reuse it if specified in the state. The agent also handles metadata for visualization purposes."""

        if (
            os.path.exists(umap_persist_file_path)
            and state.get("reuse_embedding_file_path", False)
            and os.path.exists(umap_persist_file_path + ".metadata.json")
        ):
            logger.info(f"UMAP: reusing {umap_persist_file_path}")
            return {
                "messages": [
                    f"Reused existing UMAP projection from {umap_persist_file_path}."
                ],
                "embedding_file_path": umap_persist_file_path,
            }

        logger.info(f"UMAP: computing projection -> {umap_persist_file_path}")

        t0 = time.time()
        documents = vector_store._collection.get(
            include=["embeddings", "metadatas", "documents"]
        )
        t1 = time.time()
        logger.debug(f"ChromaDB retrieval: {t1-t0:.2f}s")

        embedding_vectors = documents["embeddings"]
        metadata = documents["metadatas"]
        matched_documents_content = documents["documents"]

        logger.debug(f"UMAP: {len(embedding_vectors)} embeddings retrieved")

        for i, content in enumerate(matched_documents_content):
            # Add the first gc.CONTENT_LABEL_LIMIT characters of each content to the corresponding metadata. This is the text shown on selection in the plotly visualization
            pview = metadata[i].get("title", metadata[i].get("source", ""))

            metadata[i]["preview"] = (
                " " + pview + " => " + content[: gc.CONTENT_LABEL_LIMIT]
            )

        # Convert embeddings to numpy array
        t2 = time.time()
        embeddings_np = np.array(embedding_vectors)
        t3 = time.time()
        logger.debug(f"Numpy conversion: {t3-t2:.2f}s")

        # Reduce dimensionality using UMAP
        logger.info(f"UMAP: starting dimensionality reduction for {len(embeddings_np)} points")
        t4 = time.time()
        umap_reducer = umap.UMAP(n_components=2, random_state=42)
        reduced_embeddings = umap_reducer.fit_transform(embeddings_np)
        t5 = time.time()
        logger.debug(f"UMAP fit_transform: {t5-t4:.2f}s")
        logger.info("UMAP: projection complete")

        # Save the reduced embeddings to a file
        t6 = time.time()
        np.save(umap_persist_file_path, reduced_embeddings)
        t7 = time.time()
        logger.debug(f"Numpy save: {t7-t6:.2f}s")

        # Optionally, save the metadata to a separate file
        with open(
            umap_persist_file_path + ".metadata.json", "w", encoding="utf-8"
        ) as f:
            json.dump(metadata, f)
        return {
            "messages": [
                f"UMAP projection completed and saved to {umap_persist_file_path} with metadata."
            ],
            "embedding_file_path": umap_persist_file_path,
        }
