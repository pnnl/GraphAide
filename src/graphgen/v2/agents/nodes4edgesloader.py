import json
import logging
import traceback
from typing import List

from pydantic import BaseModel

from ..state import Edge, KGGenerationState, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.nodes4edgesloader")


class Nodes4EdgesLoaderSchema(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


class Nodes4EdgesLoaderToolSchema(BaseModel):
    """Input schema for Nodes4EdgesLoaderAgent tool."""

    nodes: List[Node]
    edges: List[Edge]


class Nodes4EdgesLoaderAgent(GraphAideAgent):
    """Create nodes referenced in edges that don't exist yet.

    Preprocessor that ensures all nodes mentioned in edges exist in Neo4j.
    For any edge, if source or target node is missing, creates it with minimal properties.
    This prevents edge loading failures due to missing nodes and preserves edge relationships.

    Used before parallel NodesLoader/EdgesLoader to handle incomplete node lists - common
    when loading pre-extracted JSON where edge definitions may reference nodes not in nodes list.

    Input state keys:
        nodes (List[Node]): Extracted node objects (for context/counting).
        edges (List[Edge]): Edge objects defining which nodes must exist.

    Output state keys:
        messages (List[str]): Status messages about the loading operation.
        agent_status (dict): Operation status.

    Requires settings:
        vector_store: Vector store instance for context.
        graph_store: Neo4j graph database connection.
    """

    tool_schema = Nodes4EdgesLoaderToolSchema
    tool_description = "FIRST STEP: Create nodes referenced in edges that don't exist yet. Must be called BEFORE NodesLoader and EdgesLoader. Pass the nodes and edges extracted by ExtractorAgent."
    tool_output_keys = ["messages", "agent_status"]

    def __call__(self, state: KGGenerationState) -> dict:

        # 1. Access dependencies
        vector_store = self.settings.get("vector_store")
        graph_store = self.settings.get("graph_store")

        if not vector_store:
            raise ValueError(
                f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
            )

        if not graph_store:
            logger.warning("Nodes4EdgesLoader: no graph_store provided. Skipping node creation.")
            return {
                "messages": [
                    "No graph store provided. Skipping node creation."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        # 2. Get nodes and edges from state
        # Works for both kg_ingest (from extraction) and kg_load_json (from pre-extracted JSON)
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])
        if not edges:
            logger.info("Nodes4EdgesLoader: No edges to process. Skipping.")
            return {
                "messages": [
                    "No edges provided for loading nodes. Skipping."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        # 3. Prepare input (NO escaping - Neo4j driver handles it via UNWIND row.* binding)
        # Send raw values so LLM doesn't see escape chars and get confused
        nodes_data = [n.model_dump() if hasattr(n, "model_dump") else dict(n) for n in nodes]
        edges_data = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in edges]
        inputtext = json.dumps({"nodes": nodes_data, "edges": edges_data})

        logger.info(f"Nodes4EdgesLoader: loading {len(nodes)} nodes, {len(edges)} edges (batch {state.get('batch_index', 'all')}/{state.get('total_batches', 'all')})")

        # 4. Invoke chain and handle result
        result, error = self._invoke_cypher_chain(graph_store, nodes, edges, inputtext)

        if error:
            logger.error(f"Nodes4EdgesLoader failed: {error}")
            return {
                "messages": [f"Error during loading: {str(error)} ==> {traceback.format_exc()}"],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        return {
            "messages": [
                "Successfully loaded nodes defined in edges section into the graph database."
            ],
            "current_agent": [self.__class__.__name__],
            "agent_status": {self.__class__.__name__: True},
        }
