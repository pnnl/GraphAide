# GraphAide

<p align="center">
  <img src="https://raw.githubusercontent.com/pnnl-int/GraphAide/develop/tests/notebooks/GraphAideLogo_Label_Final.png" alt="GraphAide Logo" width="400">
</p>

**Build knowledge graphs from any document with LLMs and Neo4j.** GraphAide is a multi-agentic system that extracts entities and relationships from diverse sources, constructs knowledge graphs, and enables natural language reasoning over them—all with minimal setup.

## 30-Second Example

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig, get_sample_data_path

# Setup (once)
graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o"),
    graphdb_config=GraphDBConfig(uri="neo4j://localhost:7687", username="neo4j", password="password"),
)

# Extract from sample document
sample_pdf = get_sample_data_path("PNNL_About.pdf")
sample_ontology = get_sample_data_path("ontology_cyber.nt")
result = graphaide.extract(file_path=sample_pdf, ontology_path=sample_ontology)
print(f"✓ Extracted {len(result.nodes)} entities, {len(result.edges)} relationships")

# Load to Neo4j
graphaide.ingest(file_path=sample_pdf, ontology_path=sample_ontology)

# Query the graph
answer = graphaide.query("What organizations are mentioned?")
print(f"✓ Answer: {answer.answer}")
```

## What It Does

- **Extract** entities & relationships from PDFs, text, images, or web data
- **Ground** entities to Wikidata for semantic enrichment
- **Load** to Neo4j for queryable knowledge graphs
- **Reason** over graphs with natural language questions
- **Track** chunk provenance for result attribution

## Supported Providers

| LLM | Embedding | Vector Store |
|-----|-----------|--------------|
| OpenAI, Anthropic, Google, AWS Bedrock, LMStudio | OpenAI, Sentence Transformers, AWS Bedrock | ChromaDB, Qdrant |

## Documentation

📚 **Quick links:**
- **[QUICKSTART.md](https://github.com/pnnl-int/GraphAide/blob/develop/QUICKSTART.md)** — 5-minute setup and CLI examples
- **[ARCHITECTURE.md](https://github.com/pnnl-int/GraphAide/blob/develop/ARCHITECTURE.md)** — Technical deep dive (agents, workflows, patterns)
- **[REFERENCE.md](https://github.com/pnnl-int/GraphAide/blob/develop/REFERENCE.md)** — Complete API/CLI reference

## Install

```bash
pip install graphaide
```

See **[QUICKSTART.md](https://github.com/pnnl-int/GraphAide/blob/develop/QUICKSTART.md)** for detailed setup, Docker, and environment configuration.

## Use Cases

- **Knowledge Graph Generation** — Extract structured data from documents into queryable graphs
- **Semantic Search** — Find related entities and concepts across datasets
- **Domain-Specific Reasoning** — Answer questions requiring cross-document reasoning
- **Data Integration** — Merge disparate sources with automated entity grounding
- **Compliance & Audit** — Track relationships and dependencies with provenance

## Architecture

GraphAide uses a multi-agent architecture orchestrated by [LangGraph](https://langchain.com/docs/langgraph):

```
Document → [FileLoader] → [Extractor] → [Nodes4EdgesLoader] 
         → [NodesLoader] → [EdgesLoader] → Neo4j
         ↓
      [VectorDB] ← [Embeddings] ← RAG Context
```

**Factory pattern** manages LLMs, vector stores, and graph databases:
- `ModelFactory` — Loads LLMs from OpenAI, Anthropic, Google, AWS Bedrock, or local LMStudio
- `GraphDBFactory` — Manages Neo4j/Neptune connections
- `VectorStoreFactory` — Manages ChromaDB or Qdrant vector indices
- `AgentFactory` — Builds extraction, loading, and query agents

**Agents communicate** via `KGGenerationState` (append-only shared state with reducers):
- `raw_text`, `file_path` — Input document
- `nodes`, `edges` — Extracted entities and relationships  
- `rag_context` — Ontology constraints and Wikidata metadata
- `messages` — Status and debug info

## Tested Configurations

| Provider | LLM | Embedding |
|----------|-----|-----------|
| OpenAI | gpt-4o, gpt-4o-mini | text-embedding-3-small |
| Anthropic | claude-3-5-sonnet | claude-3-5-sonnet (native) |
| AWS Bedrock | anthropic.claude-3-5-sonnet | amazon.titan-embed-text-v1 |
| LMStudio (local) | google/gemma-3-27b:2 | text-embedding-nomic-embed-text-v1.5 |

## Run Modes

| Mode | Command |
|------|---------|
| **CLI** | `graphaide extract doc.pdf` |
| **Docker** | `docker compose up` then `docker exec` |
| **Python** | `from graphaide import GraphAide` |
| **REST** | `graphaide serve` → `http://localhost:8000` |

## Support

Please reach out to Sumit.Purohit@pnnl.gov for any questions.

## Authors and acknowledgment
Please reach out to Sumit.Purohit@pnnl.gov for any questions.

## Citation
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

The research described in this paper is partially supported
by the Resilience Through Data Driven, Intelligently Designed
Control (RD2C) Initiative at Pacific Northwest National Laboratory (PNNL) and the United States federal government.
Pacific Northwest National Laboratory is a multiprogram
national laboratory operated for the US Department of Energy
(DOE) by Battelle Memorial Institute under Contract No. DEAC05-76RL01830. PNNL Information Release PNNL-SA205147.

## License
Please refer LICENSE and DISCLAIMER files for details.


## Project status
Active development
