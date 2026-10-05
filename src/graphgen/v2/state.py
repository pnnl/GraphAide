import hashlib
import operator
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Tuple, TypedDict, Union

from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field


# 0. Span for source alignment
class Span(BaseModel):
    """Character and token span information for source alignment."""

    start: int = Field(description="Start position")
    end: int = Field(description="End position")


# 0b. Chunk Metadata (for chunk tracking and deduplication)
class SourceDocumentMetadata(BaseModel):
    """Metadata for a source document (file).

    Tracks file-level information for chunk management.
    Represents a SourceDocument node in Neo4j (distinct from LangChain Document which is a chunk).
    """
    file_name: str = Field(description="Basename of the file (e.g., 'document.pdf')")
    file_path: str = Field(description="Full file path (source file identifier)")
    total_chunks: int = Field(default=0, description="Number of chunks from this file")
    created_at: Optional[str] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp when document was processed"
    )


class ChunkMetadata(BaseModel):
    """Metadata for a chunk (paragraph).

    Tracks chunk-level information for linking extracted entities to their source chunks.
    Chunks are deduplicated by content hash (chunk_id), enabling deduplication across files.
    """
    chunk_id: str = Field(description="Global chunk identifier (SHA256[:12]) - reproducible across files, enables deduplication")
    chunk_hash: str = Field(description="Full SHA256 hash of chunk content (for uniqueness verification)")
    file_path: str = Field(description="Source file this chunk came from")
    sequence_num: int = Field(description="0-indexed chunk number within the file (e.g., 0, 1, 2...)")
    content_preview: str = Field(description="First 500 characters of chunk content")
    token_count: int = Field(description="Approximate token count for the chunk")
    created_at: Optional[str] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp when chunk was processed"
    )


# 1. Strict Node Schema (Renamed 'type' to 'node_type')
class Node(BaseModel):
    """Defines the structure of a Node in our knowledge graph.
    Each node has a 'node_name' as found in the input text, a 'node_type' which is the label extracted from the retrieved Wikidata QID|label format, an 'english_name' which is the English translation of the node_name, an optional 'wikidata_id' which is the QID of the document retrieved, a 'node_id' which is the same as the Wikidata English label if wikidata_id exists or same as 'english_name' if no wikidata_id is assigned, and an optional 'raw_source' which is a string field for source reference.

    Args:
        BaseModel (_type_): _description_
    """

    node_name: str = Field(
        default="default_name", description="Name as found in input text"
    )
    node_type: str = Field(
        default="default_type",
        description="Label from Wikidata QID|label or english_name",
    )
    english_name: str = Field(
        default="default_english_name", description="English translation of the name"
    )
    wikidata_id: Optional[str] = Field(default=None, description="QID from Wikidata")
    node_id: Optional[str] = Field(
        default=None,
        description="""
        Canonical disambiguation key for entity identity resolution. ALWAYS equals english_name.

        LOGIC: node_id = english_name (always)
        - If Wikidata available: english_name = Wikidata's English label
        - If no Wikidata: english_name = normalized/canonical name

        PURPOSE:
        - Consolidates multilingual/variant mentions of same entity into one canonical identity
        - Enables edge-to-node matching: edges reference source/target by english_name, nodes keyed by node_id
        - Used by ExtractMerger to group and deduplicate nodes across documents/segments

        EXAMPLES:
        1. With Wikidata:
           - node_name="Putin" (English mention), english_name="Vladimir Putin", wikidata_id="Q7747"
           - node_name="Путин" (Russian mention), english_name="Vladimir Putin", wikidata_id="Q7747"
           - node_id="Vladimir Putin" (Wikidata's English label)
           → Both merged into one MergedNode with node_id="Vladimir Putin"
           → Edges reference: source_id="Vladimir Putin" ✓ matches node_id

        2. Without Wikidata:
           - node_name="John Smith", english_name="John Smith" (normalized)
           - node_name="J. Smith", english_name="John Smith" (normalized)
           - node_id="John Smith" (normalized name)
           → Both merged into one MergedNode with node_id="John Smith"
           → Edges reference: source_id="John Smith" ✓ matches node_id

        ROLE FOR AGENTS:
        - Extractor: Set english_name from Wikidata label or normalize; node_id auto-matches english_name
        - ExtractMerger: Group by node_id to consolidate duplicates
        - NodesLoader: Use node_id as UNIQUE constraint in graph database
        - EdgesLoader: Match edges by source_id/target_id which point to node_ids (=english_names) ✓
        """,
    )
    raw_source: Optional[str] = Field(
        default=None, description="Source reference string"
    )
    character_span: Optional[Span] = Field(
        default=None,
        description="Character offset range [start, end] in source text",
    )
    token_span: Optional[Span] = Field(
        default=None,
        description="Token range [start, end] for source model's tokenizer",
    )
    chunk_id: Optional[str] = Field(
        default=None,
        description="Global chunk identifier (SHA256[:12]) - links node to its source chunk (Paragraph node)"
    )
    raw_source_line: Optional[str] = Field(
        default=None,
        description="The 1-2 line context where this node was mentioned in its source chunk"
    )


