"""GraphAide Facade API - Simplified user-facing interface for GraphAide workflows.

The GraphAide class provides a clean, intuitive API for common knowledge graph operations:
- Extract nodes/edges from documents
- Load to Neo4j knowledge graph
- Query natural language over the graph
- Manage vector stores

All configuration is explicit (no magic auto-loading), but the interface hides the
complexity of WorkflowManager, WorkflowConfig, and workflow orchestration.
"""

import logging

from graphgen.v2.GraphDBManager import GraphDBConfig
from graphgen.v2.ModelManager import ModelConfig
from graphgen.v2.VectorStoreManager import VectorDBConfig
from graphgen.v2.workflows import WorkflowConfig, WorkflowManager, WorkflowResult

logger = logging.getLogger(__name__)


class GraphAide:
    """Main user-facing API for GraphAide workflows.

    Provides convenient methods for knowledge graph construction and querying.
    Requires explicit configuration (ModelConfig, GraphDBConfig) but hides
    WorkflowManager and parameter wiring complexity.

    Attributes:
        model_config: LLM configuration (provider, model, API key, etc.)
        graphdb_config: Neo4j database configuration
        vector_config: Vector store configuration (optional)
        workflow_config: Workflow base configuration (auto-created if not provided)
        manager: Internal WorkflowManager instance

    Example:
        from graphaide import GraphAide, ModelConfig, GraphDBConfig

        graphaide = GraphAide(
            model_config=ModelConfig(
                provider="openai",
                model_name="gpt-4o",
                api_key="sk-...",
                embedding_model_name="text-embedding-3-small",
            ),
            graphdb_config=GraphDBConfig(
                uri="neo4j://localhost:7687",
                username="neo4j",
                password="neo4jpwd",
            ),
        )

        # Simple extract
        result = graphaide.extract(file_path="doc.pdf", ontology_path="ont.ttl")

        # Extract with advanced parameters
        result = graphaide.extract(
            file_path="doc.pdf",
            ontology_path="ont.ttl",
            section_chunking=True,
            extract_pdf_images=True,
            use_vision_extraction=True,
        )

        # Query the graph
        answer = graphaide.query(question="What is X?")
    """

    def __init__(
        self,
        model_config: ModelConfig,
        graphdb_config: GraphDBConfig,
        vector_configs: VectorDBConfig | list[VectorDBConfig] | None = None,
        workflow_config: WorkflowConfig | None = None,
    ):
        """Initialize GraphAide with required configurations.

        Args:
            model_config: LLM configuration (required).
                Specifies provider (openai, anthropic, google, bedrock),
                model name, API key, and embedding model.
            graphdb_config: Neo4j database configuration (required).
                Specifies URI, username, password, and database name.
            vector_configs: Vector store configuration(s) (optional).
                Can be a single VectorDBConfig or a list of VectorDBConfig objects.
                For multi-retriever RAG with multiple vector stores.
                Single config: VectorDBConfig(...)
                Multiple configs: [ontology_store, wikidata_store, documents_store]
            workflow_config: Workflow base configuration (optional).
                If not provided, auto-created from model_config and graphdb_config.
                Use this to customize WorkflowManager behavior.

        Raises:
            ValueError: If model_config or graphdb_config is None.

        Example - Single vector store:
            from graphaide import VectorDBConfig, RetrieveType

            graphaide = GraphAide(
                model_config=model_config,
                graphdb_config=graphdb_config,
                vector_configs=VectorDBConfig(
                    provider="chromadb",
                    store_name="documents",
                    store_path="...",
                    retrieve_type=RetrieveType.DOCUMENTS
                )
            )

        Example - Multi-retriever with multiple stores:
            from graphaide import VectorDBConfig, IngestType, RetrieveType

            graphaide = GraphAide(
                model_config=model_config,
                graphdb_config=graphdb_config,
                vector_configs=[
                    VectorDBConfig(
                        provider="chromadb",
                        store_name="ontology_types",
                        store_path="...",
                        ingest_type=IngestType.ONTOLOGY,
                        retrieve_type=RetrieveType.ONTOLOGY
                    ),
                    VectorDBConfig(
                        provider="chromadb",
                        store_name="wikidata_qids",
                        store_path="...",
                        ingest_type=IngestType.ENTITIES,
                        retrieve_type=RetrieveType.ENTITIES
                    ),
                ]
            )
        """
        if model_config is None:
            raise ValueError("model_config is required")
        if graphdb_config is None:
            raise ValueError("graphdb_config is required")

        self.model_config = model_config
        self.graphdb_config = graphdb_config

        # Normalize vector_configs: convert single config to list
        if vector_configs is not None:
            if isinstance(vector_configs, list):
                self.vector_configs = vector_configs
            else:
                # Single VectorDBConfig provided, wrap in list
                self.vector_configs = [vector_configs]
        else:
            self.vector_configs = None

        # Create workflow config if not provided
        self.workflow_config = workflow_config or WorkflowConfig(
            model_config=model_config,
            graphdb_config=graphdb_config,
        )

        # Attach vector config(s) if provided
        if self.vector_configs:
            # Set first config as primary for backwards compatibility
            self.workflow_config.vector_config = self.vector_configs[0]

        # Initialize internal WorkflowManager
        self.manager = WorkflowManager(global_config=self.workflow_config)

    def extract(
        self,
        file_path: str | None = None,
        input_text: str | None = None,
        ontology_path: str | None = None,
        max_tokens_per_segment: int = 4096,
        use_chunk_aware: bool = False,
        filter_by_ontology: bool = False,
        merge: bool = False,
        jsonl_field_name: str = "text",
        jsonl_lines_per_batch: int = 4,
        **kwargs,
    ) -> WorkflowResult:
        # DEBUG: Log what we have at the start
        logger.debug("GraphAide.extract() called")
        logger.debug(f"  self.vector_configs = {self.vector_configs}")
        logger.debug(f"  file_path = {file_path}")
        logger.debug(f"  use_chunk_aware = {use_chunk_aware}")
        """Extract knowledge graph nodes and edges from document(s) or text.

        Extracts entities and relationships from text/PDF documents and saves
        results to JSON. Optionally tracks chunk provenance for multi-document graphs.

        For JSONL files: Automatically detects .jsonl extension and routes to parallel
        batch processing with configurable workers and batch size. Same extraction
        engine, but optimized for line-delimited input.

        Args:
            file_path: Path to document (PDF, TXT, CSV, JSONL, etc.).
                Supports multiple file formats via LangChain loaders.
                For JSONL files: Automatically uses parallel batch extraction.
                Either file_path or input_text must be provided.
            input_text: Raw text to extract from.
                Either file_path or input_text must be provided.
                If provided, file_path is ignored.
            ontology_path: Path to ontology file (OWL, TTL, NT, RDF/XML).
                Defines valid node types and edge types for filtering.
                Optional; if None, all extracted types are kept.
            max_tokens_per_segment: Maximum tokens per text segment (chunk).
                Default 4096. Reduce if LLM fails on large chunks.
                Affects extraction quality and cost.
            use_chunk_aware: If True, use chunk-aware extraction workflow.
                Creates SourceDocument and ChunkParagraph nodes in Neo4j.
                Enables queries like "Show entities from chunk#5".
            filter_by_ontology: If True, filter extracted nodes/edges to match ontology types.
                If False, keep all extracted nodes and edges regardless of ontology.
                Default False. Use True to enforce ontology constraints.
            merge: If True, deduplicate nodes/edges by node_id and output only merged results.
                If False (default), output raw extracted nodes (duplicates possible across segments).
                Merging is automatic for JSONL but must be explicitly requested for other formats.
                Default False.
            jsonl_field_name: For JSONL files only. Field to extract per line. Default "text".
            jsonl_lines_per_batch: For JSONL files only. Lines per batch sent to each extractor. Parallelism auto-scales. Default 4.
            **kwargs: Additional workflow parameters, e.g.:
                - log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR)
                - section_chunking (bool): Use section-based PDF chunking
                - extract_pdf_images (bool): Extract images from PDFs
                - use_vision_extraction (bool): Use vision model for images
                - external_metadata (Dict[str, str]): File→category mapping
                - internal_metadata (List[str]): Columns to include as metadata
                - is_raw_embedding (bool): Raw embedding mode
                - append (bool): Append to existing vector store
                - Any other KGGenerationState field

        Returns:
            WorkflowResult with extracted nodes and edges.
            Access via: result.nodes, result.edges, result.stats

        Raises:
            ValueError: If neither file_path nor input_text is provided.
            RuntimeError: If extraction fails (LLM, Neo4j, or vector store error).

        Example:
            # Extract from file
            result = graphaide.extract(file_path="doc.pdf", ontology_path="ontology.ttl")
            print(f"Extracted {len(result.nodes)} nodes, {len(result.edges)} edges")

            # Extract from text
            result = graphaide.extract(
                input_text="Copper is a metal used in electronics.",
                use_chunk_aware=True
            )
            print(f"Chunks tracked: {result.stats.get('chunks_tracked')}")
        """
        if not file_path and not input_text:
            raise ValueError("Either file_path or input_text must be provided")

        # Handle log_level if provided
        log_level = kwargs.pop("log_level", None)
        if log_level:
            from graphgen.v2.utils import setup_logging
            setup_logging(log_level=log_level)

        # Build vector_stores list from vector_configs if provided (used by all workflows)
        vector_stores = None
        logger.debug(f"GraphAide.extract: self.vector_configs = {self.vector_configs}")
        if self.vector_configs:
            from graphgen.v2.workflows.schemas import VectorStoreConfig
            from pathlib import Path

            vector_stores = []
            for config in self.vector_configs:
                # Use explicit retrieve_type from config
                retrieve_type = (
                    config.retrieve_type.value
                    if hasattr(config.retrieve_type, "value")
                    else str(config.retrieve_type)
                )

                # Combine store_path + store_name to get the actual persist directory
                persist_dir = (
                    str(Path(config.store_path) / config.store_name)
                    if config.store_path
                    else config.store_name
                )

                vector_stores.append(
                    VectorStoreConfig(
                        type=config.provider,
                        path=persist_dir,
                        url=getattr(config, "url", None),
                        collection_name=None,  # Use default Chroma collection
                        retrieve_type=retrieve_type,
                        description=getattr(config, "description", None),
                    )
                )
            logger.debug(f"Converted {len(vector_stores)} vector_configs to VectorStoreConfig")

        # Auto-detect JSONL files and route to parallel extraction
        if file_path and file_path.lower().endswith(".jsonl"):
            logger.info(f"Detected JSONL file in extract: {file_path}")
            logger.debug(
                f"  Field: {jsonl_field_name}, Lines per batch: {jsonl_lines_per_batch}, merge={merge}"
            )

            logger.debug(
                f"GraphAide.extract (JSONL): Calling manager.run() with vector_stores={vector_stores}"
            )
            result = self.manager.run(
                "kg_extract_jsonl_batch",
                {
                    "file_path": file_path,
                    "jsonl_field_name": jsonl_field_name,
                    "jsonl_lines_per_batch": jsonl_lines_per_batch,
                    "ontology_path": ontology_path,
                    "filter_by_ontology": filter_by_ontology,
                    "max_tokens_per_segment": max_tokens_per_segment,
                    "vector_stores": vector_stores,
                    "merge_output": merge,  # Flag for result_packer to output only merged nodes
                    **kwargs,
                },
            )

            # Flush any pending LangFuse traces to ensure they reach the cloud
            try:
                from graphgen.v2.LangFuseManager import flush_langfuse_traces
                flush_langfuse_traces()
            except Exception as e:
                logger.debug(f"Could not flush LangFuse traces: {e}")

            return result

        # Standard extraction for non-JSONL files
        if merge and not use_chunk_aware:
            # Use kg_extract_merge workflow for deduplication
            workflow_name = "kg_extract_merge"
            logger.debug("Using kg_extract_merge workflow (merge=True)")
        else:
            workflow_name = "kg_extract_chunk_aware" if use_chunk_aware else "kg_extract"

        result = self.manager.run(
            workflow_name,
            {
                "file_path": file_path,
                "input_text": input_text,
                "ontology_path": ontology_path,
                "max_tokens_per_segment": max_tokens_per_segment,
                "filter_by_ontology": filter_by_ontology,
                "vector_stores": vector_stores,
                "merge_output": merge,
                **kwargs,
            },
        )

        # Flush any pending LangFuse traces to ensure they reach the cloud
        try:
            from graphgen.v2.LangFuseManager import flush_langfuse_traces
            flush_langfuse_traces()
        except Exception as e:
            logger.debug(f"Could not flush LangFuse traces: {e}")

        return result

    def ingest(
        self,
        file_path: str | None = None,
        input_text: str | None = None,
        ontology_path: str | None = None,
        max_tokens_per_segment: int = 4096,
        use_chunk_aware: bool = False,
        filter_by_ontology: bool = False,
        merge: bool = False,
        jsonl_field_name: str = "text",
        jsonl_lines_per_batch: int = 4,
        **kwargs,
    ) -> WorkflowResult:
        """Extract knowledge graph and load directly to Neo4j.

        Combines extraction and Neo4j loading in one step. Extracted nodes
        and edges are created as nodes and relationships in the Neo4j database.
        Optionally tracks chunk provenance by creating SourceDocument and
        ChunkParagraph nodes.

        Automatically detects JSONL files and routes to parallel batch ingestion.

        Args:
            file_path: Path to document (PDF, TXT, CSV, JSONL, etc.).
                For JSONL files: extracts specified field, processes in parallel batches.
                For other files: standard single-file extraction.
                Either file_path or input_text must be provided.
            input_text: Raw text to ingest.
                Either file_path or input_text must be provided.
                If provided, file_path is ignored.
            ontology_path: Path to ontology file (OWL, TTL, NT, RDF/XML).
            max_tokens_per_segment: Maximum tokens per segment. Default 4096.
            use_chunk_aware: If True, create SourceDocument and ChunkParagraph nodes
                in Neo4j and link extracted entities to their source chunks.
                Enables queries like "Show all entities from document.pdf chunk#5".
                Default False.
            filter_by_ontology: If True, filter extracted nodes/edges to match ontology types.
                If False, keep all extracted nodes and edges. Default False.
            merge: If True, deduplicate nodes/edges by node_id before loading to Neo4j.
                If False (default), load raw extracted nodes (duplicates possible).
                Applies to both regular files and JSONL. Default False.
            jsonl_field_name: For JSONL files only. Field to extract per line. Default "text".
            jsonl_lines_per_batch: For JSONL files only. Lines per batch sent to each extractor. Parallelism auto-scales. Default 4.
            **kwargs: Additional workflow parameters, e.g.:
                - log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR)
                - section_chunking (bool): Use section-based PDF chunking
                - extract_pdf_images (bool): Extract images from PDFs
                - use_vision_extraction (bool): Use vision model for images
                - external_metadata (Dict[str, str]): File→category mapping
                - internal_metadata (List[str]): Columns to include as metadata
                - Any other KGGenerationState field

        Returns:
            WorkflowResult with extraction and ingestion stats.

        Raises:
            ValueError: If neither file_path nor input_text is provided.

        Example:
            # Ingest regular file
            result = graphaide.ingest(file_path="doc.pdf", ontology_path="ontology.ttl")
            print(f"Created {result.stats['nodes_created']} nodes in Neo4j")

            # Ingest JSONL (auto-detected, uses parallel batching)
            result = graphaide.ingest(
                file_path="abstracts.jsonl",
                jsonl_field_name="abstract",
                jsonl_lines_per_batch=4,
            )
            print(f"Nodes: {result.stats['nodes_created']}")
            print(f"Failed lines: {len(result.stats.get('failed_lines', []))}")

            # Ingest from text with chunk tracking
            result = graphaide.ingest(
                input_text="Copper is used in electronics and renewable energy.",
                use_chunk_aware=True,
            )
            print(f"Chunks tracked: {result.stats.get('chunks_tracked')}")
        """
        if not file_path and not input_text:
            raise ValueError("Either file_path or input_text must be provided")

        # Handle log_level if provided
        log_level = kwargs.pop("log_level", None)
        if log_level:
            from graphgen.v2.utils import setup_logging
            setup_logging(log_level=log_level)

        # Build vector_stores list from vector_configs if provided (used by all workflows)
        vector_stores = None
        logger.debug(f"GraphAide.ingest: self.vector_configs = {self.vector_configs}")
        if self.vector_configs:
            from graphgen.v2.workflows.schemas import VectorStoreConfig
            from pathlib import Path

            vector_stores = []
            for config in self.vector_configs:
                # Use explicit retrieve_type from config
                retrieve_type = (
                    config.retrieve_type.value
                    if hasattr(config.retrieve_type, "value")
                    else str(config.retrieve_type)
                )

                # Combine store_path + store_name to get the actual persist directory
                persist_dir = (
                    str(Path(config.store_path) / config.store_name)
                    if config.store_path
                    else config.store_name
                )

                vector_stores.append(
                    VectorStoreConfig(
                        type=config.provider,
                        path=persist_dir,
                        url=getattr(config, "url", None),
                        collection_name=None,  # Use default Chroma collection
                        retrieve_type=retrieve_type,
                        description=getattr(config, "description", None),
                    )
                )
            logger.debug(f"Converted {len(vector_stores)} vector_configs to VectorStoreConfig")

        # Auto-detect JSONL files and route to parallel ingestion
        if file_path and file_path.lower().endswith(".jsonl"):
            logger.info(f"Detected JSONL file: {file_path}")
            logger.debug(
                f"  Field: {jsonl_field_name}, Lines per batch: {jsonl_lines_per_batch}"
            )

            return self.manager.run(
                "kg_ingest_jsonl_batch",
                {
                    "file_path": file_path,
                    "jsonl_field_name": jsonl_field_name,
                    "jsonl_lines_per_batch": jsonl_lines_per_batch,
                    "ontology_path": ontology_path,
                    "filter_by_ontology": filter_by_ontology,
                    "vector_stores": vector_stores,
                    "merge": merge,  # Pass merge flag for deduplication
                    **kwargs,
                },
            )

        # Standard file extraction for non-JSONL files
        if merge and not use_chunk_aware:
            # Use kg_ingest_merge workflow for deduplication
            workflow_name = "kg_ingest_merge"
            logger.debug("Using kg_ingest_merge workflow (merge=True)")
        else:
            workflow_name = "kg_ingest_chunk_aware" if use_chunk_aware else "kg_ingest"

        return self.manager.run(
            workflow_name,
            {
                "file_path": file_path,
                "input_text": input_text,
                "ontology_path": ontology_path,
                "max_tokens_per_segment": max_tokens_per_segment,
                "filter_by_ontology": filter_by_ontology,
                "vector_stores": vector_stores,
                "merge": merge,
                **kwargs,
            },
        )

    def query(self, question: str, **kwargs) -> WorkflowResult:
        """Query the knowledge graph with natural language.

        Accepts natural language questions and returns answers by:
        1. Predicting query intent (subjectivity, locality, etc.)
        2. Querying the Neo4j graph (Cypher)
        3. Augmenting with vector store context (RAG)
        4. Generating natural language response

        Args:
            question: Natural language question about the graph.
                E.g., "What chemicals are used in X process?"
            **kwargs: Additional query parameters, e.g.:
                - extended_QA_pairs: Previous Q&A for context
                - extended_QC_pairs: Previous Q&Cypher pairs

        Returns:
            WorkflowResult with natural language answer and related graph entities.
            Access via: result.answer, result.nodes, result.edges

        Example:
            result = graphaide.query("What processes use copper?")
            print(f"Answer: {result.answer}")
            print(f"Related entities: {[n.node_id for n in result.nodes]}")
        """
        # Handle log_level if provided
        log_level = kwargs.pop("log_level", None)
        if log_level:
            from graphgen.v2.utils import setup_logging
            setup_logging(log_level=log_level)

        return self.manager.run(
            "kg_query",
            {"question": question, **kwargs},
        )

    def load_json(self, json_path: str, **kwargs) -> WorkflowResult:
        """Load previously extracted JSON graph to Neo4j.

        Takes a JSON file (output from extract()) and loads the nodes and edges
        into Neo4j. Useful for separating extraction (slow) from ingestion (fast).

        Args:
            json_path: Path to JSON file created by extract() workflow.
                File should contain "nodes" and "edges" arrays.
            **kwargs: Additional loading parameters.

        Returns:
            WorkflowResult with loading stats (nodes_created, edges_created).

        Example:
            result = graphaide.load_json("GraphAide_KG_Extract_20260807.json")
            print(f"Loaded {result.stats['nodes_created']} nodes")
        """
        return self.manager.run(
            "kg_load_json",
            {"json_path": json_path, **kwargs},
        )

    def ingest_vectors(
        self,
        file_paths: str | list[str],
        **kwargs,
    ) -> WorkflowResult:
        """Ingest documents to vector store for semantic search.

        Splits documents into chunks, embeds them, and stores in vector store
        (ChromaDB or Qdrant). Enables semantic search and RAG for query answering.

        Args:
            file_paths: Single file path (str) or list of file paths.
                Automatically converted to list if str.
            **kwargs: Additional parameters, e.g.:
                - split_docs (bool): Split docs into chunks
                - append (bool): Append to existing store vs. replace

        Returns:
            WorkflowResult with ingestion stats (documents_loaded, chunks_created).

        Example:
            result = graphaide.ingest_vectors(["doc1.pdf", "doc2.pdf"])
            print(f"Indexed {result.stats['chunks_created']} chunks")
        """
        # Handle log_level if provided
        log_level = kwargs.pop("log_level", None)
        if log_level:
            from graphgen.v2.utils import setup_logging
            setup_logging(log_level=log_level)

        if isinstance(file_paths, str):
            file_paths = [file_paths]

        return self.manager.run(
            "vectordb_ingest",
            {"file_paths": file_paths, **kwargs},
        )

    def ingest_jsonl(
        self,
        jsonl_path: str,
        field_name: str = "text",
        lines_per_batch: int = 4,
        ontology_path: str | None = None,
        use_jsonl_tracking: bool = True,
        **kwargs,
    ) -> WorkflowResult:
        """Ingest knowledge graphs from JSONL file in parallel batches.

        Convenience method for explicit JSONL ingestion.
        Reads JSONL file, extracts specified field from each line,
        processes in adaptive batches with parallel extraction workers.

        NOTE: You can also use .ingest(file_path="data.jsonl", ...) which
              automatically detects JSONL files and routes to this logic.

        Args:
            jsonl_path: Path to JSONL file (one JSON object per line)
            field_name: Field name to extract per line (default: "text")
            lines_per_batch: Lines per batch sent to each extractor (default: 4)
            ontology_path: Path to ontology for filtering (optional)
            use_jsonl_tracking: Create SourceDocument/ChunkParagraph nodes (default: True)
            **kwargs: Additional workflow parameters

        Returns:
            WorkflowResult with ingestion stats and failed_lines report.

        Example:
            # Explicit JSONL API
            result = graphaide.ingest_jsonl(
                jsonl_path="abstracts.jsonl",
                field_name="abstract",
                batch_size=500,
            )

            # OR use unified .ingest() API (auto-detects JSONL)
            result = graphaide.ingest(
                file_path="abstracts.jsonl",
                jsonl_field_name="abstract",
            )
        """
        logger.info(f"JSONL ingestion (explicit): {jsonl_path}")

        # Delegate to unified .ingest() method which auto-detects JSONL
        return self.ingest(
            file_path=jsonl_path,
            jsonl_field_name=field_name,
            jsonl_lines_per_batch=lines_per_batch,
            ontology_path=ontology_path,
            **kwargs,
        )

    def get_manager(self) -> WorkflowManager:
        """Access the internal WorkflowManager for advanced usage.

        Use this if you need direct control over workflow execution,
        e.g., to call workflows not exposed as convenience methods.

        Returns:
            Internal WorkflowManager instance.

        Example:
            manager = graphaide.get_manager()
            result = manager.run("kg_extract_merge", {...})
        """
        return self.manager
