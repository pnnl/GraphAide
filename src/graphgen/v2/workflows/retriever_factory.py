"""Factory functions for creating retriever nodes from vector store configs."""

import logging
from collections.abc import Callable

from graphgen.v2 import globalconfig
from graphgen.v2.state import KGGenerationState, RetrievalResult, RetrievalResultType
from graphgen.v2.workflows.schemas import VectorStoreConfig

logger = logging.getLogger("graphgen.retriever")


def make_vectorstore_retriever(
    vector_store_config: VectorStoreConfig, embeddings_func
) -> Callable[[KGGenerationState], dict]:
    """Factory: creates a retriever function node from vector store config.

    Returns a callable that LangGraph can add as a node. The function queries
    a vector store and returns standardized RetrievalResult objects.

    Args:
        vector_store_config: Configuration for the vector store (type, path, collection_name, retrieve_type)
        embeddings_func: Embeddings function from ModelFactory

    Returns:
        A function that takes KGGenerationState and returns dict with retrieval_results
    """

    def retriever_node(state: KGGenerationState) -> dict:
        """Retriever node: queries vector store and returns structured results."""

        # Initialize vector store from config - direct creation with provided embeddings_func
        # This ensures we use the same embeddings that were used during indexing
        if vector_store_config.type.lower() == "chromadb":
            from pathlib import Path

            from langchain_chroma import Chroma

            # Expand path (e.g., ~/ → /home/user/)
            expanded_path = str(Path(vector_store_config.path).expanduser())

            logger.debug(f"Retriever: Creating Chroma instance for {vector_store_config.collection_name}")
            logger.debug(f"  Path: {expanded_path}")
            logger.debug(f"  Collection: {vector_store_config.collection_name}")
            logger.debug(f"  Embeddings: {type(embeddings_func).__name__}")

            # Only pass collection_name if explicitly set; None breaks Chroma
            chroma_kwargs = {
                "persist_directory": expanded_path,
                "embedding_function": embeddings_func,
            }
            if vector_store_config.collection_name is not None:
                chroma_kwargs["collection_name"] = vector_store_config.collection_name

            vector_store = Chroma(**chroma_kwargs)
            logger.debug(f"  Store ready: {vector_store._collection.count()} vectors in collection")
        elif vector_store_config.type.lower() == "qdrant":
            from langchain_qdrant import QdrantVectorStore

            vector_store = QdrantVectorStore.from_url(
                url=vector_store_config.url,
                collection_name=vector_store_config.collection_name or "documents",
                embedding=embeddings_func,
            )
        else:
            raise ValueError(
                f"Unsupported vector store type: {vector_store_config.type}"
            )

        # Query with segment text
        query = state.get("raw_text", "")
        if not query or not isinstance(query, str):
            query = str(query) if query else ""

        if not query.strip():
            logger.debug(
                f"Retriever {vector_store_config.retrieve_type}: empty query, skipping"
            )
            return {
                "retrieval_results": [],
                "messages": [
                    f"Skipped {vector_store_config.retrieve_type} (empty query)"
                ],
            }

        try:
            # Key similarity search using the vector store
            docs = vector_store.similarity_search(query, k=globalconfig.DEFAULT_K)
            logger.debug(
                f"Retrieved {len(docs)} docs from {vector_store_config.collection_name} (retrieve_type={vector_store_config.retrieve_type})"
            )
        except Exception as e:
            logger.error(
                f"Retriever {vector_store_config.retrieve_type} failed: {e}",
                exc_info=True,
            )
            return {
                "retrieval_results": [],
                "messages": [
                    f"Retriever {vector_store_config.retrieve_type} failed: {e}"
                ],
            }

        if not docs:
            logger.warning(
                f"No documents found from {vector_store_config.collection_name} for query: {query[:100]}..."
            )
            return {
                "retrieval_results": [],
                "messages": [
                    f"No documents found from {vector_store_config.collection_name}"
                ],
            }

        retrieve_type = vector_store_config.retrieve_type

        # Extract based on retrieve_type
        if retrieve_type == "entities":
            wikidata_context = {}
            logger.debug(f"Retriever: Processing {len(docs)} entity docs")
            for i, doc in enumerate(docs):
                # Try two formats: "QID|Label" (combined) or separate id + label fields
                meta_val = doc.metadata.get("id", "") or doc.metadata.get("source", "")
                qid = None
                label = None

                # Format 1: "QID|Label" pipe-separated
                if "|" in meta_val:
                    qid_label = meta_val.split("|")
                    if len(qid_label) >= 2:
                        qid, label = qid_label[0], qid_label[1]
                # Format 2: Separate id/qid and label fields
                elif meta_val and not meta_val.startswith("Q"):  # meta_val is source, not QID
                    qid = doc.metadata.get("qid") or doc.metadata.get("id")
                    label = doc.metadata.get("label")
                else:  # meta_val is the QID
                    qid = meta_val
                    label = doc.metadata.get("label")

                if qid and label:
                    wikidata_context[qid] = {"label": label}
                    logger.debug(f"  Doc {i}: ✓ QID={qid}, Label={label}")
                else:
                    logger.debug(f"  Doc {i}: ✗ Missing QID or label (qid={qid}, label={label})")

            result = RetrievalResult(
                source=f"vectorstore_{retrieve_type}",
                result_type=RetrievalResultType.ENTITIES,
                store_description=vector_store_config.description,
                wikidata_context=wikidata_context,
            )

        elif retrieve_type == "ontology":
            # Query with metadata filters to get top-k node types and top-k edge types separately
            ontology_node_types = []
            ontology_edge_types = []

            # For ChromaDB, use the underlying collection to filter by metadata
            if hasattr(vector_store, "_collection"):
                collection = vector_store._collection

                # Search for node types with where filter
                try:
                    node_results = collection.query(
                        query_embeddings=None,
                        query_texts=[query],
                        n_results=globalconfig.DEFAULT_K,
                        where={"type": "node_type"},
                    )
                    if node_results and node_results.get("ids"):
                        for doc_ids, metadatas in zip(
                            node_results.get("ids", []),
                            node_results.get("metadatas", []),
                        ):
                            for metadata in metadatas:
                                type_id = metadata.get("id", "")
                                if type_id:
                                    ontology_node_types.append(type_id)
                except Exception:
                    # Fallback: get more results and filter
                    all_docs = vector_store.similarity_search(
                        query, k=globalconfig.DEFAULT_K * 3
                    )
                    for doc in all_docs:
                        if doc.metadata.get("type") == "node_type":
                            type_id = doc.metadata.get("id", "")
                            if type_id:
                                ontology_node_types.append(type_id)
                    ontology_node_types = ontology_node_types[: globalconfig.DEFAULT_K]

                # Search for edge types with where filter
                try:
                    edge_results = collection.query(
                        query_embeddings=None,
                        query_texts=[query],
                        n_results=globalconfig.DEFAULT_K,
                        where={"type": "edge_type"},
                    )
                    if edge_results and edge_results.get("ids"):
                        for doc_ids, metadatas in zip(
                            edge_results.get("ids", []),
                            edge_results.get("metadatas", []),
                        ):
                            for metadata in metadatas:
                                type_id = metadata.get("id", "")
                                if type_id:
                                    ontology_edge_types.append(type_id)
                except Exception:
                    # Fallback: get more results and filter
                    all_docs = vector_store.similarity_search(
                        query, k=globalconfig.DEFAULT_K * 3
                    )
                    for doc in all_docs:
                        if doc.metadata.get("type") == "edge_type":
                            type_id = doc.metadata.get("id", "")
                            if type_id:
                                ontology_edge_types.append(type_id)
                    ontology_edge_types = ontology_edge_types[: globalconfig.DEFAULT_K]
            else:
                # Fallback for non-ChromaDB stores
                all_docs = vector_store.similarity_search(
                    query, k=globalconfig.DEFAULT_K * 3
                )
                for doc in all_docs:
                    if doc.metadata.get("type") == "node_type":
                        type_id = doc.metadata.get("id", "")
                        if type_id and type_id not in ontology_node_types:
                            ontology_node_types.append(type_id)
                            if len(ontology_node_types) >= globalconfig.DEFAULT_K:
                                break
                for doc in all_docs:
                    if doc.metadata.get("type") == "edge_type":
                        type_id = doc.metadata.get("id", "")
                        if type_id and type_id not in ontology_edge_types:
                            ontology_edge_types.append(type_id)
                            if len(ontology_edge_types) >= globalconfig.DEFAULT_K:
                                break

            result = RetrievalResult(
                source=f"vectorstore_{retrieve_type}",
                result_type=RetrievalResultType.TYPES,
                store_description=vector_store_config.description,
                ontology_node_types=list(set(ontology_node_types)),  # deduplicate
                ontology_edge_types=list(set(ontology_edge_types)),  # deduplicate
            )

        elif retrieve_type == "documents":
            documents = [doc.page_content for doc in docs]
            result = RetrievalResult(
                source=f"vectorstore_{retrieve_type}",
                result_type=RetrievalResultType.DOCUMENTS,
                store_description=vector_store_config.description,
                documents=documents,
            )

        else:
            # Custom retriever type
            result = RetrievalResult(
                source=f"vectorstore_{retrieve_type}",
                result_type=RetrievalResultType.CUSTOM,
                store_description=vector_store_config.description,
                custom_data={"docs": [doc.page_content for doc in docs]},
            )

        return {
            "retrieval_results": [result],
            "messages": [
                f"Retrieved from {vector_store_config.path} ({retrieve_type}): {len(docs)} docs"
            ],
        }

    return retriever_node
