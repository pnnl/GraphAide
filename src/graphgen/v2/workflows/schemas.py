"""Input and output schemas for all workflows."""

from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

from graphgen.v2.state import Node, Edge, MergedNode, MergedEdge


# ============================================================================
# MULTI-RETRIEVER SUPPORT
# ============================================================================

class VectorStoreConfig(BaseModel):
    """Configuration for a single vector store retriever.

    Maps a vector store to how its data should be retrieved and processed during extraction.
    """
    type: str = Field(..., description="Vector store type (chromadb, qdrant, etc.)")
    path: Optional[str] = Field(None, description="Path to vector store (for file-based stores like ChromaDB)")
    url: Optional[str] = Field(None, description="URL to vector store (for remote stores like Qdrant)")
    collection_name: Optional[str] = Field(None, description="Collection/index name in the vector store")
    api_key: Optional[str] = Field(None, description="API key for remote vector stores")
    retrieve_type: str = Field(..., description="How to process retrieved data: 'ontology', 'entities', 'documents', 'custom'")
    description: Optional[str] = Field(None, description="Human-readable description of this vector store (e.g., 'Wikidata entity context', 'Domain-specific ontology types'). Added to context before retrieval results so LLM understands the data source.")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "type": "chromadb",
                "path": "/data/chroma",
                "collection_name": "documents",
                "retriever_type": "ontology"
            }
        }


# ============================================================================
# KG EXTRACTION (extract_graph function)
# ============================================================================

class KGExtractInput(BaseModel):
    """Input schema for knowledge graph extraction workflow."""
    file_path: Optional[str] = Field(
        None,
        description="Path to PDF or text file to extract from. Either file_path or input_text must be provided."
    )
    input_text: Optional[str] = Field(
        None,
        description="Raw text to extract from. Either file_path or input_text must be provided. If provided, file_path is ignored."
    )
    ontology_path: Optional[str] = Field(
        None,
        description="Optional path to ontology file (.owl, .ttl, .nt)",
        alias="ontology_file_path",
    )
    max_tokens_per_segment: int = Field(
        4096,
        description="Max tokens per text segment. Reduce if LLM calls fail (e.g., 2048)",
    )
    vector_stores: Optional[List[VectorStoreConfig]] = Field(
        None,
        description="Optional list of vector stores for multi-retriever RAG. If provided, dynamically creates retrievers for each store.",
    )
    filter_by_ontology: bool = Field(
        False,
        description="If True, filter nodes/edges to match ontology types. If False, keep all extracted nodes and edges.",
    )
    jsonl_field_name: str = Field(
        "text",
        description="For JSONL files only. Field to extract per line.",
    )
    jsonl_lines_per_batch: int = Field(
        4,
        description="For JSONL files only. Number of lines per batch sent to each extractor. Parallelism auto-scales: ceil(total_lines / lines_per_batch).",
    )
    merge_output: bool = Field(
        False,
        description="If True, output only deduplicated nodes/edges (merged). If False, output raw nodes/edges (may have duplicates).",
    )

    @model_validator(mode="after")
    def validate_input(self):
        """Validate that at least one of file_path or input_text is provided."""
        if not self.file_path and not self.input_text:
            raise ValueError("Either file_path or input_text must be provided")
        return self

    class Config:
        """Pydantic config."""
        populate_by_name = True  # Accept both field name and alias
        json_schema_extra = {
            "example": {
                "file_path": "document.pdf",
                "ontology_path": "ontology.owl",
                "max_tokens_per_segment": 4096,
                "filter_by_ontology": False,
                "vector_stores": [
                    {"type": "chromadb", "path": "/data/chroma1", "collection_name": "documents", "retriever_type": "ontology"},
                    {"type": "chromadb", "path": "/data/chroma2", "collection_name": "documents", "retriever_type": "entities"}
                ]
            }
        }


class KGExtractOutput(BaseModel):
    """Output schema for knowledge graph extraction workflow."""
    nodes: List[Node] = Field(default_factory=list, description="Extracted nodes")
    edges: List[Edge] = Field(default_factory=list, description="Extracted edges")
    segments_processed: int = Field(..., description="Number of document segments processed")
    output_json_path: Optional[str] = Field(
        None, description="Path to saved JSON file with nodes/edges"
    )

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


# ============================================================================
# KG EXTRACTION WITH MERGING (extract_merge_graph function)
# ============================================================================

class KGExtractMergeInput(BaseModel):
    """Input schema for knowledge graph extraction + merging workflow."""
    file_path: str = Field(..., description="Path to PDF or text file to extract from")
    ontology_path: Optional[str] = Field(
        None,
        description="Optional path to ontology file (.owl, .ttl, .nt)",
        alias="ontology_file_path",
    )
    max_tokens_per_segment: int = Field(
        4096,
        description="Max tokens per text segment. Reduce if LLM calls fail (e.g., 2048)",
    )
    vector_stores: Optional[List[VectorStoreConfig]] = Field(
        None,
        description="Optional list of vector stores for multi-retriever RAG. If provided, dynamically creates retrievers for each store.",
    )

    class Config:
        """Pydantic config."""
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "file_path": "document.pdf",
                "ontology_path": "ontology.owl",
                "max_tokens_per_segment": 4096,
                "vector_stores": [
                    {"type": "chromadb", "path": "/data/chroma1", "collection_name": "documents", "retriever_type": "ontology"},
                    {"type": "chromadb", "path": "/data/chroma2", "collection_name": "documents", "retriever_type": "entities"}
                ]
            }
        }


