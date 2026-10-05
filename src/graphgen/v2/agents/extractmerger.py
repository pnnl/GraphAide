"""ExtractMerger Agent: Consolidates nodes and edges by canonical identifiers."""

import logging
from typing import Any, Dict
from collections import defaultdict
from langgraph.types import Command

from graphgen.v2.state import KGGenerationState, Node, Edge, MergedNode, MergedEdge, Span
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.extractmerger")


class ExtractMergerAgent(GraphAideAgent):
    """Consolidates extracted nodes and edges by deduplication keys.

    Merges multiple mentions of the same entity (nodes) or relationship (edges):
    - Nodes: Grouped by node_id (canonical key)
    - Edges: Grouped by (source_id, target_id, edge_type)

    Produces merged_nodes and merged_edges lists with consolidated metadata.
    """

    def __call__(self, state: KGGenerationState, config: Dict[str, Any] = None) -> Command:
        """Merge nodes and edges, consolidating metadata.

        Args:
            state: Current KGGenerationState with extracted nodes and edges
            config: LangGraph config (optional)

        Returns:
            Command to update state with merged_nodes and merged_edges
        """
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])

        logger.info(f"ExtractMerger: Consolidating {len(nodes)} nodes and {len(edges)} edges")

        # Merge nodes by node_id
        merged_nodes = self._merge_nodes(nodes)
        logger.info(f"ExtractMerger: Consolidated to {len(merged_nodes)} unique nodes")

        # Merge edges by (source, target, edge_type)
        merged_edges = self._merge_edges(edges)
        logger.info(f"ExtractMerger: Consolidated to {len(merged_edges)} unique edges")

        return Command(
            update={
                "merged_nodes": merged_nodes,
                "merged_edges": merged_edges,
            }
        )

    def _merge_nodes(self, nodes: list[Node]) -> list[MergedNode]:
        """Group nodes by node_id and consolidate metadata.

        Args:
            nodes: List of extracted nodes

        Returns:
            List of deduplicated MergedNode objects
        """
        # Group by node_id
        grouped = defaultdict(list)
        for node in nodes:
            try:
                node_id = node.node_id or node.english_name
                grouped[node_id].append(node)
            except Exception as e:
                logger.error(f"ExtractMerger: Error grouping node {node}: {type(e).__name__}: {e}")
                continue

        merged_nodes = []
        for node_id, node_group in grouped.items():
            try:
                # Extract consolidated fields
                node_names = list(set(n.node_name for n in node_group))
                node_types = list(set(n.node_type for n in node_group))
                character_spans = [
                    n.character_span for n in node_group if n.character_span is not None
                ]
                token_spans = [
                    n.token_span for n in node_group if n.token_span is not None
                ]
                raw_sources = list(set(n.raw_source for n in node_group if n.raw_source))

                # Use first node's attributes as primary (or most common)
                primary_node = node_group[0]
                english_name = primary_node.english_name
                wikidata_id = primary_node.wikidata_id

                merged_node = MergedNode(
                    node_id=node_id,
                    english_name=english_name,
                    wikidata_id=wikidata_id,
                    node_names=node_names,
                    node_types=node_types,
                    character_spans=character_spans,
                    token_spans=token_spans,
                    raw_sources=raw_sources,
                    mention_count=len(node_group),
                )
                merged_nodes.append(merged_node)
            except Exception as e:
                logger.error(f"ExtractMerger: Error merging node group {node_id}: {type(e).__name__}: {e}")
                logger.error(f"Node group size: {len(node_group)}")
                if node_group:
                    logger.debug(f"First node: {node_group[0]}")
                continue

        return merged_nodes

    def _merge_edges(self, edges: list[Edge]) -> list[MergedEdge]:
        """Group edges by (source, target, edge_type) and consolidate metadata.

        Args:
            edges: List of extracted edges

        Returns:
            List of deduplicated MergedEdge objects
        """
        # Group by (source, target, edge_type)
        grouped = defaultdict(list)
        for edge in edges:
            try:
                key = (
                    edge.source_id,
                    edge.target_id,
                    edge.edge_type,
                )
                grouped[key].append(edge)
            except Exception as e:
                logger.error(f"ExtractMerger: Error grouping edge {edge}: {type(e).__name__}: {e}")
                continue

        merged_edges = []
        for (source, target, edge_type), edge_group in grouped.items():
            try:
                # Ensure all required fields are strings (convert None → empty string)
                source_id = str(source) if source else ""
                target_id = str(target) if target else ""
                edge_type_str = str(edge_type) if edge_type else ""

                # Skip invalid edges (missing required fields)
                if not source_id or not target_id or not edge_type_str:
                    logger.warning(f"ExtractMerger: Skipping invalid edge ({source_id}, {target_id}, {edge_type_str})")
                    continue

                # Extract consolidated fields
                argument_roles = [e.argument_role for e in edge_group]
                start_datetimes = [e.start_datetime for e in edge_group]
                end_datetimes = [e.end_datetime for e in edge_group]

                character_spans = [
                    e.character_span for e in edge_group if e.character_span is not None
                ]
                token_spans = [
                    e.token_span for e in edge_group if e.token_span is not None
                ]
                raw_sources = list(set(e.raw_source for e in edge_group if e.raw_source))

                merged_edge = MergedEdge(
                    source_id=source_id,
                    target_id=target_id,
                    edge_type=edge_type_str,
                    argument_roles=argument_roles,
                    start_datetimes=start_datetimes,
                    end_datetimes=end_datetimes,
                    character_spans=character_spans,
                    token_spans=token_spans,
                    raw_sources=raw_sources,
                    mention_count=len(edge_group),
                )
                merged_edges.append(merged_edge)
            except Exception as e:
                logger.error(f"ExtractMerger: Error merging edge group ({source}, {target}, {edge_type}): {type(e).__name__}: {e}")
                logger.error(f"Edge group size: {len(edge_group)}")
                if edge_group:
                    logger.debug(f"First edge: {edge_group[0]}")
                continue

        return merged_edges
