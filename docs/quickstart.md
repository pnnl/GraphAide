# Quick Start: Extract Knowledge Graphs

This guide shows how to extract knowledge graphs from documents and text using GraphAide.

## Setup

### 1. Install GraphAide

```bash
pip install graphaide
```

### 2. Configure Environment

Create a `.env` file in your project directory:

```env
# LLM Provider (OpenAI example)
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL_NAME=gpt-4o
OPENAI_EMBEDDING_MODEL_NAME=text-embedding-3-small

# Or use custom base URL (for internal APIs)
OPENAI_BASE_URL=https://your-api-endpoint.com

# Neo4j Database
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

### 3. Initialize GraphAide

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure LLM
model_config = ModelConfig(
    provider="openai",
    model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
    api_key=os.getenv("OPENAI_API_KEY"),
    embedding_model_name=os.getenv("OPENAI_EMBEDDING_MODEL_NAME"),
    base_url=os.getenv("OPENAI_BASE_URL", None),  # Optional
)

# Configure Neo4j
graphdb_config = GraphDBConfig(
    uri=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD"),
    database=os.getenv("NEO4J_DATABASE", "neo4j"),
)

# Create GraphAide instance
graphaide = GraphAide(
    model_config=model_config,
    graphdb_config=graphdb_config,
)
```

## Extract from File

Extract knowledge graph from a PDF or text file:

```python
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.ttl",  # Optional: constrains node/edge types
    max_tokens_per_segment=4096,
)

print(f"Extracted {len(result.nodes)} nodes, {len(result.edges)} edges")
print(f"Saved to: {result.stats.get('output_json_path')}")
```

**Supported file formats:** PDF, TXT, MD, CSV

**Output:** JSON file with extracted nodes and edges (location printed in output)

## Extract from Text

Extract knowledge graph from raw text (new feature):

```python
text = """
Sumit Purohit is a Data Scientist at PNNL working on GraphAide.
GraphAide is a knowledge graph generation framework that extracts
structured information and loads it into Neo4j.
"""

result = graphaide.extract(
    input_text=text,
    ontology_path="ontology.ttl",  # Optional
    max_tokens_per_segment=4096,
)

print(f"Extracted {len(result.nodes)} nodes, {len(result.edges)} edges")
```

**Note:** Either `file_path` or `input_text` must be provided (not both)

## Extract with Chunk Tracking

Track which chunks entities came from (for multi-document graphs):

```python
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.ttl",
    use_chunk_aware=True,
    max_tokens_per_segment=4096,
)

print(f"Chunks tracked: {result.stats.get('chunks_tracked')}")
```

**What it does:**
- Creates `SourceDocument` and `ChunkParagraph` nodes in Neo4j
- Links extracted entities to their source chunks
- Enables queries like "Show all entities from chunk #5"

## Next Steps

- **Ingest to Neo4j:** Use `graphaide.ingest()` to extract and load directly
- **Query the graph:** Use `graphaide.query()` for natural language Q&A
- **Load JSON:** Use `graphaide.load_json()` to load previously extracted JSON
- **Advanced configs:** Pass any `KGGenerationState` parameter via `**kwargs`

## Troubleshooting

**"API key not found"**
- Ensure `.env` file exists in your working directory
- Check `OPENAI_API_KEY` is set correctly

**"Could not connect to Neo4j"**
- Verify Neo4j is running: `neo4j status`
- Check `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`

**"Max tokens exceeded"**
- Reduce `max_tokens_per_segment` (try 2048 or 1024)
- LLM will handle smaller chunks better
