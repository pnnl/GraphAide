"""Context building and deduplication utilities for RAG extraction.

Handles building optimized context strings for LLM extraction, with intelligent
deduplication to avoid redundant information across chunks.
"""

import logging
from typing import Dict, List, Any, Optional, Set
import tiktoken

from graphgen.v2.state import RetrievalResult, RetrievalResultType, RAGContextSummary
from graphgen.v2 import globalconfig

logger = logging.getLogger("graphgen.contextbuilder")


def deduplicate_types(
    summary: Optional[RAGContextSummary],
    retrieval_results: List[RetrievalResult]
) -> tuple[Set[str], Set[str]]:
    """Deduplicate node and edge types from summary and retrieval results.

    Uses set union instead of list extend to avoid duplicates.

    Args:
        summary: RAGContextSummary with base ontology types
        retrieval_results: Per-chunk retrieval results

    Returns:
        Tuple of (deduplicated_node_types, deduplicated_edge_types) as sets
    """
    node_types: Set[str] = set()
    edge_types: Set[str] = set()

    # Start with summary types
    if summary:
        node_types.update(summary.ontology_node_types or [])
        edge_types.update(summary.ontology_edge_types or [])

    # Add types from retrieval results (TYPES result_type)
    for result in retrieval_results:
        if result.result_type == RetrievalResultType.TYPES:
            node_types.update(result.ontology_node_types or [])
            edge_types.update(result.ontology_edge_types or [])

    return node_types, edge_types


def deduplicate_definitions(
    summary: Optional[RAGContextSummary],
    retrieval_results: List[RetrievalResult]
) -> tuple[Dict[str, str], Dict[str, str]]:
    """Deduplicate node and edge definitions from summary and retrieval results.

    Uses dict merge to avoid duplicate keys.

    Args:
        summary: RAGContextSummary with base definitions
        retrieval_results: Per-chunk retrieval results

    Returns:
        Tuple of (node_definitions, edge_definitions) as dicts
    """
    node_definitions: Dict[str, str] = {}
    edge_definitions: Dict[str, str] = {}

    # Start with summary definitions
    if summary:
        node_definitions.update(summary.ontology_node_definitions or {})
        edge_definitions.update(summary.ontology_edge_definitions or {})

    # Merge definitions from retrieval results
    for result in retrieval_results:
        if result.result_type == RetrievalResultType.TYPES and result.custom_data:
            definitions_dict = result.custom_data.get("definitions", {})
            if isinstance(definitions_dict, dict):
                node_definitions.update(definitions_dict)

    return node_definitions, edge_definitions


def deduplicate_entities(
    retrieval_results: List[RetrievalResult]
) -> Dict[str, Any]:
    """Deduplicate Wikidata entities from retrieval results.

    Uses dict merge to avoid duplicate QIDs (last one wins on conflict).

    Args:
        retrieval_results: Per-chunk retrieval results

    Returns:
        Deduplicated wikidata_context dict (QID → entity metadata)
    """
    entities: Dict[str, Any] = {}

    for result in retrieval_results:
        if result.result_type == RetrievalResultType.ENTITIES and result.wikidata_context:
            entities.update(result.wikidata_context)

    return entities


