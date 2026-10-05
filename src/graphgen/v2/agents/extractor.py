import logging

import tiktoken
from pydantic import BaseModel, Field

from graphgen.v2 import globalconfig

from ..ontology_utils import build_enriched_ontology_context
from ..state import Edge, KGGenerationState, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.extractor")

# Fallback chunk sizes for retry logic
FALLBACK_CHUNK_SIZES = [4096, 2048, 1024]


def split_text_by_tokens(text: str, max_tokens: int) -> list[str]:
    """Split text into chunks of approximately max_tokens each.

    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk

    Returns:
        List of text chunks
    """
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(tokenizer.decode(chunk_tokens))

    return chunks


class ExtractorSchema(BaseModel):
    nodes: list[Node] = Field(
        default_factory=list, description="Extracted entity nodes"
    )
    edges: list[Edge] = Field(
        default_factory=list, description="Extracted relationships"
    )


class ExtractorToolSchema(BaseModel):
    """Input schema for ExtractorAgent tool.

    Note: RAG context (ontology types, Wikidata data, etc.) is read from shared state
    automatically. It does not need to be passed explicitly.
    """

    raw_text: str = Field(
        description="The text to extract entities and relationships from"
    )


class ExtractorAgent(GraphAideAgent):
    """Extract nodes and edges from raw text to build a knowledge graph.

    Takes raw text input and uses an LLM with structured output to identify
    entities (nodes) and relationships (edges) for knowledge graph construction.
    Uses vector store for context retrieval and supports ontology-guided extraction.

    Input state keys:
        raw_text (str): The text to extract entities and relationships from.
        rag_context (RAGContext, optional): Ontology types and external knowledge sources.
            - rag_context.ontology_node_types: Allowed node types from ontology
            - rag_context.ontology_edge_types: Allowed edge types from ontology
            - rag_context.wikidata_context: Wikidata entity metadata for grounding

    Output state keys:
        nodes (List[Node]): Extracted entity nodes with names, types, and Wikidata IDs.
        edges (List[Edge]): Extracted relationships between nodes.
        messages (List[str]): Status messages about extraction results.
    """

    tool_schema = ExtractorToolSchema
    tool_description = "Extract entities (nodes) and relationships (edges) from text. Ontology constraints are read automatically from state - ensure OntologyLoaderAgent has been called first to load the ontology."
    tool_output_keys = ["nodes", "edges", "messages"]

    def _extract_single_chunk(
        self, text: str, context: str, structured_llm, chain, callbacks=None
    ) -> tuple[list[Node], list[Edge]]:
        """Extract nodes and edges from a single text chunk.

        Args:
            text: Text to extract from
            context: Context string with ontology types and retrieved docs
            structured_llm: LLM with structured output
            chain: Prompt | LLM chain
            callbacks: Optional list of LangChain callbacks for tracing (e.g., LangFuse)

        Returns:
            Tuple of (nodes, edges)

        Raises:
            Exception if extraction fails
        """
        inputs = {
            "question": text,
            "context": context,
            **self.settings.get("partials", {}),
        }

        # Log model and provider info
        model_name = (
            self.model.model_name if hasattr(self.model, "model_name") else "unknown"
        )
        provider = self.model.provider if hasattr(self.model, "provider") else "unknown"
        logger.debug(f"Using LLM: {provider}/{model_name}")

        logger.debug(f"Invoking LLM with context ({len(context)} chars)")
        if context:
            context_preview = context[:300].replace("\n", " ")
            logger.debug(f"Context preview: {context_preview}...")

        # DEBUG: Log what's being sent to LLM - FULL DETAIL
        logger.debug(f"\n{'=' * 80}\nEXTRACTOR: FULL INPUT TO LLM:\n{'=' * 80}")
        logger.debug(f"Provider/Model: {provider}/{model_name}")
        logger.debug(f"\n>>> QUESTION/TEXT TO EXTRACT FROM ({len(text)} chars):")
        logger.debug(text)  # Full text
        logger.debug(f"\n>>> CONTEXT PASSED TO LLM ({len(context)} chars):")
        logger.debug(context)  # Full context
        # Debug: Print first 100 words of context for quick review
        if context:
            words = context.split()[:100]
            context_100_words = " ".join(words)
            logger.debug(f"\n>>> CONTEXT (first 100 words):\n{context_100_words}")
        logger.debug("\n>>> PROMPT TEMPLATE (if available):")
        if hasattr(self, "prompt"):
            logger.debug(f"Prompt: {self.prompt}")
        logger.debug(f"{'=' * 80}\n")

        config = {"callbacks": callbacks} if callbacks else {}
        result = chain.invoke(inputs, config=config)

        # DEBUG: Log what was received from LLM - FULL DETAIL
        logger.debug(f"\n{'=' * 80}\nEXTRACTOR: OUTPUT FROM LLM:\n{'=' * 80}")
        logger.debug(f"Raw result type: {type(result)}")
        logger.debug(
            f"Raw result keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}"
        )
        logger.debug(
            f"Nodes returned: {len(result.nodes) if hasattr(result, 'nodes') else 0}"
        )
        logger.debug(
            f"Edges returned: {len(result.edges) if hasattr(result, 'edges') else 0}"
        )

        if hasattr(result, "nodes") and result.nodes:
            logger.debug(f"\n>>> ALL NODES EXTRACTED ({len(result.nodes)} total):")
            for i, node in enumerate(result.nodes, 1):
                logger.debug(f"  [{i}] {node}")

        if hasattr(result, "edges") and result.edges:
            logger.debug(f"\n>>> ALL EDGES EXTRACTED ({len(result.edges)} total):")
            for i, edge in enumerate(result.edges, 1):
                logger.debug(f"  [{i}] {edge}")
        logger.debug(f"{'=' * 80}\n")

        extracted_nodes = [
            n if isinstance(n, Node) else Node(**n) for n in result.nodes
        ]
        extracted_edges = [
            e if isinstance(e, Edge) else Edge(**e) for e in result.edges
        ]
        return extracted_nodes, extracted_edges

    def _extract_with_fallback(
        self, text: str, context: str, structured_llm, chain, callbacks=None
    ) -> tuple[list[Node], list[Edge], list[str]]:
        """Extract with progressive chunk size reduction on failure.

        Tries extraction with original text first. If it fails, splits text
        into smaller chunks and retries. Uses FALLBACK_CHUNK_SIZES: [4096, 2048, 1024].

        Args:
            text: Text to extract from
            context: Context string
            structured_llm: LLM with structured output
            chain: Prompt | LLM chain

        Returns:
            Tuple of (nodes, edges, messages)
        """
        all_nodes = []
        all_edges = []
        messages = []

        # Try with original text first
        try:
            nodes, edges = self._extract_single_chunk(
                text, context, structured_llm, chain, callbacks
            )
            return nodes, edges, [f"Extracted {len(nodes)} nodes, {len(edges)} edges"]
        except Exception:
            pass

        # Progressive fallback with smaller chunk sizes
        last_error = None
        for chunk_size in FALLBACK_CHUNK_SIZES:
            chunks = split_text_by_tokens(text, chunk_size)

            # Skip if chunking doesn't help (same or more chunks than before)
            if len(chunks) <= 1 and chunk_size == FALLBACK_CHUNK_SIZES[0]:
                continue

            try:
                chunk_nodes = []
                chunk_edges = []
                logger.debug(
                    f"Processing {len(chunks)} chunks (chunk_size={chunk_size} tokens)"
                )
                for i, chunk in enumerate(chunks):
                    logger.debug(f"  Chunk {i + 1}/{len(chunks)}: {len(chunk)} chars")
                    nodes, edges = self._extract_single_chunk(
                        chunk, context, structured_llm, chain, callbacks
                    )
                    logger.debug(
                        f"    → {len(nodes)} nodes, {len(edges)} edges extracted"
                    )
                    chunk_nodes.extend(nodes)
                    chunk_edges.extend(edges)

                messages.append(
                    f"Extracted with {chunk_size}-token chunks: "
                    f"{len(chunk_nodes)} nodes, {len(chunk_edges)} edges from {len(chunks)} chunks"
                )
                return chunk_nodes, chunk_edges, messages

            except Exception as e:
                last_error = e
                logger.debug(f"{chunk_size}-token chunks failed ({e}), trying smaller")
                continue

        # All attempts failed
        raise RuntimeError(
            f"Extraction failed with all chunk sizes {FALLBACK_CHUNK_SIZES}. "
            f"Last error: {last_error}"
        )

    def __call__(self, state: KGGenerationState) -> dict:
        from graphgen.v2.state import RetrievalResultType
        from graphgen.v2.workflows.retriever_factory import make_vectorstore_retriever
        from graphgen.v2 import globalconfig

        # Log vector store path on startup
        logger.info(f"Vector store path: {globalconfig.VECTOR_STORE_BASEDIR}")

        # DEBUG: Log what we received at the start
        logger.debug(
            f"ExtractorAgent.__call__: State keys present: {list(state.keys())}"
        )

        # 1. Run dynamic retrievers if vector_store_configs are present
        vector_store_configs = state.get("vector_store_configs", [])
        logger.debug(
            f"ExtractorAgent: vector_store_configs from state = {vector_store_configs}"
        )
        logger.debug(
            f"ExtractorAgent: vector_store_configs type = {type(vector_store_configs)}, len = {len(vector_store_configs) if vector_store_configs else 0}"
        )
        # Get embeddings for all retrieval scenarios (both multi-retriever and fallback)
        embeddings = (
            self.model.model.embedding_function
            if hasattr(self.model, "model")
            else None
        )
        logger.debug(
            f"ExtractorAgent: embeddings from model = {type(embeddings).__name__ if embeddings else None}"
        )

        # If we don't have embeddings from model, get from agent factory
        if not embeddings:
            logger.debug(
                "ExtractorAgent: No embeddings from model, getting from factory..."
            )
            from graphgen.v2.ModelManager import ModelFactory
            from graphgen.v2.workflows.base import WorkflowConfig
            from graphgen.v2.workflows.utils import get_agent_factory

            # If we have model_config in settings, create ModelFactory directly with it
            # This preserves user's explicit embedding_model_name instead of falling back to Bedrock
            if self.settings and self.settings.get("model_config"):
                model_config = self.settings["model_config"]
                model_factory = ModelFactory(model_config=model_config)
                embeddings = model_factory.get_embeddings(
                    provider=model_config.provider
                )
            else:
                # Fallback: create from workflow config
                workflow_config = WorkflowConfig()
                agent_factory = get_agent_factory(workflow_config)
                embeddings = agent_factory.model_factory.get_embeddings()

        if vector_store_configs:
            # Run each configured retriever
            logger.info(f"Multi-retrieval: {len(vector_store_configs)} retriever(s)")
            all_retrieval_results = []

            for config in vector_store_configs:
                try:
                    retriever_func = make_vectorstore_retriever(config, embeddings)
                    result_dict = retriever_func(state)
                    if "retrieval_results" in result_dict:
                        results = result_dict["retrieval_results"]
                        all_retrieval_results.extend(results)
                        logger.info(
                            f"✓ {len(results)} result(s) from {config.collection_name}"
                        )
                    else:
                        logger.warning(f"✗ No results from {config.collection_name}")
                except Exception as e:
                    logger.error(
                        f"Retriever {config.retrieve_type} failed: {e}", exc_info=True
                    )

            # Get or create rag_context (from OntologyLoader or build new)
            rag_context = state.get("rag_context")
            if not rag_context:
                from graphgen.v2.state import RAGContext

                rag_context = RAGContext(
                    ontology_node_types=[],
                    ontology_edge_types=[],
                    retrieval_results=[],
                )

            # Safety: ensure retrieval_results is a list
            if rag_context.retrieval_results is None:
                rag_context.retrieval_results = []

            # Add retriever results to rag_context
            rag_context.retrieval_results.extend(all_retrieval_results)
            state["rag_context"] = rag_context

            # Summary log
            if all_retrieval_results:
                by_type = {}
                for result in all_retrieval_results:
                    rtype = (
                        result.result_type.value
                        if hasattr(result.result_type, "value")
                        else str(result.result_type)
                    )
                    by_type[rtype] = by_type.get(rtype, 0) + 1
                logger.info(
                    f"✓ {len(all_retrieval_results)} total: {', '.join([f'{c} {t}' for t, c in by_type.items()])}"
                )

        # 2. Build context from RAGContext and retrieval_results
        context = "\n"
        rag_context = state.get("rag_context")
        logger.debug(
            f"ExtractorAgent: Building context, rag_context present? {rag_context is not None}"
        )

        # Add ontology types from RAGContext (handle None safely)
        node_types = (rag_context.ontology_node_types if rag_context else None) or []
        edge_types = (rag_context.ontology_edge_types if rag_context else None) or []
        logger.debug(
            f"  From rag_context: {len(node_types)} node types, {len(edge_types)} edge types"
        )

        # Process retrieval_results (extract ontology types and add to context)
        retrieval_results = (rag_context.retrieval_results if rag_context else None) or []
        logger.debug(f"  retrieval_results from rag_context: {len(retrieval_results)} items")

        # Extract ontology types from TYPES results
        for result in retrieval_results:
            if result.result_type == RetrievalResultType.TYPES:
                if result.ontology_node_types:
                    node_types.extend(result.ontology_node_types)
                if result.ontology_edge_types:
                    edge_types.extend(result.ontology_edge_types)

        # Remove duplicates
        node_types = list(set(node_types))
        edge_types = list(set(edge_types))

        if node_types and edge_types:
            logger.info(
                f"Ontology - {len(node_types)} node types, {len(edge_types)} edge types"
            )
            logger.debug(f"Node types: {node_types}")
            logger.debug(f"Edge types: {edge_types}")

            # Use enriched context with definitions and examples if available
            if rag_context:
                enriched_context = build_enriched_ontology_context(rag_context)
                context += enriched_context
                logger.debug(
                    "Using enriched ontology context with definitions and examples"
                )
            else:
                # Fallback to simple context if no RAGContext
                context += f"Ontology Node Types: {', '.join(node_types)}\n"
                context += f"Ontology Edge Types: {', '.join(edge_types)}\n"
                context += "Make sure to assign node types and edge types from the list above.\n"

        # Add entities and documents to context
        for result in retrieval_results:
            logger.debug(f"Processing result: type={result.result_type}, has_wikidata={bool(result.wikidata_context)}, has_docs={bool(result.documents)}")

            if result.store_description:
                context += (
                    f"\n[Vector Store: {result.source}]\n{result.store_description}\n"
                )

            # Use description to infer actual data type if provided (e.g., "ontology types in QID format")
            actual_type = result.result_type

            if actual_type == RetrievalResultType.ENTITIES:
                if result.wikidata_context:
                    for qid, entity_data in result.wikidata_context.items():
                        label = entity_data.get("label", "")
                        context += f"QID={qid} Label={label}\n"

            elif actual_type == RetrievalResultType.DOCUMENTS:
                if result.documents:
                    context += f"# Context from {result.source}:\n"
                    for j, doc_text in enumerate(result.documents[:2], 1):
                        context += f"[Doc {j}] {doc_text[:200]}...\n"

            elif actual_type == RetrievalResultType.CUSTOM:
                if result.custom_data:
                    context += f"# {result.source}:\n{result.custom_data}\n"

        logger.info(f"Context ready ({len(context)} chars)")
        logger.debug(f"ExtractorAgent: Full Context = {context}")

        # 4. Fallback: if no retrieval results, use single default store
        if not retrieval_results:
            logger.warning("No retrieval results, falling back to default vector store")
            vector_store = self.settings.get("vector_store")
            if not vector_store:
                raise ValueError(
                    f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
                )
            # Log vector store path for debugging
            from graphgen.v2 import globalconfig
            store_path = globalconfig.VECTOR_STORE_BASEDIR / "GA_VDB"
            logger.info(f"Vector store path: {store_path}")

            query = state.get("raw_text", "")

            # Ensure query is a string
            if isinstance(query, list):
                query = " ".join(str(q) for q in query)
            elif not isinstance(query, str):
                query = str(query)

            # Verify query is string before similarity search
            if not isinstance(query, str):
                logger.error(
                    f"query is {type(query)}, not string. Value: {repr(query)[:200]}"
                )
                query = str(query)

            # Skip search if query is empty
            if not query or query.isspace():
                logger.info("ExtractorAgent: skipping similarity search (empty query)")
                docs = []
            else:
                try:
                    docs = vector_store.similarity_search(
                        query, k=globalconfig.DEFAULT_K
                    )
                except Exception as e:
                    logger.error(f"Similarity search failed: {e}")
                    logger.debug(
                        f"Query type: {type(query)}, value: {repr(query)[:200]}"
                    )
                    docs = []

            for doc in docs:
                meta_val = doc.metadata.get(
                    "source", doc.metadata.get("id", doc.metadata.get("title", ""))
                )
                if "|" in meta_val:
                    qid_label = meta_val.split("|")
                    if len(qid_label) >= 2:
                        context += f"QID={qid_label[0]} Label={qid_label[1]}\n"

        # 3. Setup LLM chain
        structured_llm = self.model.with_structured_output(ExtractorSchema)
        chain = self.prompt | structured_llm

        # 4. Extract with fallback retry logic
        # Get LangFuse callback if available to pass through chain invocations
        callbacks = []
        if self._langfuse_client:
            callbacks.append(self._langfuse_client)
            logger.info(f"✓ [ExtractorAgent] Using LangFuse callback for tracing: {type(self._langfuse_client).__name__}")
            logger.debug(f"  Callback: {self._langfuse_client}")
        else:
            logger.info(f"⚠️  [ExtractorAgent] LangFuse callback not available - no tracing will be recorded")
        callbacks.append(self._debug_callback)
        logger.info(f"✓ [ExtractorAgent] Debug callback added for event verification")
        try:
            extracted_nodes, extracted_edges, messages = self._extract_with_fallback(
                text=state.get("raw_text", ""),
                context=context,
                structured_llm=structured_llm,
                chain=chain,
                callbacks=callbacks,
            )
            logger.info(messages[-1])

            # Show extracted types for debugging
            extracted_node_types = list(
                set(n.node_type for n in extracted_nodes if n.node_type)
            )
            extracted_edge_types = list(
                set(e.edge_type for e in extracted_edges if e.edge_type)
            )
            logger.debug(f"Extracted node types: {extracted_node_types}")
            logger.debug(f"Extracted edge types: {extracted_edge_types}")

            # Enhanced DEBUG: Show detailed extraction results
            logger.debug(f"\n{'=' * 60}\nEXTRACTION SUMMARY:\n{'=' * 60}")
            logger.debug(f"Total nodes extracted: {len(extracted_nodes)}")
            for node_type in extracted_node_types:
                count = sum(1 for n in extracted_nodes if n.node_type == node_type)
                logger.debug(f"  - {node_type}: {count} nodes")
            logger.debug(f"\nTotal edges extracted: {len(extracted_edges)}")
            for edge_type in extracted_edge_types:
                count = sum(1 for e in extracted_edges if e.edge_type == edge_type)
                logger.debug(f"  - {edge_type}: {count} edges")
            logger.debug(f"{'=' * 60}\n")

            # Save pre-filtered graph before ontology filtering
            pre_filtered_nodes = extracted_nodes.copy()
            pre_filtered_edges = extracted_edges.copy()
            filter_stats = {}

            # Check if filtering is enabled (default: True)
            filter_by_ontology = state.get("filter_by_ontology", False)
            logger.debug(
                f"filter_by_ontology from state: {filter_by_ontology} (type: {type(filter_by_ontology)})"
            )

            # Filter nodes and edges to ontology types if ontology is provided AND filtering is enabled
            if filter_by_ontology and (node_types or edge_types):
                logger.debug(
                    f"Applying ontology filter (filter_by_ontology={filter_by_ontology}, has_ontology={bool(node_types or edge_types)})"
                )
                filtered_nodes = (
                    [n for n in extracted_nodes if n.node_type in node_types]
                    if node_types
                    else extracted_nodes
                )
                filtered_edges = (
                    [e for e in extracted_edges if e.edge_type in edge_types]
                    if edge_types
                    else extracted_edges
                )
                skipped_nodes = len(extracted_nodes) - len(filtered_nodes)
                skipped_edges = len(extracted_edges) - len(filtered_edges)
                if skipped_nodes or skipped_edges:
                    logger.info(
                        f"Filtered out {skipped_nodes} nodes, {skipped_edges} edges not in ontology"
                    )
                    # Show which node types were filtered out
                    allowed_node_set = set(node_types) if node_types else set()
                    rejected_node_types = set()
                    for n in pre_filtered_nodes:
                        if n.node_type and n.node_type not in allowed_node_set:
                            rejected_node_types.add(n.node_type)
                    if rejected_node_types:
                        logger.debug(
                            f"Rejected node types: {list(rejected_node_types)}"
                        )

                    # Show which edge types were filtered out
                    allowed_edge_set = set(edge_types) if edge_types else set()
                    rejected_edge_types = set()
                    for e in pre_filtered_edges:
                        if e.edge_type and e.edge_type not in allowed_edge_set:
                            rejected_edge_types.add(e.edge_type)
                    if rejected_edge_types:
                        logger.debug(
                            f"Rejected edge types: {list(rejected_edge_types)}"
                        )
                    filter_stats = {
                        "filtered_nodes": skipped_nodes,
                        "filtered_edges": skipped_edges,
                        "nodes_before": len(pre_filtered_nodes),
                        "edges_before": len(pre_filtered_edges),
                        "nodes_after": len(filtered_nodes),
                        "edges_after": len(filtered_edges),
                    }
                extracted_nodes = filtered_nodes
                extracted_edges = filtered_edges

                # Save pre-filtered graph with "PreFilter" prefix
                try:
                    import json
                    from datetime import datetime

                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    pre_filter_filename = (
                        f"GraphAide_KG_Extract_PreFilter_{timestamp}.json"
                    )

                    # Convert to dict for JSON serialization
                    pre_nodes_data = []
                    for n in pre_filtered_nodes:
                        node_dict = (
                            n.model_dump() if hasattr(n, "model_dump") else dict(n)
                        )
                        if "grounding_id" in node_dict:
                            node_dict["node_id"] = node_dict.pop("grounding_id")
                        pre_nodes_data.append(node_dict)

                    pre_edges_data = []
                    for e in pre_filtered_edges:
                        edge_dict = (
                            e.model_dump() if hasattr(e, "model_dump") else dict(e)
                        )
                        if "source_node_english_name" in edge_dict:
                            edge_dict["source_id"] = edge_dict.pop(
                                "source_node_english_name"
                            )
                        if "target_node_english_name" in edge_dict:
                            edge_dict["target_id"] = edge_dict.pop(
                                "target_node_english_name"
                            )
                        pre_edges_data.append(edge_dict)

                    pre_filter_data = {
                        "source_file": state.get("file_path", ""),
                        "extraction_stage": "pre_filter",
                        "nodes_before_filter": len(pre_filtered_nodes),
                        "edges_before_filter": len(pre_filtered_edges),
                        "nodes_after_filter": len(extracted_nodes),
                        "edges_after_filter": len(extracted_edges),
                        "filtered_out_nodes": skipped_nodes,
                        "filtered_out_edges": skipped_edges,
                        "nodes": pre_nodes_data,
                        "edges": pre_edges_data,
                    }

                    with open(pre_filter_filename, "w", encoding="utf-8") as f:
                        json.dump(pre_filter_data, f, indent=2, ensure_ascii=False)
                    logger.debug(f"Pre-filtered graph saved to: {pre_filter_filename}")
                except Exception as e:
                    logger.error(f"Failed to save pre-filtered graph: {e}")

            return {
                "nodes": extracted_nodes,
                "edges": extracted_edges,
                "messages": messages,
                "filter_stats": filter_stats,
                "agent_status": {self.__class__.__name__: True},
            }
        except Exception as e:
            logger.error(f"All extraction attempts failed: {e}")
            # Final fallback: try unstructured output
            try:
                chain = self.prompt | self.model
                inputs = {
                    "question": state.get("raw_text", ""),
                    "context": context,
                    **self.settings.get("partials", {}),
                }
                config = {"callbacks": callbacks}
                logger.debug(f"🔍 [ExtractorChain] Invoking with {len(callbacks)} callbacks")
                response = chain.invoke(inputs, config=config)
                json_response = (
                    response.content if hasattr(response, "content") else response
                )
                logger.warning("Final fallback to unstructured output")
                return {
                    "unstructured_response": [json_response],
                    "messages": [
                        "Fallback: extracted unstructured response after chunk retries failed"
                    ],
                    "nodes": [Node()],
                    "edges": [Edge()],
                    "agent_status": {self.__class__.__name__: True},
                }
            except Exception as inner_e:
                logger.error(f"Final fallback failed: {inner_e}")
                return {
                    "messages": [
                        f"All extraction attempts failed. Error: {e!s}, Fallback error: {inner_e!s}"
                    ],
                    "nodes": [Node()],
                    "edges": [Edge()],
                    "agent_status": {self.__class__.__name__: False},
                }