# 2. Strict Edge Schema
class Edge(BaseModel):
    """Define the structure of an Edge in our knowledge Graph
        Each edge has a 'source_id' which is the english_name of the source node, an 'edge_type' which is the label of the relationship, a 'target_id' which is the english_name of the target node, an optional 'argument_role' which is the extracted role from source to target, optional 'start_datetime' and 'end_datetime' for temporal information, and an optional 'raw_source' which is a file name for source reference.
    Args:
        BaseModel (_type_): _description_
    """

    source_id: Optional[str] = Field(
        default=None, description="English name of the source node"
    )
    target_id: Optional[str] = Field(
        default=None, description="English name of the target node"
    )
    edge_type: Optional[str] = Field(default=None, description="Type of the edge")
    argument_role: Optional[str] = Field(
        default=None, description="Role of the argument"
    )
    start_datetime: Optional[str] = Field(
        default=None, description="Start time if available"
    )
    end_datetime: Optional[str] = Field(
        default=None, description="End time if available"
    )
    raw_source: Optional[str] = Field(
        default=None, description="Name of the input source file"
    )
    character_span: Optional[Span] = Field(
        default=None,
        description="Character offset range [start, end] for the relationship in source text",
    )
    token_span: Optional[Span] = Field(
        default=None,
        description="Token range [start, end] for the relationship in source model's tokenizer",
    )
    chunk_id: Optional[str] = Field(
        default=None,
        description="Global chunk identifier (SHA256[:12]) - links edge to its source chunk (Paragraph node)"
    )
    raw_source_line: Optional[str] = Field(
        default=None,
        description="The 1-2 line context where this relationship was mentioned in its source chunk"
    )


# 3. Merged Node Schema (consolidated from multiple mentions with same node_id)
class MergedNode(BaseModel):
    """Node after consolidating multiple mentions with same node_id.

    Aggregates name variations, type assignments, and source locations
    for the same canonical entity.
    """

    node_id: str = Field(
        description="Canonical identifier (wikidata_id or english_name) - deduplication key"
    )
    wikidata_id: Optional[str] = Field(
        default=None, description="Wikidata QID if grounded"
    )
    english_name: str = Field(description="Primary English name (canonical)")

    # Consolidated mentions (lists)
    node_names: List[str] = Field(
        description="All name variations found across mentions"
    )
    node_types: List[str] = Field(
        description="All type assignments across different mentions"
    )

    # Source locations (all occurrences)
    character_spans: List[Span] = Field(
        description="All character positions where this node appears"
    )
    token_spans: List[Span] = Field(
        description="All token ranges where this node appears"
    )
    raw_sources: List[str] = Field(description="All source files mentioning this node")

    # Merge metadata
    mention_count: int = Field(
        default=1, description="How many mentions were consolidated"
    )

    # Chunk tracking
    chunk_ids: List[str] = Field(
        default_factory=list,
        description="Global chunk IDs where this node was extracted (for multi-chunk nodes)"
    )


