#!/usr/bin/env python3
"""Test GraphAide with sample data - PNNL_About.pdf + business.nt ontology."""

from graphaide import GraphAide, ModelConfig, GraphDBConfig, get_sample_data_path
from graphgen.v2.utils import setup_logging

# Enable debug logging to see what's happening
setup_logging(log_level="DEBUG")

# Configure
model_config = ModelConfig(
    provider="openai",
    model_name="gpt-4o-mini",  # Use cheaper model for testing
    api_key=None,  # Will use OPENAI_API_KEY env var
)

graphdb_config = GraphDBConfig(
    uri="neo4j://localhost:7687",
    username="neo4j",
    password="password",
)

# Create GraphAide instance
graphaide = GraphAide(model_config=model_config, graphdb_config=graphdb_config)

# Get sample files
pdf_path = get_sample_data_path("PNNL_About.pdf")
ontology_path = get_sample_data_path("business.nt")

print(f"\n📄 Sample PDF: {pdf_path}")
print(f"📋 Ontology: {ontology_path}\n")

# Test 1: Extract to JSON (no database needed)
print("=" * 60)
print("TEST 1: Extract entities & relationships to JSON")
print("=" * 60)
try:
    result = graphaide.extract(
        file_path=str(pdf_path),
        ontology_path=str(ontology_path),
        max_tokens_per_segment=2048,
    )
    print(f"✓ Extracted {len(result.nodes)} nodes, {len(result.edges)} edges")

    # Show sample entities
    print("\nSample entities (first 5):")
    for node in result.nodes[:5]:
        print(f"  - {node.name} ({node.type})")

    # Show sample relationships
    print("\nSample relationships (first 5):")
    for edge in result.edges[:5]:
        print(f"  - {edge.source_name} -> {edge.target_name} ({edge.relationship})")

except Exception as e:
    print(f"✗ Extraction failed: {e}")
    print("\n💡 Make sure:")
    print("   - OPENAI_API_KEY is set in .env or environment")
    print("   - Your API key has sufficient quota")

# Test 2: Ingest to Neo4j (requires running Neo4j)
print("\n" + "=" * 60)
print("TEST 2: Extract + Load to Neo4j")
print("=" * 60)
print("(Requires Neo4j running at neo4j://localhost:7687)")
try:
    result = graphaide.ingest(
        file_path=str(pdf_path),
        ontology_path=str(ontology_path),
    )
    print(f"✓ Loaded to Neo4j: {result.message}")

    # Test 3: Query the graph
    print("\n" + "=" * 60)
    print("TEST 3: Query the Knowledge Graph")
    print("=" * 60)

    question = "What organizations are mentioned in the document?"
    print(f"Question: {question}\n")

    answer = graphaide.query(question=question)
    print(f"Answer:\n{answer.answer}")

except Exception as e:
    print(f"⚠ Neo4j test skipped: {e}")
    print("\n💡 To test Neo4j integration:")
    print("   docker run -d --name neo4j -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/password neo4j:latest")
    print("   # Then re-run this script")

print("\n" + "=" * 60)
print("✓ Tests complete!")
print("=" * 60)
