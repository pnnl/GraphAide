"""ChunkGraphLoadAgent - Loads SourceDocument and ChunkParagraph nodes to Neo4j."""

import logging
from typing import Any, Dict, List

from ..state import ChunkMetadata, Node, SourceDocumentMetadata
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.chunkgraphload")


class ChunkGraphLoadAgent(GraphAideAgent):
    """Loads SourceDocument and ChunkParagraph nodes to Neo4j with relationships.

    Creates:
    - SourceDocument nodes (one per unique file) with properties: file_name, file_path, total_chunks, created_at
    - ChunkParagraph nodes (one per unique chunk_id, deduplicated by content hash) with properties: chunk_id, chunk_hash, sequence_num, content_preview, token_count, created_at
    - Relationships: SourceDocument -[CONTAINS]-> ChunkParagraph (file contains chunks)
    - Relationships: Node -[EXTRACTED_FROM_CHUNK]-> ChunkParagraph (entity came from chunk)

    Follows Neo4jPostProcessorAgent pattern:
    - Hardcoded Cypher queries (deterministic, no LLM)
    - Direct graph_store.query() execution
    - Batch operations using UNWIND for efficiency
    - No GraphCypherQAChain wrapper (overkill for simple MERGE operations)

    Chunk Deduplication:
    - Two files with identical content get the same ChunkParagraph (by chunk_id)
    - Both SourceDocuments reference same ChunkParagraph via CONTAINS
    - Enables queries: "Which files mention this exact text?"

    Input state keys:
        chunk_documents (List[SourceDocumentMetadata]): Files being processed
        chunk_paragraphs (List[ChunkMetadata]): Chunks to create/link
        nodes (List[Node]): KG nodes to link to chunks (must have chunk_id set)

    Output state keys:
        messages (List[str]): Status messages about created nodes/relationships
        current_agent (List[str]): Agent name (for tracking)
    """

    tool_output_keys = ["messages", "current_agent"]

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Load chunk metadata nodes and relationships to Neo4j.

        Args:
            state: KGGenerationState dict

        Returns:
            Status messages and agent tracking info
        """
        graph_store = self.settings.get("graph_store")
        if not graph_store:
            logger.error("ChunkGraphLoad: graph_store not configured")
            return {
                "messages": ["Error: ChunkGraphLoadAgent requires graph_store in settings"],
                "current_agent": [self.__class__.__name__],
            }

        chunk_documents = state.get("chunk_documents", [])
        chunk_paragraphs = state.get("chunk_paragraphs", [])
        nodes = state.get("nodes", [])

        try:
            # 1. Create SourceDocument nodes (MERGE by file_path to deduplicate)
            if chunk_documents:
                self._create_source_documents(graph_store, chunk_documents)

            # 2. Create ChunkParagraph nodes (MERGE by chunk_id to deduplicate by content)
            if chunk_paragraphs:
                self._create_chunk_paragraphs(graph_store, chunk_paragraphs)

            # 3. Link SourceDocument -[CONTAINS]-> ChunkParagraph
            if chunk_paragraphs:
                self._link_documents_to_chunks(graph_store, chunk_paragraphs)

            # 4. Set chunk_id and raw_source_line on nodes (hardcoded Cypher to ensure it's applied)
            # LLM templates might not include chunk_id, so force-set it here
            if nodes:
                self._set_chunk_properties_on_nodes(graph_store, nodes)

            # NOTE: Node-chunk linking happens in Neo4jPostProcessorAgent AFTER nodes are created in Neo4j.
            # We can't link here because nodes don't exist yet (they're created later by NodesLoaderAgent).
            # ChunkGraphLoadAgent only creates SourceDocument/ChunkParagraph structure.

            return {
                "messages": [
                    f"✓ Created {len(set(d.file_path for d in chunk_documents))} SourceDocument nodes",
                    f"✓ Created {len(set(p.chunk_id for p in chunk_paragraphs))} ChunkParagraph nodes (deduplicated by content hash)",
                    f"✓ Linked {len([n for n in nodes if n.chunk_id])} KG nodes to chunks",
                ],
                "current_agent": [self.__class__.__name__],
            }

        except Exception as e:
            logger.error(f"ChunkGraphLoad error: {str(e)}", exc_info=True)
            return {
                "messages": [f"Error in ChunkGraphLoadAgent: {str(e)}"],
                "current_agent": [self.__class__.__name__],
            }

    def _create_source_documents(self, graph_store: Any, documents: List[SourceDocumentMetadata]) -> None:
        """Create SourceDocument nodes (one per unique file).

        MERGE by file_path to deduplicate if same file processed multiple times.

        Args:
            graph_store: Neo4j graph store instance
            documents: List of SourceDocumentMetadata to create
        """
        doc_query = """
        UNWIND $docs AS doc
        MERGE (d:SourceDocument {file_path: doc.file_path})
        ON CREATE SET
            d.file_name = doc.file_name,
            d.total_chunks = doc.total_chunks,
            d.created_at = doc.created_at
        RETURN d
        """

        doc_params = {
            "docs": [
                {
                    "file_path": doc.file_path,
                    "file_name": doc.file_name,
                    "total_chunks": doc.total_chunks,
                    "created_at": doc.created_at,
                }
                for doc in documents
            ]
        }

        graph_store.query(doc_query, params=doc_params)
        logger.info(
            f"ChunkGraphLoad: created {len(set(d.file_path for d in documents))} SourceDocument nodes"
        )

    def _create_chunk_paragraphs(self, graph_store: Any, chunks: List[ChunkMetadata]) -> None:
        """Create ChunkParagraph nodes (one per unique chunk_id).

        MERGE by chunk_id to deduplicate identical chunks across files.
        Two files with same content get same ChunkParagraph node.

        Args:
            graph_store: Neo4j graph store instance
            chunks: List of ChunkMetadata to create
        """
        para_query = """
        UNWIND $paras AS para
        MERGE (p:ChunkParagraph {chunk_id: para.chunk_id})
        ON CREATE SET
            p.chunk_hash = para.chunk_hash,
            p.sequence_num = para.sequence_num,
            p.content_preview = para.content_preview,
            p.token_count = para.token_count,
            p.created_at = para.created_at
        RETURN p
        """

        para_params = {
            "paras": [
                {
                    "chunk_id": para.chunk_id,
                    "chunk_hash": para.chunk_hash,
                    "sequence_num": para.sequence_num,
                    "content_preview": para.content_preview,
                    "token_count": para.token_count,
                    "created_at": para.created_at,
                }
                for para in chunks
            ]
        }

        graph_store.query(para_query, params=para_params)
        logger.info(
            f"ChunkGraphLoad: created {len(set(p.chunk_id for p in chunks))} ChunkParagraph nodes "
            f"(deduplicated by content hash)"
        )

    def _link_documents_to_chunks(self, graph_store: Any, chunks: List[ChunkMetadata]) -> None:
        """Link SourceDocument -[CONTAINS]-> ChunkParagraph.

        Establishes relationship: each source file contains its chunks.

        Args:
            graph_store: Neo4j graph store instance
            chunks: List of ChunkMetadata to link
        """
        link_query = """
        UNWIND $paras AS para
        MATCH (d:SourceDocument {file_path: para.file_path})
        MATCH (p:ChunkParagraph {chunk_id: para.chunk_id})
        MERGE (d)-[r:CONTAINS]->(p)
        RETURN r
        """

        link_params = {
            "paras": [
                {
                    "file_path": para.file_path,
                    "chunk_id": para.chunk_id,
                }
                for para in chunks
            ]
        }

        graph_store.query(link_query, params=link_params)
        logger.info("ChunkGraphLoad: linked SourceDocuments to ChunkParagraphs")

    def _set_chunk_properties_on_nodes(self, graph_store: Any, nodes: List[Node]) -> None:
        """Set chunk_id and raw_source_line on existing nodes using hardcoded Cypher.

        This ensures chunk provenance is captured even if LLM templates weren't followed.
        Uses direct Cypher execution (no LLM) to guarantee chunk properties are set.

        Args:
            graph_store: Neo4j graph store instance
            nodes: List of Node objects with chunk_id to set
        """
        nodes_with_chunks = [n for n in nodes if n.chunk_id]

        if not nodes_with_chunks:
            logger.debug("ChunkGraphLoad: no nodes with chunk_id to update")
            return

        set_query = """
        UNWIND $node_data AS nd
        MATCH (n {node_id: nd.node_id})
        SET n.chunk_id = nd.chunk_id,
            n.raw_source_line = nd.raw_source_line
        RETURN n
        """

        set_params = {
            "node_data": [
                {
                    "node_id": node.node_id,
                    "chunk_id": node.chunk_id,
                    "raw_source_line": node.raw_source_line or "",
                }
                for node in nodes_with_chunks
            ]
        }

        try:
            graph_store.query(set_query, params=set_params)
            logger.info(f"ChunkGraphLoad: set chunk_id and raw_source_line on {len(nodes_with_chunks)} nodes")
        except Exception as e:
            logger.warning(f"ChunkGraphLoad: failed to set chunk properties: {e}")

    def _link_nodes_to_chunks(self, graph_store: Any, nodes: List[Node]) -> None:
        """Link KG_Node -[EXTRACTED_FROM_CHUNK]-> ChunkParagraph.

        Establishes provenance: each extracted entity links to its source chunk.
        Only links nodes that have chunk_id set (extracted via ChunkTrackerAgent).

        Args:
            graph_store: Neo4j graph store instance
            nodes: List of Node objects (only those with chunk_id will be linked)
        """
        nodes_with_chunks = [n for n in nodes if n.chunk_id]

        if not nodes_with_chunks:
            logger.debug("ChunkGraphLoad: no nodes with chunk_id to link")
            return

        link_query = """
        UNWIND $node_data AS nd
        MATCH (n {node_id: nd.node_id})
        MATCH (p:ChunkParagraph {chunk_id: nd.chunk_id})
        MERGE (n)-[r:EXTRACTED_FROM_CHUNK]->(p)
        ON CREATE SET r.raw_source_line = nd.raw_source_line
        RETURN r
        """

        link_params = {
            "node_data": [
                {
                    "node_id": node.node_id,
                    "chunk_id": node.chunk_id,
                    "raw_source_line": node.raw_source_line or "",
                }
                for node in nodes_with_chunks
            ]
        }

        graph_store.query(link_query, params=link_params)
        logger.info(f"ChunkGraphLoad: linked {len(nodes_with_chunks)} KG nodes to ChunkParagraph chunks")
