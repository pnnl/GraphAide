# Resources & Reference

Useful tools, examples, and references for working with GraphAide.

## Official Resources

- **[GitHub Repository](https://github.com/pnnl/GraphAide)** — Source code and issue tracking
- **[PyPI Package](https://pypi.org/project/graphaide)** — Installation and release information
- **[GitHub Issues](https://github.com/pnnl/GraphAide/issues)** — Bug reports and feature requests
- **[GitHub Discussions](https://github.com/pnnl/GraphAide/discussions)** — Questions and discussions

## Quick Reference

### Core Functions

| Function | Purpose | Learn More |
|----------|---------|------------|
| `GraphAide.extract()` | Extract entities and relationships from documents | [Extraction Guide](extraction/) |
| `GraphAide.ingest()` | Extract and load to Neo4j in one step | [Ingestion Guide](ingestion/) |
| `GraphAide.query()` | Ask questions about your knowledge graph | Query Examples |
| `GraphAide.ingest_to_vectordb()` | Load documents into vector store | [Vector Store Setup](vector-stores/setup.md) |
| `GraphAide.load_json_to_neo4j()` | Load pre-extracted JSON to Neo4j | [Ingestion Guide](ingestion/) |

### Key Classes

| Class | Purpose |
|-------|---------|
| `ModelConfig` | Configure LLM provider and settings |
| `GraphDBConfig` | Configure Neo4j connection |
| `VectorDBConfig` | Configure vector store (ChromaDB, Qdrant) |
| `VectorStoreConfig` | Configure retrieval behavior |
| `KGExtractInput` | Schema for extraction workflow |
| `Node` | Entity in extracted knowledge graph |
| `Edge` | Relationship in extracted knowledge graph |

## Common Use Cases

### Use Case 1: Extract from PDF

```python
from graphaide import GraphAide, ModelConfig, get_sample_data_path

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="...")
)

result = graphaide.extract(file_path="document.pdf")
print(f"✓ {len(result.nodes)} entities, {len(result.edges)} relationships")
```

### Use Case 2: Build Knowledge Graph from Multiple Documents

```python
import os
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="...")
)

# Ingest all PDFs
for filename in os.listdir("documents/"):
    if filename.endswith(".pdf"):
        print(f"Ingesting {filename}...")
        graphaide.ingest(file_path=f"documents/{filename}")

# Query
answer = graphaide.query("What are the main topics?")
print(answer)
```

### Use Case 3: Extract with Domain Ontology

```python
from graphaide import GraphAide, ModelConfig, get_sample_data_path

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="...")
)

# Use domain-specific ontology
result = graphaide.extract(
    file_path="cybersecurity_report.pdf",
    ontology_path=get_sample_data_path("ontology_cyber.nt"),
    filter_by_ontology=True
)
```

### Use Case 4: Semantic Search with Vector Store

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig
from graphaide.workflows.schemas import VectorStoreConfig

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="..."),
    vectordb_config=VectorDBConfig(provider="chromadb", path="./kb")
)

# Build knowledge base
graphaide.ingest_to_vectordb(file_paths=["knowledge.pdf"], split_docs=True)

# Extract with context
result = graphaide.extract(
    file_path="new_document.pdf",
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./kb",
            retrieve_type="documents"
        )
    ]
)
```

### Use Case 5: Batch Process JSONL

```python
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="...")
)

# documents.jsonl: {"text": "document content"}
result = graphaide.ingest(
    jsonl_file_path="documents.jsonl",
    jsonl_field_name="text",
    jsonl_lines_per_batch=4
)

print(f"Processed {result.segments_processed} documents")
```

## Querying Your Knowledge Graph

### Basic Neo4j Queries

After ingesting, query your graph in Neo4j Browser at `http://localhost:7474`:

```cypher
// Find all organizations
MATCH (n:Organization) RETURN n

// Find relationships between people and organizations
MATCH (p:Person)-[r:worksFor]->(o:Organization)
RETURN p.name, o.name

// Find all entities of a type
MATCH (n:Technology) RETURN n.name, COUNT(*) as mentions

// Complex: find people working for organizations in a specific location
MATCH (p:Person)-[:worksFor]->(o:Organization)
WHERE o.location = "Seattle"
RETURN p.name, o.name

// Find connected components (subgraphs)
MATCH (n)-[r*]-(m)
RETURN n, r, m
LIMIT 50
```

### Using GraphAide Query Function

