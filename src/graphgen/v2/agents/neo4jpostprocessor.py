import logging
from typing import List

import openai
from pydantic import BaseModel

from ..state import Edge, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.neo4jpostprocessor")


class Neo4jPostProcessorSchema(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


class Neo4jPostProcessorToolSchema(BaseModel):
    """Input schema for Neo4jPostProcessorAgent tool."""

    nodes: List[Node]
    edges: List[Edge]


class Neo4jPostProcessorAgent(GraphAideAgent):
    """Post-process the Neo4j graph to fix node labels and edge types.

    Runs cleanup Cypher queries to set proper node labels from the 'type'
    property and convert generic 'REL' relationships to their proper types
    using the 'edge_type' property. Uses APOC procedures.

    Input state keys:
        nodes (List[Node]): Nodes that were loaded (for validation).
        edges (List[Edge]): Edges that were loaded (for validation).

    Output state keys:
        messages (List[str]): Status messages about post-processing.
        is_valid (bool): Whether the operation completed successfully.

    Requires settings:
        vector_store: Vector store instance (required but not used directly).
        graph_store: Neo4j graph database connection with APOC enabled.
    """

    tool_schema = Neo4jPostProcessorToolSchema
    tool_description = "Post-process Neo4j graph to fix node labels and edge types using APOC procedures. You must pass the nodes and edges that were loaded."
    tool_output_keys = ["messages", "agent_status"]

    def __call__(self, state: dict) -> dict:

        # 1. Access the Vector Store from the factory-injected settings
        vector_store = self.settings.get("vector_store")
        graph_store = self.settings.get("graph_store")

        if not vector_store:
            raise ValueError(
                f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
            )

        # 2. Check if edges provided (nodes may be empty for edge-batch processing)
        edges = state.get("edges", [])
        if not edges:
            return {
                "messages": [
                    "No edges provided in state for post-processing. Skipping graph database update."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }
        try:
            lablesetquery = """MATCH (n)
            WHERE n.node_type IS NOT NULL
            CALL apoc.create.setLabels(n, apoc.coll.toSet(n.node_type)) YIELD node
            RETURN node
            """
            graph_store.query(lablesetquery)

            # make sure edge_type exist and 'type' does not exist
            """MATCH ()-[r]->()
            SET r.edge_type = CASE
                WHEN r.type IS NOT NULL THEN r.type
                ELSE coalesce(r.edge_type, "DREL")
            END
            REMOVE r.type
            RETURN r
            """

            # Convert REL edges to proper types - only process edges WITH edge_type
            edgelablesetquery = """
            MATCH (a)-[r:REL]->(b)
            WHERE r.edge_type IS NOT NULL AND toString(r.edge_type) <> ""
            WITH a, b, r, properties(r) AS props, toString(r.edge_type) AS newType

            // Create new relationship with proper type
            CALL apoc.create.relationship(a, newType, props, b) YIELD rel
            WITH rel, r

            // Delete original REL relationship
            DELETE r

            RETURN rel
            """
            logger.info("Neo4jPostProcessor: converting REL edges with edge_type to typed relationships")
            result = graph_store.query(edgelablesetquery)
            skipped_count_query = "MATCH (a)-[r:REL]->(b) WHERE r.edge_type IS NULL OR toString(r.edge_type) = '' RETURN count(r) as cnt"
            skipped = graph_store.query(skipped_count_query)
            logger.info(f"Neo4jPostProcessor: converted {len(result) if result else 0} edges, skipped {skipped[0]['cnt'] if skipped else 0} edges without edge_type")

            # Link nodes to chunks (for chunk-aware workflows)
            # This runs AFTER nodes are created, so MATCH will succeed
            # IMPORTANT: Exclude ChunkParagraph nodes to prevent self-loops
            link_nodes_to_chunks_query = """
            MATCH (n)
            WHERE n.chunk_id IS NOT NULL AND NOT n:ChunkParagraph
            MATCH (p:ChunkParagraph {chunk_id: n.chunk_id})
            MERGE (n)-[r:EXTRACTED_FROM_CHUNK]->(p)
            ON CREATE SET r.raw_source_line = n.raw_source_line
            RETURN COUNT(r) as linked_count
            """
            try:
                link_result = graph_store.query(link_nodes_to_chunks_query)
                linked_count = link_result[0]['linked_count'] if link_result else 0
                if linked_count > 0:
                    logger.info(f"Neo4jPostProcessor: created {linked_count} EXTRACTED_FROM_CHUNK edges")
            except Exception as e:
                logger.debug(f"Neo4jPostProcessor: no chunk linking needed (non-chunk-aware workflow): {e}")

            try:
                distinct_english_names_query = """MATCH (n)
                WHERE n.english_name IS NOT NULL
                SET n.english_name = apoc.coll.toSet(n.english_name)
                RETURN n"""
                graph_store.query(distinct_english_names_query)
                logger.debug("Neo4jPostProcessor: updated distinct english names")

                distinct_names_query = """MATCH (n)
                WHERE n.name IS NOT NULL
                SET n.name = apoc.coll.toSet(n.name)
                RETURN n"""
                graph_store.query(distinct_names_query)
                logger.debug("Neo4jPostProcessor: updated distinct names")

                distinct_names_query = """MATCH (n)
                WHERE n.node_name IS NOT NULL
                SET n.node_name = apoc.coll.toSet(n.node_name)
                RETURN n"""
                graph_store.query(distinct_names_query)
                logger.debug("Neo4jPostProcessor: updated distinct node names")

                distinct_raw_source_query = """MATCH (n)
                WHERE n.raw_source IS NOT NULL
                SET n.raw_source = apoc.coll.toSet(n.raw_source)
                RETURN n"""
                graph_store.query(distinct_raw_source_query)
                logger.debug("Neo4jPostProcessor: updated distinct raw_source")

                distinct_type_query = """MATCH (n)
                WHERE n.node_type IS NOT NULL
                SET n.node_type = apoc.coll.toSet(n.node_type)
                RETURN n"""
                graph_store.query(distinct_type_query)
                logger.debug("Neo4jPostProcessor: updated distinct types")

                distinct_start_datetime_query = """MATCH (n)
                WHERE n.start_datetime IS NOT NULL
                SET n.start_datetime = apoc.coll.toSet(n.start_datetime)
                RETURN n"""
                graph_store.query(distinct_start_datetime_query)
                logger.debug("Neo4jPostProcessor: updated distinct start_datetime")

                distinct_end_datetime_query = """MATCH (n)
                WHERE n.end_datetime IS NOT NULL
                SET n.end_datetime = apoc.coll.toSet(n.end_datetime)
                RETURN n"""
                graph_store.query(distinct_end_datetime_query)
                logger.debug("Neo4jPostProcessor: updated distinct end_datetime")

            except Exception as e:
                logger.error(f"Neo4jPostProcessor failed to update distinct names or raw_source: {e}")

            # 4. Return updated state
            return {
                "messages": [
                    "Successfully updated node labels, edge types with REL default value the graph database."
                ],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: True},
            }
        except openai.PermissionDeniedError as e:
            logger.error(f"Neo4jPostProcessor permission denied [{e.status_code}]: {e.body}")
        except Exception as e:
            logger.error(f"Neo4jPostProcessor failed: {e}")
            return {
                "messages": [f"Error during extraction: {str(e)}"],
                "current_agent": [self.__class__.__name__],
                "agent_status": {self.__class__.__name__: False},
            }