# 4. Merged Edge Schema (consolidated from multiple mentions with same source, target, type)
class MergedEdge(BaseModel):
    """Edge after consolidating multiple mentions with same (source, target, edge_type).

    Aggregates argument roles, temporal info, and source locations for the same relationship.
    """

    source_id: str = Field(description="English name of the source node")
    target_id: str = Field(description="English name of the target node")
    edge_type: str = Field(description="Type of the relationship")

    # Consolidated variations (lists)
    argument_roles: List[Optional[str]] = Field(
        description="All argument roles assigned to this relationship"
    )
    start_datetimes: List[Optional[str]] = Field(
        description="All start times if temporal"
    )
    end_datetimes: List[Optional[str]] = Field(description="All end times if temporal")

    # Source tracking (lists)
    character_spans: List[Span] = Field(
        description="All character positions where this relationship appears"
    )
    token_spans: List[Span] = Field(
        description="All token ranges where this relationship appears"
    )
    raw_sources: List[str] = Field(
        description="All source files mentioning this relationship"
    )

    # Merge metadata
    mention_count: int = Field(
        default=1, description="How many relationship mentions were consolidated"
    )

    # Chunk tracking
    chunk_ids: List[str] = Field(
        default_factory=list,
        description="Global chunk IDs where this relationship was extracted (for multi-chunk edges)"
    )


# 4. Multi-Retriever Support Classes
class RetrievalResultType(str, Enum):
    """Types of retrieval results for multi-retriever RAG."""
    TYPES = "types"                    # Ontology types (node/edge)
    ENTITIES = "entities"              # Wikidata/DBpedia entities
    DOCUMENTS = "documents"            # Raw documents/passages
    RELATIONSHIPS = "relationships"    # Pre-extracted relationships
    IMAGES = "images"                  # Image metadata (multimodal)
    CUSTOM = "custom"                  # Custom domain-specific results


class RetrievalResult(BaseModel):
    """Standardized container for retrieval results from any source.

    Enables heterogeneous retrieval sources (vector stores, APIs, local files)
    to return results in a consistent format that agents can consume uniformly.
    """
    source: str = Field(..., description="Source identifier (e.g., 'vectorstore_ontology', 'vectorstore_entities')")
    result_type: RetrievalResultType = Field(..., description="Type of retrieval result")
    store_description: Optional[str] = Field(None, description="Human-readable description of the vector store (e.g., 'Wikidata entity context'). Added to context before results so LLM understands data source.")

    # Typed fields for different result_type values
    ontology_node_types: Optional[List[str]] = Field(None, description="For TYPES: allowed node types")
    ontology_edge_types: Optional[List[str]] = Field(None, description="For TYPES: allowed edge types")
    wikidata_context: Optional[Dict[str, Any]] = Field(None, description="For ENTITIES: QID→metadata")
    documents: Optional[List[str]] = Field(None, description="For DOCUMENTS: retrieved passages")
    relationships: Optional[List[Dict[str, Any]]] = Field(None, description="For RELATIONSHIPS: pre-extracted")
    custom_data: Optional[Dict[str, Any]] = Field(None, description="For CUSTOM: domain-specific data")

    # Source-specific metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Source-specific metadata")


# 5. RAG Pipeline Context
class RAGContext(BaseModel):
    """Consolidated context for the RAG pipeline.

    Holds all context data needed across RAG steps: ontology metadata,
    external knowledge sources (Wikidata, DBpedia, etc.), and retrieval configs.

    Benefits:
    - Single context object instead of scattered state fields
    - Extensible: add new data sources without modifying KGGenerationState
    - Type-safe: Pydantic validates all context data
    """

    ontology_node_types: List[str] = Field(
        default_factory=list, description="List of valid node types from ontology"
    )
    ontology_edge_types: List[str] = Field(
        default_factory=list, description="List of valid edge types from ontology"
    )
    ontology_node_definitions: Dict[str, str] = Field(
        default_factory=dict,
        description="Node type → definition mapping (from skos:definition in RDF)"
    )
    ontology_node_examples: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Node type → list of examples (from skos:example in RDF)"
    )
    ontology_edge_definitions: Dict[str, str] = Field(
        default_factory=dict,
        description="Edge type → definition mapping (from skos:definition in RDF)"
    )
    ontology_edge_examples: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Edge type → list of examples (from skos:example in RDF)"
    )
    wikidata_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Wikidata QID → entity metadata (label, description, etc.)",
    )
    retrieval_results: List[RetrievalResult] = Field(
        default_factory=list,
        description="Standardized results from all retrievers (ontology, entities, documents, etc.)",
    )


