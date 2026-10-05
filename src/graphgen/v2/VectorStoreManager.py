import importlib
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_chroma import Chroma
from pydantic import BaseModel, Field

import graphgen.v2.globalconfig as globalconfig
from graphgen.v2.ModelManager import ModelFactory

logger = logging.getLogger("graphgen.v2.VectorStoreManager")


class IngestType(str, Enum):
    """Types of data to ingest into a vector store.

    Used during vector store ingestion to determine how to parse input files
    and what metadata/structure to assign to indexed documents.
    """
    ONTOLOGY = "ontology"      # Ontology types, definitions, node/edge specifications
    ENTITIES = "entities"      # Wikidata entity info, QIDs, entity labels
    DOCUMENTS = "documents"    # Raw document chunks, text paragraphs, raw content
    CUSTOM = "custom"          # Custom application-specific data


class RetrieveType(str, Enum):
    """Types of data to retrieve from a vector store.

    Used during extraction to determine how to process retrieved results
    and what context to pass to the LLM.
    """
    ONTOLOGY = "ontology"      # Extract node/edge types for guided extraction
    ENTITIES = "entities"      # Extract Wikidata mappings for entity grounding
    DOCUMENTS = "documents"    # Extract raw document chunks for RAG context
    CUSTOM = "custom"          # Custom application-specific data


class VectorDBConfig(BaseModel):
    provider: str = Field(default_factory=lambda: os.getenv("VECTOR_STORE_PROVIDER", "chromadb"))
    store_name: str = Field(default_factory=lambda: os.getenv("VECTOR_STORE_NAME", "GA_VDB"))
    store_path: Optional[str] = globalconfig.VECTOR_STORE_BASEDIR
    collection_name: Optional[str] = None  # Collection name within the store (None uses Chroma default)
    ingest_type: IngestType = Field(
        default=IngestType.DOCUMENTS,
        description="How to parse and ingest data into this store: ontology, entities, documents, or custom"
    )
    retrieve_type: RetrieveType = Field(
        default=RetrieveType.DOCUMENTS,
        description="How to process retrieved data from this store: ontology, entities, documents, or custom"
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable description of this vector store (e.g., 'Wikidata entity context'). Passed to LLM context to explain the data source."
    )


class VectorFactory:
    def __init__(self, model_factory, vectordb_config: Optional[VectorDBConfig] = None):
        # init looks different from GraphDBFactory becuase it is not read from a config section but part of models. TODO: streamline this.
        self.model_factory: ModelFactory = model_factory
        self._vectordb_configs: Dict[str, VectorDBConfig] = {}
        self._vectordb_objects: Dict[str, Any] = {}
        if vectordb_config:
            logger.info(f"VectorFactory: using runtime config [{vectordb_config.provider}]")
            VDB_STORE_KEY = f"{vectordb_config.provider}_{vectordb_config.store_name}"
            self._vectordb_configs[VDB_STORE_KEY] = vectordb_config
        # default values if no config provided at init, we can override them at runtime when we call get_store() with a specific config if needed.
        else:
            self._vectordb_configs["chromadb"] = VectorDBConfig()

    def get_store(
        self,
        vectordb_config: Optional[VectorDBConfig] = None,
    ) -> Any:
        """
        Retrieves or creates a specific vector store (chromadb or Qdrant).
        :param vectordb_config: Configuration for the vector store

        Priority: explicit vectordb_config > env vars > defaults
        """
        importlib.reload(
            globalconfig
        )  # Ensure we have the latest env vars if they were updated at runtime

        if vectordb_config is None:
            vectordb_config = next(iter(self._vectordb_configs.values()), None)

            # Only use env vars as fallback if no config was provided
            if vectordb_config is None:
                runtime_store_name = os.getenv("VECTOR_STORE_NAME", "GA_VDB")
                runtime_provider = os.getenv("VECTOR_STORE_PROVIDER", "chromadb")
                vectordb_config = VectorDBConfig(
                    provider=runtime_provider,
                    store_name=runtime_store_name,
                )
        # If explicit config provided, use it as-is (no env var override)

        VDB_STORE_KEY = f"{vectordb_config.provider}_{vectordb_config.store_name}"
        if VDB_STORE_KEY in self._vectordb_objects:
            return self._vectordb_objects[VDB_STORE_KEY]
        else:
            self._vectordb_configs[VDB_STORE_KEY] = vectordb_config
            path_obj = (
                Path(vectordb_config.store_path).expanduser()
                / vectordb_config.store_name
            )
            # Ensure the base directory exists
            if not path_obj.exists():
                logger.info(f"Creating vector store: {path_obj}")

            if vectordb_config.provider.lower() == "chromadb":
                # Only pass collection_name if explicitly set; None breaks Chroma
                chroma_kwargs = {
                    "persist_directory": path_obj,
                    "embedding_function": self.model_factory.get_embeddings(),
                }
                if vectordb_config.collection_name is not None:
                    chroma_kwargs["collection_name"] = vectordb_config.collection_name

                self._vectordb_objects[VDB_STORE_KEY] = Chroma(**chroma_kwargs)
                logger.info(f"VectorStore ready: {vectordb_config.store_name} [{self._vectordb_objects[VDB_STORE_KEY]._collection.count()} vectors]")
            elif vectordb_config.provider.lower() == "qdrant":
                self._vectordb_objects[VDB_STORE_KEY] = self._create_qdrant_store(
                    vectordb_config, path_obj
                )
                logger.info(f"VectorStore ready (Qdrant): {vectordb_config.store_name}")
            else:
                raise ValueError(
                    f"Unsupported vector database provider '{vectordb_config.provider}'. Supported providers: 'chromadb', 'Qdrant'."
                )

            return self._vectordb_objects[VDB_STORE_KEY]

    def _create_qdrant_store(self, vectordb_config: VectorDBConfig, path_obj: Path) -> Any:
        """
        Creates a Qdrant vector store wrapper compatible with LangChain.
        :param vectordb_config: Vector store configuration
        :param path_obj: Path to store data
        :return: Qdrant wrapper instance
        """
        try:
            from langchain_qdrant import QdrantVectorStore
            from qdrant_client import QdrantClient
        except ImportError:
            raise ImportError(
                "qdrant-client and langchain-qdrant are required for Qdrant support. "
                "Install with: pip install qdrant-client>=2.7.0"
            )

        # Create Qdrant client with local file storage
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(path_obj))

        # Get embedding dimension from model
        embeddings = self.model_factory.get_embeddings()

        # Check if collection exists first (avoid embedding test for existing collections)
        collection_name = vectordb_config.store_name.replace("-", "_").replace(".", "_")
        collection_exists = False
        try:
            client.get_collection(collection_name)
            collection_exists = True
            # Get embedding_dim from existing collection
            collection_info = client.get_collection(collection_name)
            embedding_dim = collection_info.config.vectors.size
        except Exception:
            # Collection doesn't exist, need to get embedding_dim via test
            embedding_dim = len(embeddings.embed_query("test"))

        if not collection_exists:
            from qdrant_client.models import Distance, VectorParams
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
            )

        # Return LangChain-compatible wrapper
        return QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )
