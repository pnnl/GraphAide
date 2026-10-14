# API Reference

Complete reference for GraphAide classes, functions, and configurations.

## Main GraphAide Class

::: graphgen.graphaide_api.GraphAide

## Configuration Classes

### ModelConfig

::: graphgen.config.ModelConfig

### GraphDBConfig

::: graphgen.config.GraphDBConfig

### VectorDBConfig

::: graphgen.config.VectorDBConfig

## Workflow Schemas

### Extraction

::: graphgen.v2.workflows.schemas.KGExtractInput

::: graphgen.v2.workflows.schemas.KGExtractOutput

### Ingestion

::: graphgen.v2.workflows.schemas.KGIngestInput

::: graphgen.v2.workflows.schemas.KGIngestOutput

### Vector Database

::: graphgen.v2.workflows.schemas.VectorDBIngestInput

::: graphgen.v2.workflows.schemas.VectorDBIngestOutput

::: graphgen.v2.workflows.schemas.VectorStoreConfig

## Data Models

### Node (Entity)

::: graphgen.v2.state.Node

### Edge (Relationship)

::: graphgen.v2.state.Edge

### MergedNode

::: graphgen.v2.state.MergedNode

### MergedEdge

::: graphgen.v2.state.MergedEdge

## Utilities

### get_sample_data_path

```python
def get_sample_data_path(filename: str) -> Path
```

Get path to sample data files bundled with GraphAide.

**Parameters:**
- `filename` (str): Name of sample file (e.g., "PNNL_About.pdf", "ontology_cyber.nt")

**Returns:**
- `Path`: Full path to the sample file

**Example:**
```python
from graphaide import get_sample_data_path

pdf_path = get_sample_data_path("PNNL_About.pdf")
ontology_path = get_sample_data_path("ontology_cyber.nt")
```

## Enumerations

### ProviderType

```python
class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AWS_BEDROCK = "bedrock"
    LMSTUDIO = "lmstudio"
```

### VectorDBProviderType

```python
class VectorDBProviderType(str, Enum):
    CHROMADB = "chromadb"
    QDRANT = "qdrant"
```

## Exception Classes

### GraphAideError

Base exception for all GraphAide errors.

```python
try:
    result = graphaide.extract(file_path="document.pdf")
except GraphAideError as e:
    print(f"GraphAide error: {e}")
```

### ConfigurationError

Raised when configuration is invalid.

### ExtractionError

Raised when extraction fails.

### IngestionError

Raised when ingestion to Neo4j fails.

### VectorStoreError

Raised when vector store operations fail.

## Complete Example

```python
from graphaide import (
    GraphAide,
    ModelConfig,
    GraphDBConfig,
    VectorDBConfig,
    get_sample_data_path
)
from graphaide.workflows.schemas import VectorStoreConfig

# Create configuration
model_config = ModelConfig(
    provider="openai",
    model_name="gpt-4o",
    api_key="sk-...",
    embedding_model="text-embedding-3-small",
    temperature=0.3,
    max_output_tokens_limit_llm=16000
)

graphdb_config = GraphDBConfig(
    uri="neo4j://localhost:7687",
    username="neo4j",
    password="password"
)

vectordb_config = VectorDBConfig(
    provider="chromadb",
    path="./chroma"
)

# Initialize GraphAide
graphaide = GraphAide(
    model_config=model_config,
    graphdb_config=graphdb_config,
    vectordb_config=vectordb_config
)

# Load sample ontology
sample_ontology = get_sample_data_path("ontology_cyber.nt")

# Extract with vector store retrieval
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path=sample_ontology,
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./chroma",
            retrieve_type="documents",
            description="Knowledge base context"
        )
    ],
    filter_by_ontology=True,
    max_tokens_per_segment=8192
)

# Print results
print(f"Extracted {len(result.nodes)} entities")
print(f"Extracted {len(result.edges)} relationships")

# Access nodes
for node in result.nodes[:5]:
    print(f"- {node.label} ({node.type})")

# Ingest to Neo4j
ingest_result = graphaide.ingest(
    file_path="document.pdf",
    ontology_path=sample_ontology
)

print(f"Ingested {ingest_result.nodes_created} nodes")
print(f"Ingested {ingest_result.edges_created} edges")

# Query the graph
answer = graphaide.query("What are the main topics?")
print(f"Answer: {answer}")
```

## CLI Reference

GraphAide also provides a command-line interface:

```bash
# Show version
graphaide --version

# Extract from PDF
graphaide extract document.pdf --ontology ontology.nt

# Ingest to Neo4j
graphaide ingest document.pdf --output results.json

# Start REST server
graphaide serve --host 0.0.0.0 --port 8000
```

## REST API

When running `graphaide serve`, access the API at `http://localhost:8000`:

### Extract Endpoint

```
POST /extract
Content-Type: application/json

{
  "file_path": "document.pdf",
  "ontology_path": "ontology.nt",
  "max_tokens_per_segment": 8192,
  "filter_by_ontology": false
}
```

**Response:**
```json
{
  "nodes": [...],
  "edges": [...],
  "segments_processed": 5,
  "output_json_path": "GraphAide_KG_Extract_20261014_120000.json"
}
```

### Ingest Endpoint

```
POST /ingest
Content-Type: application/json

{
  "file_path": "document.pdf",
  "ontology_path": "ontology.nt",
  "clear_existing": false
}
```

**Response:**
```json
{
  "nodes_created": 42,
  "edges_created": 35,
  "segments_processed": 5
}
```

### Query Endpoint

```
POST /query
Content-Type: application/json

{
  "question": "What organizations are mentioned?",
  "max_results": 10
}
```

**Response:**
```json
{
  "question": "What organizations are mentioned?",
  "answer": "PNNL and GraphAide are mentioned...",
  "graph_answer": "MATCH (n:Organization) RETURN n",
  "related_nodes": [...],
  "related_edges": [...]
}
```

## Type Hints

All functions use Python type hints for IDE autocomplete and type checking.

```python
from graphaide import GraphAide, ModelConfig
from pathlib import Path
from typing import Optional, List

graphaide: GraphAide = GraphAide(model_config=ModelConfig(...))

# Type hints guide IDE autocomplete
result = graphaide.extract(
    file_path="document.pdf",  # str or Path
    ontology_path: Optional[str] = None,
    max_tokens_per_segment: int = 8192
)

# Result types are well-defined
nodes: List[Node] = result.nodes
edges: List[Edge] = result.edges
```

## For More Information

- **[Installation Guide](installation/)** — Get started
- **[Configuration Guide](configuration/)** — Detailed config options
- **[Examples](resources.md)** — Real-world use cases
- **[GitHub Repository](https://github.com/pnnl/GraphAide)** — Source code