```python
answer = graphaide.query("What organizations are mentioned?")
print(answer)

answer = graphaide.query("Who works for PNNL?")
print(answer)

answer = graphaide.query("What technologies are used?")
print(answer)
```

## LLM Provider Comparison

| Provider | Cost | Speed | Quality | Setup |
|----------|------|-------|---------|-------|
| **OpenAI** | Moderate | Fast | Excellent | Easy (API key) |
| **Anthropic** | Moderate | Fast | Excellent | Easy (API key) |
| **Google** | Low | Medium | Good | Moderate |
| **AWS Bedrock** | Low | Medium | Good | Complex (AWS creds) |
| **LM Studio** | Free | Slow | Fair | Hard (local server) |

### Recommended Combinations

| Scenario | Provider | Model | Why |
|----------|----------|-------|-----|
| **Quick Start** | OpenAI | gpt-4o | Best quality, fast setup |
| **Cost Conscious** | OpenAI | gpt-4o-mini | Good quality, lower cost |
| **Privacy** | LMStudio | Gemma 27B | Local, no API calls |
| **Enterprise** | AWS Bedrock | Claude 3.5 | Cost-effective at scale |
| **Local** | Anthropic | Claude 3.5 | Fast, no local infrastructure |

## Vector Store Comparison

| Store | Speed | Memory | Features | Production |
|-------|-------|--------|----------|-----------|
| **ChromaDB** | Fast | Low | Simple API | Good for dev |
| **Qdrant** | Very Fast | Medium | Advanced search | Excellent |

### When to Use Each

- **ChromaDB:** Local development, small collections, quick prototyping
- **Qdrant:** Production, large collections, distributed systems, high performance

## Troubleshooting Guide

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError: graphgen` | Package not installed properly | `pip install -e .` |
| `Neo4j connection failed` | Neo4j not running | Start Neo4j: `docker run -p 7687:7687 neo4j` |
| `API Key invalid` | Wrong or expired API key | Check provider console, verify key |
| `Out of memory` | Processing large file | Reduce `max_tokens_per_segment` |
| `Empty extraction` | LLM couldn't find entities | Use ontology to guide extraction |

### Performance Tips

1. **Faster extraction:** Use smaller context window (4096 instead of 8192)
2. **Better results:** Use ontology to guide extraction
3. **Scale JSONL:** Increase `jsonl_lines_per_batch` for parallelism
4. **Vector store:** Use ChromaDB for local dev, Qdrant for production

## Development

### Running Tests

```bash
pip install pytest
pytest tests/ -v
```

### Building Documentation

```bash
pip install mkdocs mkdocs-material mkdocstrings[python]
mkdocs serve  # Local preview
mkdocs build  # Build static site
```

### Contributing

See [GitHub Contributing Guidelines](https://github.com/pnnl/GraphAide/blob/develop/CONTRIBUTING.md)

## Research & Citations

If you use GraphAide in your research, please cite:

```bibtex
@inproceedings{purohit2024graphaide,
  title={GraphAide: Advanced Graph-Assisted Query and Reasoning System},
  author={Purohit, Sumit and Chin, George and Mackey, Patrick S and Cottam, Joseph A},
  booktitle={2024 IEEE International Conference on Big Data (BigData)},
  pages={3485--3493},
  year={2024},
  organization={IEEE}
}
```

## Support & Contact

- **Questions?** Open a [GitHub Discussion](https://github.com/pnnl/GraphAide/discussions)
- **Bug Report?** File a [GitHub Issue](https://github.com/pnnl/GraphAide/issues)
- **Contact:** sumit.purohit@pnnl.gov

## Glossary

| Term | Definition |
|------|-----------|
| **Entity** | A specific thing extracted (person, organization, location, etc.) |
| **Relationship** | A connection between two entities (works for, located in, etc.) |
| **Ontology** | A formal definition of entity and relationship types for a domain |
| **Embedding** | Numerical representation of text for semantic search |
| **Vector Store** | Database of embeddings for fast semantic retrieval |
| **RAG** | Retrieval-Augmented Generation (using external knowledge during generation) |
| **Knowledge Graph** | A graph of interconnected entities and relationships |
| **LLM** | Large Language Model (AI model like GPT-4, Claude) |
| **Neo4j** | Popular graph database for storing knowledge graphs |

## Next Steps

- Explore [Installation Options](installation/)
- Learn [Configuration](configuration/)
- Start [Extracting](extraction/)
- Build [Knowledge Graphs](ingestion/)
- Enhance with [Vector Stores](vector-stores/)
