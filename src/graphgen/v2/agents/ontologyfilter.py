"""OntologyFilter: keeps only ontology-typed nodes and edges, then drops edges left without endpoints."""

import json
import logging
from datetime import datetime

from graphgen.v2.state import KGGenerationState

logger = logging.getLogger("graphgen.agents.ontologyfilter")


def _dump(obj):
    data = obj.model_dump() if hasattr(obj, "model_dump") else dict(obj)
    return data


def _save_pre_filter(state, pre_nodes, pre_edges, kept_nodes, kept_edges, skipped_nodes, skipped_edges):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
        batch_info = ""
        if state.get("batch_index") is not None:
            batch_info = f"_Batch{state.get('batch_index')}"
        filename = f"GraphAide_KG_Extract_PreFilter_{timestamp}{batch_info}.json"

        nodes_data = []
        for n in pre_nodes:
            node_dict = _dump(n)
            if "grounding_id" in node_dict:
                node_dict["node_id"] = node_dict.pop("grounding_id")
            nodes_data.append(node_dict)

        edges_data = []
        for e in pre_edges:
            edge_dict = _dump(e)
            if "source_node_english_name" in edge_dict:
                edge_dict["source_id"] = edge_dict.pop("source_node_english_name")
            if "target_node_english_name" in edge_dict:
                edge_dict["target_id"] = edge_dict.pop("target_node_english_name")
            edges_data.append(edge_dict)

        payload = {
            "source_file": state.get("file_path", ""),
            "extraction_stage": "pre_filter",
            "nodes_before_filter": len(pre_nodes),
            "edges_before_filter": len(pre_edges),
            "nodes_after_filter": len(kept_nodes),
            "edges_after_filter": len(kept_edges),
            "filtered_out_nodes": skipped_nodes,
            "filtered_out_edges": skipped_edges,
            "nodes": nodes_data,
            "edges": edges_data,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.debug(f"Pre-filtered graph saved to: {filename}")
    except Exception as e:
        logger.error(f"Failed to save pre-filtered graph: {e}")


def ontology_filter(state: KGGenerationState) -> dict:
    """Keep only nodes/edges whose types are in the ontology, then drop edges with a missing endpoint.

    No-op unless filter_by_ontology is True and the ontology defines node or edge types.
    """
    if not state.get("filter_by_ontology", False):
        return {}

    summary = state.get("rag_context_summary")
    node_types = list(getattr(summary, "ontology_node_types", None) or [])
    edge_types = list(getattr(summary, "ontology_edge_types", None) or [])
    if not node_types and not edge_types:
        return {}

    pre_nodes = list(state.get("nodes", []))
    pre_edges = list(state.get("edges", []))

    kept_nodes = [n for n in pre_nodes if not node_types or n.node_type in node_types]
    kept_node_ids = {n.node_id for n in kept_nodes}
    kept_edges = [
        e
        for e in pre_edges
        if (not edge_types or e.edge_type in edge_types)
        and e.source_id in kept_node_ids
        and e.target_id in kept_node_ids
    ]

    skipped_nodes = len(pre_nodes) - len(kept_nodes)
    skipped_edges = len(pre_edges) - len(kept_edges)
    filter_stats = {}
    if skipped_nodes or skipped_edges:
        filter_stats = {
            "filtered_nodes": skipped_nodes,
            "filtered_edges": skipped_edges,
            "nodes_before": len(pre_nodes),
            "edges_before": len(pre_edges),
            "nodes_after": len(kept_nodes),
            "edges_after": len(kept_edges),
        }
        _save_pre_filter(state, pre_nodes, pre_edges, kept_nodes, kept_edges, skipped_nodes, skipped_edges)

    logger.info(
        f"SmartExtractor[ontologyfilter] chunk={state.get('current_chunk_id')}: "
        f"nodes {len(pre_nodes)} -> {len(kept_nodes)}, edges {len(pre_edges)} -> {len(kept_edges)}"
    )
    return {"nodes": kept_nodes, "edges": kept_edges, "filter_stats": filter_stats}