def deduplicate_documents(
    retrieval_results: List[RetrievalResult],
    max_docs: int = 2
) -> List[str]:
    """Deduplicate document snippets from retrieval results.

    Avoids duplicate passages by content hash (simple dedup).

    Args:
        retrieval_results: Per-chunk retrieval results
        max_docs: Maximum number of documents to include

    Returns:
        Deduplicated list of document snippets
    """
    docs_dict: Dict[str, str] = {}  # hash → doc_text

    for result in retrieval_results:
        if result.result_type == RetrievalResultType.DOCUMENTS and result.documents:
            for doc in result.documents[:max_docs]:
                doc_hash = hash(doc)
                if doc_hash not in docs_dict:
                    docs_dict[doc_hash] = doc

    return list(docs_dict.values())[:max_docs]


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for
        encoding_name: Tiktoken encoding name

    Returns:
        Number of tokens
    """
    try:
        tokenizer = tiktoken.get_encoding(encoding_name)
        tokens = tokenizer.encode(text)
        return len(tokens)
    except Exception as e:
        logger.warning(f"Token counting failed: {e}, using character estimate")
        return len(text) // 4  # Rough estimate: 1 token ≈ 4 chars


def build_chunk_context(
    summary: Optional[RAGContextSummary],
    retrieval_results: List[RetrievalResult],
    include_token_count: bool = True
) -> str:
    """Build deduplicated context string for a single chunk.

    Combines ontology types, definitions, entities, and documents into a
    single LLM-friendly context string with intelligent deduplication.

    Args:
        summary: RAGContextSummary with static ontology context
        retrieval_results: Fresh retrieval results for this chunk only
        include_token_count: Whether to log token count

    Returns:
        Context string ready for LLM extraction
    """
    context_parts: List[str] = []

    # 1. Get types and definitions
    node_types, edge_types = deduplicate_types(summary, retrieval_results)
    node_definitions, edge_definitions = deduplicate_definitions(summary, retrieval_results)
    node_examples = summary.ontology_node_examples if summary else {}
    edge_examples = summary.ontology_edge_examples if summary else {}

    # 2. Node and Edge Types with Definitions and Examples (no separate list)
    if node_definitions or edge_definitions:
        context_parts.append("# Node and Edge Types")
        context_parts.append("Below are the node and edge types with their definitions and examples. Extract entities and relationships using ONLY these types.")
        context_parts.append("Note: Type names are listed without brackets. In examples, text in [brackets] represents specific instances of that type.\n")

    if node_definitions:
        context_parts.append("## Node Types")
        for node_type, definition in sorted(node_definitions.items()):
            line = f"- {node_type}: {definition}"
            # Append examples (text snippets with bracketed entity names)
            if node_type in node_examples:
                examples_text = "; ".join(node_examples[node_type][:3])
                line += f" (Examples: {examples_text})"
            context_parts.append(line)
        context_parts.append("")

    if edge_definitions:
        context_parts.append("## Edge Types")
        for edge_type, definition in sorted(edge_definitions.items()):
            line = f"- {edge_type}: {definition}"
            # Append examples (text snippets showing relationships)
            if edge_type in edge_examples:
                examples_text = "; ".join(edge_examples[edge_type][:3])
                line += f" (Examples: {examples_text})"
            context_parts.append(line)
        context_parts.append("")

    # 5. Add store descriptions
    for result in retrieval_results:
        if result.store_description:
            context_parts.append(f"[Vector Store: {result.source}]")
            context_parts.append(result.store_description)
            context_parts.append("")

    # 6. Entities (deduplicated)
    entities = deduplicate_entities(retrieval_results)

    if entities:
        context_parts.append("# Entity Context (Wikidata)")
        for qid, entity_data in sorted(entities.items()):
            label = entity_data.get("label", "")
            description = entity_data.get("description", "")
            desc_suffix = f" - {description[:100]}" if description else ""
            context_parts.append(f"{qid}: {label}{desc_suffix}")
        context_parts.append("")

    # 7. Documents (deduplicated)
    docs = deduplicate_documents(retrieval_results, max_docs=2)

    if docs:
        context_parts.append("# Reference Documents")
        for i, doc in enumerate(docs, 1):
            context_parts.append(f"[Doc {i}] {doc[:300]}...")
        context_parts.append("")

    # Combine all parts
    context = "\n".join(context_parts)

    # Log token count if requested
    if include_token_count:
        token_count = count_tokens(context)
        logger.debug(f"Built context: {len(context)} chars, ~{token_count} tokens")

    return context


def validate_context_window(context: str, max_tokens: int) -> bool:
    """Validate that context fits within token window.

    Args:
        context: Context string
        max_tokens: Maximum allowed tokens

    Returns:
        True if context fits, False otherwise
    """
    token_count = count_tokens(context)
    fits = token_count <= max_tokens

    if not fits:
        logger.warning(
            f"Context exceeds window: {token_count} tokens > {max_tokens} max"
        )

    return fits
