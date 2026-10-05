import json
import logging
from typing import List

from pydantic import BaseModel

from ..state import Edge, KGGenerationState, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.edgesloader")


class EdgesLoaderSchema(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


class EdgesLoaderToolSchema(BaseModel):
    """Input schema for EdgesLoaderAgent tool."""

    nodes: List[Node]
    edges: List[Edge]


class EdgesLoaderAgent(GraphAideAgent):
    """Load extracted edges (relationships) into a Neo4j graph database.

    Takes edges from the state and generates Cypher queries to create
    relationships between existing nodes in the graph database.

    Input state keys:
        nodes (List[Node]): Node objects (required for context).
        edges (List[Edge]): Edge objects defining relationships to create.

    Output state keys:
        messages (List[str]): Status messages about the loading operation.
        is_valid (bool): Whether the operation completed successfully.

    Requires settings:
        vector_store: Vector store instance for context.
        graph_store: Neo4j graph database connection.
    """

    tool_schema = EdgesLoaderToolSchema
    tool_description = "THIRD STEP: Load extracted edges (relationships) into Neo4j. Call AFTER Nodes4EdgesLoaderAgent, in parallel with NodesLoaderAgent. You must pass the nodes and edges extracted by ExtractorAgent."
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
            logger.warning("No graph_store provided, skipping edge loading")
            return {
                "messages": [
                    "No graph store provided. Skipping edge loading."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        # 2. Get nodes and edges from state
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])

        if not edges:
            logger.info("No edges to load, skipping")
            return {
                "messages": [
                    "No edges provided for loading. Skipping."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        # 3. Prepare input (NO escaping - Neo4j driver handles it via UNWIND row.* binding)
        # Send raw values so LLM doesn't see escape chars and get confused
        edges_data = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in edges]
        inputtext = json.dumps({"edges": edges_data})

        logger.info(f"Loading {len(edges)} edges (batch {state.get('batch_index', 'all')}/{state.get('total_batches', 'all')})")

        # 4. Invoke chain and handle result
        result, error = self._invoke_cypher_chain(graph_store, nodes, edges, inputtext)

        if error:
            return {
                "messages": [f"Error during loading: {str(error)}"],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        return {
            "messages": ["Successfully loaded edges into the graph database."],
            "current_agent": [self.__class__.__name__],
            "agent_status": {self.__class__.__name__: True},
        }