# 5. The Central State
# Using Annotated + operator.add ensures that each of your 10 agents
# appends their findings to the list rather than overwriting previous work.
class KGGenerationState(TypedDict):
    """Defines the central state structure used by the GraphAide agents.

    Args:
        TypedDict (_type_): _description_
    """

    # Allows Pydantic to handle complex nested objects
    model_config = ConfigDict(arbitrary_types_allowed=True)

    raw_text: Annotated[str, lambda a, b: b]  # Last write wins (parallel-safe)
    segments: Annotated[List[str], operator.add]
    file_path: Annotated[
        Optional[str], lambda a, b: b
    ]  # Last write wins (parallel-safe)
    input_text: Annotated[
        Optional[str], lambda a, b: b
    ]  # Raw text input (parallel-safe)
    file_paths: Annotated[
        Optional[Union[List[str], str]], lambda a, b: b
    ]  # List or comma-separated paths (parallel-safe)
    unstructured_response: Annotated[List[str], operator.add]
    nodes: Annotated[List[Node], operator.add]
    edges: Annotated[List[Edge], operator.add]
    merged_nodes: Annotated[List[MergedNode], operator.add]
    merged_edges: Annotated[List[MergedEdge], operator.add]

    # Metadata for multi-agent coordination (uses add_messages for ReAct compatibility)
    messages: Annotated[list, add_messages]

    # Metadata for vector store
    is_raw_embedding: Optional[bool]
    embedding_file_path: Optional[str]
    reuse_embedding_file_path: Optional[bool] = False
    append: Optional[bool]
    section_chunking: Optional[bool]  # Use section-based PDF chunking with unstructured
    max_characters: Optional[
        int
    ]  # Max chars per section chunk when section_chunking=True
    max_tokens_per_segment: Optional[int]  # Max tokens per segment (default 4096)
    vector_store_provider: Optional[
        str
    ]  # Vector store provider: "chromadb" or "qdrant" (default: "chromadb")
    use_vision_extraction: Optional[bool] = (
        False  # Extract text from images using vision model
    )
    image_file_paths: Optional[List[str]] = None  # List of image file paths (PNG/JPG)
    extract_pdf_images: Optional[bool] = False  # Extract images from PDFs

    # CSV/file loader metadata
    source_column: Optional[str]  # Column name for document source (CSV files)
    external_metadata: Optional[Dict[str, str]]  # Filename→category mapping
    internal_metadata: Optional[List[str]]  # Column names to include as metadata

    # RAG pipeline context (ontology, Wikidata, retrieval configs, etc.)
    ontology_file_path: Optional[str]
    filter_by_ontology: Annotated[bool, lambda a, b: b] = False  # Filter nodes/edges by ontology types (default: False)
    rag_context: Optional[RAGContext]
    vector_store_configs: Annotated[List, operator.add]  # Multi-retriever vector store configs

    # Ontology generation inputs (for ontology_generate workflow)
    node_types: Annotated[List[str], operator.add]
    edge_types: Annotated[List[str], operator.add]
    output_path: Optional[str]

    # Batch tracking (for kg_load_json workflow with large files)
    batch_index: Optional[int]  # Current batch number (1-indexed)
    total_batches: Optional[int]  # Total number of batches

    # Output file path for kg_extract results
    output_json_path: Optional[str]

    # Chunk tracking (for chunk-aware KG extraction)
    current_chunk_id: Annotated[Optional[str], lambda a, b: b]  # chunk_id for current segment (Global identifier) - last write wins
    chunk_sequence: Annotated[Optional[int], lambda a, b: b]  # 0-indexed chunk number within current file (for dispatcher) - last write wins
    total_chunks: Annotated[Optional[int], lambda a, b: b]  # Total chunks in current file (from FileLoader) - last write wins
    chunk_documents: Annotated[List[SourceDocumentMetadata], operator.add]  # Tracked source documents (accumulate)
    chunk_paragraphs: Annotated[List[ChunkMetadata], operator.add]  # Tracked chunks/paragraphs (accumulate)

    current_agent: Annotated[List[str], operator.add]
    agent_status: Annotated[Dict[str, bool], lambda a, b: {**a, **b}]

    # JSONL ingestion fields (file_path is reused for JSONL files - auto-detected by .jsonl extension)
    jsonl_field_name: str = "text"  # Field to extract per line
    jsonl_lines: Annotated[List[Dict], operator.add]  # Lines in current batch
    jsonl_line_numbers: Annotated[List[int], operator.add]  # Corresponding line numbers
    jsonl_failed_lines: Annotated[List[Dict], operator.add]  # Failed lines (with error details)
    jsonl_tracking: bool = True  # Enable provenance tracking
    jsonl_lines_per_batch: int = 4  # Lines per batch sent to each extractor

    # Merge output flag (output only merged nodes/edges when merge=True)
    merge_output: Annotated[bool, lambda a, b: b] = False  # If True, skip raw nodes/edges, output merged only