class KGExtractMergeOutput(BaseModel):
    """Output schema for knowledge graph extraction + merging workflow."""
    nodes: List[MergedNode] = Field(default_factory=list, description="Deduplicated and consolidated nodes")
    edges: List[MergedEdge] = Field(default_factory=list, description="Deduplicated and consolidated edges")
    segments_processed: int = Field(..., description="Number of document segments processed")
    output_json_path: Optional[str] = Field(
        None, description="Path to saved JSON file with nodes/edges"
    )

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


# ============================================================================
# KG INGESTION (ingest_to_neo4j function)
# ============================================================================

class KGIngestInput(BaseModel):
    """Input schema for knowledge graph ingestion workflow."""
    file_path: Optional[str] = Field(
        None,
        description="Path to PDF or text file to ingest. Either file_path, input_text, or jsonl_file_path must be provided."
    )
    input_text: Optional[str] = Field(
        None,
        description="Raw text to ingest. Either file_path, input_text, or jsonl_file_path must be provided. If provided, file_path is ignored."
    )
    jsonl_file_path: Optional[str] = Field(
        None,
        description="Path to JSONL file for parallel batch ingestion. Either file_path, input_text, or jsonl_file_path must be provided."
    )
    jsonl_field_name: str = Field(
        "text",
        description="Field name to extract from each JSONL line (used only if jsonl_file_path is provided)"
    )
    jsonl_lines_per_batch: int = Field(
        4,
        description="Lines per batch sent to each extractor. Parallelism auto-scales: ceil(total_lines / lines_per_batch)."
    )
    ontology_path: Optional[str] = Field(
        None,
        description="Optional path to ontology file (.owl, .ttl, .nt)",
        alias="ontology_file_path",
    )
    max_tokens_per_segment: int = Field(
        4096,
        description="Max tokens per text segment. Reduce if LLM calls fail (e.g., 2048)",
    )
    clear_existing: bool = Field(
        False,
        description="Whether to clear existing graph before ingesting (dangerous!)"
    )
    filter_by_ontology: bool = Field(
        True,
        description="If True, filter nodes/edges to match ontology types. If False, keep all extracted nodes and edges.",
    )
    merge_output: bool = Field(
        False,
        description="If True, output only deduplicated nodes/edges (merged). If False, output raw nodes/edges (may have duplicates).",
    )

    @model_validator(mode="after")
    def validate_input(self):
        """Validate that at least one of file_path, input_text, or jsonl_file_path is provided."""
        if not self.file_path and not self.input_text and not self.jsonl_file_path:
            raise ValueError("Either file_path, input_text, or jsonl_file_path must be provided")
        return self

    class Config:
        """Pydantic config."""
        populate_by_name = True  # Accept both field name and alias
        json_schema_extra = {
            "example": {
                "file_path": "document.pdf",
                "ontology_path": "ontology.owl",
                "max_tokens_per_segment": 4096,
                "clear_existing": False,
                "filter_by_ontology": False,
            }
        }


class KGIngestOutput(BaseModel):
    """Output schema for knowledge graph ingestion workflow."""
    nodes_created: int = Field(..., description="Number of nodes created in Neo4j")
    edges_created: int = Field(..., description="Number of edges created in Neo4j")
    segments_processed: int = Field(..., description="Number of document segments processed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "nodes_created": 42,
                "edges_created": 35,
                "segments_processed": 3,
            }
        }


# ============================================================================
# KG LOADING FROM JSON (load_json_to_neo4j function)
# ============================================================================

class KGLoadJsonInput(BaseModel):
    """Input schema for loading pre-extracted JSON into Neo4j."""
    json_path: str = Field(..., description="Path to JSON file from kg_extract output")
    clear_existing: bool = Field(
        False,
        description="Whether to clear existing graph before loading (dangerous!)"
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "json_path": "GraphAide_KG_Extract_20260605_072114.json",
                "clear_existing": False,
            }
        }


class KGLoadJsonOutput(BaseModel):
    """Output schema for loading JSON into Neo4j."""
    nodes_created: int = Field(..., description="Number of nodes created in Neo4j")
    edges_created: int = Field(..., description="Number of edges created in Neo4j")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "nodes_created": 42,
                "edges_created": 35,
            }
        }


# ============================================================================
# KG QUERYING (query_graph function)
# ============================================================================

