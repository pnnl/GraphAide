"""ChunkTrackerAgent - Wraps ExtractorAgent to add chunk tracking and deduplication."""

import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..state import ChunkMetadata, Edge, Node, SourceDocumentMetadata
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.chunktrackeragent")


class ChunkTrackerAgent(GraphAideAgent):
    """Wraps ExtractorAgent to add chunk tracking and deduplication support.

    Responsibilities:
    1. Compute global chunk_id from raw_text (SHA256[:12]) for deduplication across files
    2. Track chunk metadata (sequence, file_path, token count, content preview)
    3. Call wrapped ExtractorAgent to extract KG nodes/edges
    4. Enhance extracted nodes/edges with chunk_id and raw_source_line
    5. Create SourceDocumentMetadata and ChunkMetadata for Neo4j graph loading
    6. Enable queries like: "Show all entities from document.pdf chunk#3"

    Data Model:
    - chunk_id (global): SHA256[:12] hash of chunk content (reproducible, deduplicates identical chunks)
    - sequence_num (per-file): 0-indexed chunk number within file (human-readable: chunk#0, chunk#1, etc.)
    - raw_source_line: 1-2 line context where entity was found (granular provenance)

    Chunk Deduplication:
    - Two files with identical chunk content share ONE ChunkParagraph node (by chunk_id)
    - Both SourceDocuments reference same ChunkParagraph via CONTAINS relationship
    - Extracted nodes from both files link to same ChunkParagraph

    Input state keys:
        raw_text (str): Current chunk content
        file_path (str): Source file being processed
        chunk_sequence (int): 0-indexed chunk number within file
        total_chunks (int): Total chunks from this file (for metadata)
        rag_context: For ontology/Wikidata grounding

    Output state keys:
        nodes (List[Node]): Enhanced with chunk_id and raw_source_line
        edges (List[Edge]): Enhanced with chunk_id and raw_source_line
        chunk_documents (List[SourceDocumentMetadata]): File-level metadata
        chunk_paragraphs (List[ChunkMetadata]): Chunk-level metadata
        current_chunk_id (str): Global chunk identifier (for current processing)
        messages (List[str]): Status messages from extractor + chunk tracking info
    """

    def __init__(self, wrapped_extractor: GraphAideAgent, **kwargs):
        """Initialize ChunkTrackerAgent with wrapped ExtractorAgent.

        Args:
            wrapped_extractor: ExtractorAgent instance to wrap
            **kwargs: Additional args passed to parent GraphAideAgent
        """
        # ChunkTrackerAgent is a wrapper that doesn't extract directly.
        # Use wrapped extractor's model and inherit its settings.
        # The wrapped_extractor will handle all LLM operations.
        model = wrapped_extractor.model
        settings = kwargs.pop("settings", None) or wrapped_extractor.settings
        super().__init__(model=model, template_str="", settings=settings)
        self.wrapped_extractor = wrapped_extractor

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process chunk with tracking, call extractor, enhance output with chunk metadata.

        Args:
            state: KGGenerationState dict

        Returns:
            Enhanced state with chunk_id, raw_source_line on nodes/edges, and metadata
        """
        try:
            # DEBUG: Log incoming state
            logger.debug(f"\n{'='*80}\nCHUNKTRACKER RECEIVED STATE:\n{'='*80}")
            logger.debug(f"State keys: {list(state.keys())}")
            logger.debug(f"file_path: {state.get('file_path')}")
            logger.debug(f"chunk_sequence: {state.get('chunk_sequence')}")
            logger.debug(f"total_chunks: {state.get('total_chunks')}")
            logger.debug(f"raw_text length: {len(state.get('raw_text', ''))} chars")
            logger.debug(f"raw_text (first 300 chars): {state.get('raw_text', '')[:300]}")
            logger.debug(f"{'='*80}\n")

            # 1. Extract chunk information from state
            raw_text = state.get("raw_text", "")
            file_path = state.get("file_path", "")
            chunk_sequence = state.get("chunk_sequence", 0)
            total_chunks = state.get("total_chunks", 0)

            if not raw_text:
                logger.warning("ChunkTracker: raw_text is empty, skipping chunk")
                return {
                    "messages": ["ChunkTracker: No raw_text to process"],
                    "current_agent": [self.__class__.__name__],
                }

            # 2. Compute global chunk_id (SHA256[:12] for reproducibility + deduplication)
            chunk_hash = hashlib.sha256(raw_text.encode()).hexdigest()
            chunk_id = chunk_hash[:12]  # Global identifier (reproducible across files)

            logger.debug(f"ChunkTracker: Processing chunk {chunk_sequence} (chunk_id={chunk_id}) from {file_path}")

            # 3. Approximate token count (rough estimate: words * 1.3)
            word_count = len(raw_text.split())
            token_count = int(word_count * 1.3)

            # 4. Create SourceDocumentMetadata (file-level)
            file_name = os.path.basename(file_path) if file_path else "unknown"
            doc_metadata = SourceDocumentMetadata(
                file_name=file_name,
                file_path=file_path,
                total_chunks=total_chunks,
                created_at=datetime.now().isoformat(),
            )

            # 5. Create ChunkMetadata (chunk-level)
            chunk_metadata = ChunkMetadata(
                chunk_id=chunk_id,
                chunk_hash=chunk_hash,
                file_path=file_path,
                sequence_num=chunk_sequence,
                content_preview=raw_text[:500],
                token_count=token_count,
                created_at=datetime.now().isoformat(),
            )

            # 6. Enhance state with chunk context for extractor
            enhanced_state = {**state, "current_chunk_id": chunk_id}

            # 7. Call wrapped ExtractorAgent
            extractor_output = self.wrapped_extractor(enhanced_state)

            # 8. Enhance extracted nodes with chunk_id and raw_source_line
            enhanced_nodes = []
            for node in extractor_output.get("nodes", []):
                node.chunk_id = chunk_id
                # Find 1-2 line context where this node was mentioned
                node.raw_source_line = self._find_mention_in_chunk(node.node_name, raw_text)
                enhanced_nodes.append(node)

            # 9. Enhance extracted edges with chunk_id and raw_source_line
            enhanced_edges = []
            for edge in extractor_output.get("edges", []):
                edge.chunk_id = chunk_id
                # Find context where this relationship was mentioned
                mention_str = f"{edge.source_id} {edge.edge_type} {edge.target_id}"
                edge.raw_source_line = self._find_mention_in_chunk(mention_str, raw_text)
                enhanced_edges.append(edge)

            logger.info(
                f"ChunkTracker: Enhanced {len(enhanced_nodes)} nodes, {len(enhanced_edges)} edges "
                f"with chunk_id={chunk_id} from {file_name}#{chunk_sequence}"
            )

            # 10. Return enhanced output + metadata
            return {
                "nodes": enhanced_nodes,
                "edges": enhanced_edges,
                "chunk_documents": [doc_metadata],  # Will accumulate via operator.add
                "chunk_paragraphs": [chunk_metadata],  # Will accumulate via operator.add
                "current_chunk_id": chunk_id,
                "messages": extractor_output.get("messages", [])
                + [f"✓ Chunk tracked: {file_name}#{chunk_sequence} (chunk_id={chunk_id})"],
                "current_agent": [self.__class__.__name__],
            }

        except Exception as e:
            logger.error(f"ChunkTracker error: {str(e)}", exc_info=True)
            return {
                "messages": [f"ChunkTracker error: {str(e)}"],
                "current_agent": [self.__class__.__name__],
                "chunk_documents": [],
                "chunk_paragraphs": [],
            }

    def _find_mention_in_chunk(self, mention: str, chunk_text: str) -> str:
        """Find 1-2 line context where mention appears in chunk.

        Args:
            mention: Text/entity to search for
            chunk_text: Chunk content to search in

        Returns:
            1-2 line context where mention was found, or fallback to mention string
        """
        if not mention or not chunk_text:
            return mention

        lines = chunk_text.split("\n")

        # Search for mention (case-insensitive)
        for i, line in enumerate(lines):
            if mention.lower() in line.lower():
                # Return 1-2 line context (previous line + current line)
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context = "\n".join(lines[start:end]).strip()
                return context

        # Fallback: return mention if not found in chunk
        logger.debug(f"ChunkTracker: Mention '{mention}' not found in chunk, using fallback")
        return mention
