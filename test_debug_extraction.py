#!/usr/bin/env python
"""Test script to debug extractor with vector stores."""

from graphaide import GraphAide, ModelConfig, GraphDBConfig, VectorDBConfig, IngestType, RetrieveType
from graphgen.v2.utils import setup_logging

# Enable DEBUG logging to see all debug statements
setup_logging(log_level="DEBUG")

# Create configs
model_config = ModelConfig(provider="openai", model_name="gpt-4o")
graphdb_config = GraphDBConfig(
    uri="neo4j://localhost:7687",
    username="neo4j",
    password="neo4jpwd",
    provider="neo4j",
)

# Create a vector config
vector_config = VectorDBConfig(
    provider="chromadb",
    store_name="test_entities",
    store_path="C:\\Users\\puro755\\.vectorstores_graphaide",
    ingest_type=IngestType.ENTITIES,
    retrieve_type=RetrieveType.ENTITIES,
)

print("\n" + "="*80)
print("TEST: Extracting from text with multi-retriever vector store")
print("="*80 + "\n")

# Initialize GraphAide with vector config
graphaide = GraphAide(
    model_config=model_config,
    graphdb_config=graphdb_config,
    vector_configs=[vector_config]
)

# Extract from simple text to see debug output
result = graphaide.extract(
    input_text="Hypersonics are advanced military technologies. They are very fast weapons.",
    filter_by_ontology=False,
)

print("\n" + "="*80)
print("RESULT")
print("="*80)
print(f"Nodes: {len(result.nodes)}")
print(f"Edges: {len(result.edges)}")
print("\nCheck the debug output above to see:")
print("  - vector_store_configs being received")
print("  - Multi-retriever execution")
print("  - Retrieval results being collected")
print("  - Context being built")