class KGQueryInput(BaseModel):
    """Input schema for knowledge graph query workflow."""
    question: str = Field(..., description="Natural language question to ask the knowledge graph")
    max_results: int = Field(
        10,
        description="Maximum number of results to return",
        ge=1,
        le=100
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "question": "What organizations are mentioned?",
                "max_results": 10,
            }
        }


class KGQueryOutput(BaseModel):
    """Output schema for knowledge graph query workflow."""
    question: str = Field(..., description="The question that was asked")
    answer: Optional[str] = Field(None, description="Natural language answer to the question")
    graph_answer: Optional[str] = Field(
        None,
        description="Graph traversal result (Cypher or similar)"
    )
    graph_answer_text: Optional[str] = Field(
        None,
        description="Textual interpretation of graph answer"
    )
    related_nodes: List[Node] = Field(
        default_factory=list,
        description="Nodes related to the answer"
    )
    related_edges: List[Edge] = Field(
        default_factory=list,
        description="Edges related to the answer"
    )

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "question": "What organizations are mentioned?",
                "answer": "GraphAide and PNNL are mentioned...",
                "graph_answer": "MATCH (n:Organization) RETURN n",
                "graph_answer_text": "Found 2 organizations",
                "related_nodes": [],
                "related_edges": [],
            }
        }


# ============================================================================
# VECTORDB INGESTION (ingest_to_vectordb function)
# ============================================================================

class VectorDBIngestInput(BaseModel):
    """Input schema for vector store ingestion workflow."""
    file_paths: List[str] = Field(..., description="List of file paths to load into vector store")
    split_docs: bool = Field(
        True,
        description="Whether to split documents into chunks"
    )
    append: bool = Field(
        False,
        description="Whether to append to existing vector store or replace"
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "file_paths": ["document1.pdf", "document2.pdf"],
                "split_docs": True,
                "append": False,
            }
        }


class VectorDBIngestOutput(BaseModel):
    """Output schema for vector store ingestion workflow."""
    documents_loaded: int = Field(..., description="Number of documents loaded")
    chunks_created: int = Field(..., description="Number of text chunks created")
    vector_store_name: str = Field(..., description="Name of vector store")
    vector_store_path: str = Field(..., description="Path to vector store")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "documents_loaded": 2,
                "chunks_created": 15,
                "vector_store_name": "GA_VDB",
                "vector_store_path": "./chroma",
            }
        }


# ============================================================================
# ONTOLOGY GENERATION
# ============================================================================

class OntologyGenerateInput(BaseModel):
    """Input schema for ontology generation workflow."""
    node_types: List[str] = Field(
        ...,
        description="List of node type names (e.g., ['Organization', 'Person', 'Topic'])"
    )
    edge_types: List[str] = Field(
        ...,
        description="List of edge/relationship type names (e.g., ['worksWith', 'relatedTo'])"
    )
    output_path: str = Field(
        default="ontology.nt",
        description="Path to save generated N-Triple ontology file"
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "node_types": ["Organization", "Person", "Topic"],
                "edge_types": ["worksWith", "relatedTo", "manages"],
                "output_path": "ontology.nt",
            }
        }


class OntologyGenerateOutput(BaseModel):
    """Output schema for ontology generation workflow."""
    ontology_file_path: str = Field(..., description="Path to generated N-Triple file")
    node_types_count: int = Field(..., description="Number of node types in ontology")
    edge_types_count: int = Field(..., description="Number of edge types in ontology")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "ontology_file_path": "ontology.nt",
                "node_types_count": 3,
                "edge_types_count": 3,
            }
        }


# ============================================================================
# VECTORDB VISUALIZATION (visualize_vector_store function)
# ============================================================================

class VectorDBVisualizeInput(BaseModel):
    """Input schema for vector store visualization workflow."""
    reuse_embedding: bool = Field(
        False,
        description="Whether to reuse existing UMAP projection if available"
    )
    output_dir: str = Field(
        "./data",
        description="Directory to save visualization outputs"
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "reuse_embedding": False,
                "output_dir": "./data",
            }
        }


class VectorDBVisualizeOutput(BaseModel):
    """Output schema for vector store visualization workflow."""
    projection_file_path: str = Field(..., description="Path to saved UMAP projection file")
    visualization_image_path: str = Field(..., description="Path to saved visualization image")
    projection_metadata_path: str = Field(..., description="Path to projection metadata JSON")
    num_embeddings_projected: int = Field(..., description="Number of embeddings projected")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "projection_file_path": "./data/umap_embeddings.npy",
                "visualization_image_path": "./data/vector_store_visualization.html",
                "projection_metadata_path": "./data/umap_embeddings.npy.metadata.json",
                "num_embeddings_projected": 42,
            }
        }


# ============================================================================
# GENERIC BASE SCHEMAS (for custom workflows)
# ============================================================================

class GenericWorkflowInput(BaseModel):
    """Base schema for custom workflow inputs."""
    pass


class GenericWorkflowOutput(BaseModel):
    """Base schema for custom workflow outputs."""
    result: Optional[dict] = Field(
        None,
        description="Generic result dictionary"
    )
