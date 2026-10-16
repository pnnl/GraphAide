# Ingesting Knowledge Graphs to Neo4j

Learn how to load extracted data into Neo4j for querying and analysis.

## What is Ingestion?

Ingestion is the process of taking extracted entities and relationships and loading them into a Neo4j graph database, where you can query and analyze them.

## Quick Start: Ingest to Neo4j

### Configure Neo4j Connection

First, set up your Neo4j database configuration:

```python
from graphaide import GraphDBConfig

graphdb_config = GraphDBConfig(
    uri="neo4j://localhost:7687",      # Neo4j server address
    username="neo4j",                   # Neo4j username
    password="password"                 # Neo4j password
)
```

### Initialize GraphAide with Neo4j

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig

# Setup LLM
model_config = ModelConfig(
    provider="openai",
    model_name="gpt-5.6-luna",
    api_key="..."
)

# Setup Neo4j
graphdb_config = GraphDBConfig(
    uri="neo4j://localhost:7687",
    username="neo4j",
    password="password"
)

# Initialize GraphAide with both configs
graphaide = GraphAide(
    model_config=model_config,
    graphdb_config=graphdb_config
)

# Extract AND ingest to Neo4j in one call
result = graphaide.ingest(file_path="document.pdf")

print(f"✓ Ingested {result.nodes_created} entities")
print(f"✓ Ingested {result.edges_created} relationships")
```

### Ingest with Ontology

```python
result = graphaide.ingest(
    file_path="document.pdf",
    ontology_path="ontology.nt"
)
```

### Ingest from Text

```python
text = """
GraphAide is a knowledge graph system built by PNNL.
It uses LLMs to extract entities and relationships.
"""

result = graphaide.ingest(input_text=text)
```

## Batch Ingestion: Multiple Documents

### From JSONL File

Process many documents in parallel:

```python
# documents.jsonl
# {"text": "First document content..."}
# {"text": "Second document content..."}
# {"text": "Third document content..."}

result = graphaide.ingest(
    jsonl_file_path="documents.jsonl",
    jsonl_field_name="text",
    jsonl_lines_per_batch=4  # Process 4 documents at once
)

print(f"Processed {result.segments_processed} documents")
```

### From Pre-extracted JSON

If you already have extracted data as JSON:

```python
result = graphaide.load_json_to_neo4j(
    json_path="GraphAide_KG_Extract_20261014_120000.json"
)

print(f"Loaded {result.nodes_created} nodes")
print(f"Loaded {result.edges_created} edges")
```

## Ingestion Options

### Clear Existing Graph

⚠️ **Warning: This deletes all data in Neo4j!**

```python
result = graphaide.ingest(
    file_path="document.pdf",
    clear_existing=True  # Only use when intentional
)
```

### Filter by Ontology

Only ingest entities and relationships matching your ontology:

```python
result = graphaide.ingest(
    file_path="document.pdf",
    ontology_path="ontology.nt",
    filter_by_ontology=True
)
```

### Merge Output

Automatically deduplicate entities during ingestion:

```python
result = graphaide.ingest(
    file_path="document.pdf",
    merge_output=True  # Combine duplicate entities
)
```

## Query Your Knowledge Graph

After ingestion, query your data in Neo4j:

### Using GraphAide Query

```python
answer = graphaide.query("What organizations are mentioned?")
print(answer)
```

### Using Neo4j Browser

Visit `http://localhost:7474` (default Neo4j web interface):

```cypher
// Find all organizations
MATCH (n:Organization) 
RETURN n.name, count(*)
ORDER BY count(*) DESC

// Find relationships
MATCH (p:Person)-[r:worksFor]->(o:Organization)
RETURN p.name, o.name

// Complex query: people and organizations
MATCH (p:Person)-[r:worksFor]->(o:Organization)
RETURN p, r, o
```

## Understanding Graph Structure

GraphAide creates nodes and edges in Neo4j:

### Nodes (Entities)

```python
{
    "id": "unique-identifier",
    "type": "Organization",           # Entity type from extraction
    "label": "GraphAide",              # Display name
    "properties": {
        "description": "A knowledge graph system",
        "source": "PNNL_About.pdf"
    }
}
```

In Neo4j:
```cypher
(n:Organization {name: "GraphAide", source: "PNNL_About.pdf"})
```

### Edges (Relationships)

```python
{
    "type": "worksFor",                # Relationship type
    "source": "sumit",                 # From node
    "target": "pnnl",                  # To node
    "properties": {
        "role": "Developer"
    }
}
```

In Neo4j:
```cypher
(p:Person)-[r:worksFor {role: "Developer"}]->(o:Organization)
```

## Ingestion Workflow

Here's what happens internally:

```
1. Extract Entities & Relationships
   ↓
2. Filter by Ontology (optional)
   ↓
3. Merge/Deduplicate (optional)
   ↓
4. Create Nodes in Neo4j
   ↓
5. Create Edges (Relationships) in Neo4j
   ↓
6. Return Statistics
```

## Common Patterns

### Build Knowledge Graph from Corpus

```python
import os
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-5.6-luna", api_key="...")
)

# Ingest all PDFs in folder
pdf_files = [f for f in os.listdir("documents/") if f.endswith(".pdf")]

for pdf_file in pdf_files:
    print(f"Ingesting {pdf_file}...")
    result = graphaide.ingest(file_path=f"documents/{pdf_file}")
    print(f"  → {result.nodes_created} entities, {result.edges_created} relationships")
```

### Iterative Refinement

```python
# First pass: extract all
result1 = graphaide.ingest(file_path="doc.pdf", merge_output=False)

# Second pass: with ontology filtering
result2 = graphaide.ingest(
    file_path="doc.pdf",
    ontology_path="ontology.nt",
    filter_by_ontology=True
)

# Compare
print(f"Without filtering: {result1.nodes_created}")
print(f"With filtering: {result2.nodes_created}")
```

### Batch Processing with Error Handling

```python
results = []

for jsonl_file in ["batch1.jsonl", "batch2.jsonl", "batch3.jsonl"]:
    try:
        result = graphaide.ingest(jsonl_file_path=jsonl_file)
        results.append({
            "file": jsonl_file,
            "nodes": result.nodes_created,
            "edges": result.edges_created
        })
    except Exception as e:
        print(f"Error ingesting {jsonl_file}: {e}")

# Summary
total_nodes = sum(r["nodes"] for r in results)
total_edges = sum(r["edges"] for r in results)
print(f"Total ingested: {total_nodes} nodes, {total_edges} edges")
```

## Troubleshooting

### Neo4j Connection Failed

```python
# Check Neo4j is running
# Default: localhost:7687

from graphaide import GraphDBConfig

graphdb_config=GraphDBConfig(
    uri="neo4j://localhost:7687",
    username="neo4j",
    password="password"
)
```

### Memory Issues with Large Batches

```python
# Process smaller batches
result = graphaide.ingest(
    jsonl_file_path="large_file.jsonl",
    jsonl_lines_per_batch=2  # Reduce batch size
)
```

### Duplicate Entities

```python
# Use merge_output to deduplicate
result = graphaide.ingest(
    file_path="doc.pdf",
    merge_output=True  # Combines similar entities
)
```

## Next Steps

- **[Query Your Graph](../resources.md#querying)** — Learn advanced Cypher queries
- **[Enhance Extraction](../vector-stores/usage.md)** — Use vector stores for better results
- **[See Examples](../resources.md)** — Learn from real-world use cases
