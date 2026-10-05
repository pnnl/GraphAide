import json
import logging
from typing import List

from pydantic import BaseModel

from ..state import Edge, KGGenerationState, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.nodesloader")


class NodesLoaderSchema(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


class NodesLoaderToolSchema(BaseModel):
    """Input schema for NodesLoaderAgent tool."""

    nodes: List[Node]


class NodesLoaderAgent(GraphAideAgent):
    """Load extracted nodes into a Neo4j graph database.

    Takes nodes from the state and generates Cypher queries to create
    them in the graph database. Uses GraphCypherQAChain for query generation.

    Input state keys:
        nodes (List[Node]): Node objects to load into the database.
        edges (List[Edge]): Edge objects (required but not directly loaded by this agent).

    Output state keys:
        messages (List[str]): Status messages about the loading operation.
        is_valid (bool): Whether the operation completed successfully.

    Requires settings:
        vector_store: Vector store instance for context.
        graph_store: Neo4j graph database connection.
    """

    tool_schema = NodesLoaderToolSchema
    tool_description = "SECOND STEP: Load extracted nodes into Neo4j. Call AFTER Nodes4EdgesLoaderAgent, then in parallel with EdgesLoaderAgent. You must pass the nodes extracted by ExtractorAgent."
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
            logger.warning("No graph_store provided, skipping node loading")
            return {
                "messages": [
                    "No graph store provided. Skipping node loading."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        # 2. Get nodes and edges from state
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])

        if not nodes:
            logger.info("No nodes to load, skipping")
            return {
                "messages": [
                    "No nodes provided for loading. Skipping."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        # 3. Prepare input (NO escaping - Neo4j driver handles it via UNWIND row.* binding)
        # Send raw values so LLM doesn't see escape chars and get confused
        nodes_data = [n.model_dump() if hasattr(n, "model_dump") else dict(n) for n in nodes]
        inputtext = json.dumps({"nodes": nodes_data, "edges": str(edges)})

        logger.info(f"Loading {len(nodes)} nodes (batch {state.get('batch_index', 'all')}/{state.get('total_batches', 'all')})")

        # 4. Invoke chain and handle result
        result, error = self._invoke_cypher_chain(graph_store, nodes, edges, inputtext)

        if error:
            return {
                "messages": [f"Error during loading: {str(error)}"],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }

        return {
            "messages": ["Successfully loaded nodes into the graph database."],
            "current_agent": [self.__class__.__name__],
            "agent_status": {self.__class__.__name__: True},
        }