class ExtractGraphV3(BaseModel):
    nodes: List[dict] = Field(
        description="list of all the nodes. Every entry is an object of node_name in original language of input text, type, wikidata_id if available, start_time if available, end_time if available, english_lable if node_name is not in english, otherwise same as node_name., the last element is raw_source, the name of the input source file. Only node_name is mandatory and can not be None."
    )
    edges: List[dict] = Field(
        description="list of all the edges. Every entry is an object of source, edge_type, target, start_time, end_time. the last element is raw_source, the name of the input source file, if provided. Only source and target nodes are mandatory and can not be None."
    )


class KnowledgGraph(BaseModel):
    nodes: List[dict] = Field(
        description="list of all the nodes. Each node entry is an object of 'name' as found in the input text, its 'type' as extracted from the lable of the retrieved wikidata QID|label format, 'english_name' which is the english translation of the 'name', 'wikidata_id' which is the QID of the document retrieved as listed in QID|lable, and 'node_id' which is same as the Wikidata English label if wikidata_id exists, If no wikidata_id is assigned, it is same as 'english_name', 'raw_source' is a string field"
    )
    edges: List[dict] = Field(
        description="list of all the edges. Every edge entry is an object of <source_id>, <edge_type>, <target_id>, <argument_role> if available, <start_datetime> if avialable, <end_datetime> if available. source_id is the english_name of the source node, edge_type is the lable of the relationship. target_id is the english_name of the target node. <argument_role> is the extracted role from source to target. <raw_source> is a file name."
    )


class IntentSchema(BaseModel):
    """
    Independent 0..1 scores for five intent dimensions.
    Sum is NOT constrained; each dimension is scored on its own scale.
    """

    subjectivity: float = Field(
        ..., ge=0.0, le=1.0, description="Opinion/sentiment strength"
    )
    locality: float = Field(
        ..., ge=0.0, le=1.0, description="Context-specific place/time"
    )
    navigationality: float = Field(
        ..., ge=0.0, le=1.0, description="Seeking pointers/links/locations"
    )
    procedurality: float = Field(
        ..., ge=0.0, le=1.0, description="Step-by-step/how-to guidance"
    )
    causality: float = Field(
        ..., ge=0.0, le=1.0, description="Reasons/causes/explanations"
    )


class KGQuestionAnswerState(TypedDict):
    """This state structure is designed to hold all relevant information for a question-answering task on the knowledge graph.
    It includes the original question, a list of extended question-answer pairs for context, the.
    Args:
        TypedDict (_type_): _description_
    """

    question: str  # The input question to be answered using the knowledge graph
    extended_QA_pairs: Annotated[
        List[Tuple[str, str]], operator.add
    ]  # List of (question, answer) pairs for context
    extended_QC_pairs: Annotated[
        List[Tuple[str, str]], operator.add
    ]  # List of (question, cypher) pairs for context
    answer: Optional[str]
    graph_question: Optional[
        str
    ]  # The reformulated question for graph querying, if applicable
    graph_answer: Optional[
        str
    ]  # The answer retrieved from the graph database, if applicable
    graph_answer_text: Optional[
        str
    ]  # A natural language description of the graph answer, if applicable
    intent_scores: Optional[IntentSchema]
    related_nodes: Annotated[List[Node], operator.add]
    related_edges: Annotated[List[Edge], operator.add]
    is_answered: bool
    retrieved_docs: Annotated[
        list, operator.add
    ]  # Documents retrieved from vector store
    retrieved_context: Optional[str]  # Formatted context from vector store
    # Metadata for multi-agent coordination (uses add_messages for ReAct compatibility)
    messages: Annotated[list, add_messages]
