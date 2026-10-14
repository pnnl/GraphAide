# Welcome to GraphAide

<div align="center">
  <img src="assets/logo.png" alt="GraphAide Logo" width="300">
</div>

## What is GraphAide?

**GraphAide** is a powerful, multi-agentic system that transforms your documents into queryable knowledge graphs using Large Language Models (LLMs) and Neo4j.

Whether you have PDFs, text files, images, or web data, GraphAide can:
- **Extract** entities and relationships automatically
- **Ground** data to external sources like Wikidata for enrichment
- **Load** everything into Neo4j for graph queries
- **Reason** over your knowledge graph with natural language
- **Track** where information came from with full provenance

## Why GraphAide?

| Feature | Benefit |
|---------|---------|
| **Multi-Model Support** | Use OpenAI, Anthropic, Google, AWS Bedrock, or local models |
| **Flexible Configuration** | Customize LLMs, embeddings, vector stores, and databases |
| **Multi-Retriever RAG** | Enhance extraction with multiple knowledge sources simultaneously |
| **Production Ready** | Deploy as CLI, Docker, Python library, or REST API |
| **Enterprise Ready** | Track provenance, support compliance and auditing |

## Quick Start

### 30-Second Example (Simplest)

```python
from graphaide import GraphAide, ModelConfig, get_sample_data_path

# Setup - uses default Neo4j at localhost:7687
graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai", 
        model_name="gpt-4o",
        api_key="sk-..."
    )
)

# Extract from sample document
sample_pdf = get_sample_data_path("PNNL_About.pdf")
sample_ontology = get_sample_data_path("ontology_cyber.nt")
result = graphaide.extract(file_path=sample_pdf, ontology_path=sample_ontology)
print(f"✓ Extracted {len(result.nodes)} entities, {len(result.edges)} relationships")
```

### With Custom Neo4j

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig, get_sample_data_path

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="sk-..."),
    graphdb_config=GraphDBConfig(uri="neo4j://my-server:7687", username="neo4j", password="password"),
)

sample_pdf = get_sample_data_path("PNNL_About.pdf")
result = graphaide.extract(file_path=sample_pdf)
graphaide.ingest(file_path=sample_pdf)
answer = graphaide.query("What organizations are mentioned?")
```

## Use Cases

- **Knowledge Management** — Build searchable knowledge graphs from company documents
- **Research Analysis** — Extract and connect findings across papers and reports
- **Data Integration** — Merge information from multiple sources with automatic entity linking
- **Compliance Auditing** — Track relationships and dependencies with full provenance
- **Domain Expertise** — Answer questions requiring reasoning across documents

## What You'll Learn

Start with **[Installation](installation/index.md)** to get GraphAide running, then explore:

1. **[Configuration](configuration/index.md)** — Set up models, databases, and vector stores
2. **[Extraction](extraction/index.md)** — Extract entities and relationships from documents
3. **[Ontologies](extraction/ontology.md)** — Use domain knowledge to guide extraction
4. **[Ingestion](ingestion/index.md)** — Load extracted data into Neo4j
5. **[Vector Stores](vector-stores/setup.md)** — Enhance extraction with semantic search

## Get Help

- 📖 Check [Resources](resources.md) for tutorials and examples
- 🐛 Report issues on [GitHub Issues](https://github.com/pnnl/GraphAide/issues)
- 💬 Ask questions via [GitHub Discussions](https://github.com/pnnl/GraphAide/discussions)

## Legal

Please review the important legal documents:

- **[Legal Information](legal/)** — License, disclaimer, acknowledgment, notices

---

**Ready to build your first knowledge graph?** Start with [Installation](installation/index.md).
