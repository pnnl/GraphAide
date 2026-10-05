# GraphAide Quick Start

Get up and running in 5 minutes.

---

## Install & Configure (2 min)

### 1. Install Package
```bash
pip install graphaide
```

### 2. Setup Environment
Create `.env` in your project directory:
```bash
# LLM Provider (pick one)
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o
OPENAI_EMBEDDING_MODEL_NAME=text-embedding-3-small

# Graph Database
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

### 3. Start Neo4j (Optional - for ingest/query)
```bash
docker run -d \
  --name neo4j \
  -p 7687:7687 \
  -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

---

## Your First Extraction (3 min)

### Try with Sample Data

We include sample documents in the package. Extract from them:

**Python:**
```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig, get_sample_data_path

# Setup
graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o"),
    graphdb_config=GraphDBConfig(uri="neo4j://localhost:7687", username="neo4j", password="password"),
)

# Get sample files
pdf_path = get_sample_data_path("PNNL_About.pdf")
ontology_path = get_sample_data_path("ontology_cyber.nt")

# Extract to JSON
result = graphaide.extract(file_path=pdf_path, ontology_path=ontology_path)
print(f"✓ {len(result.nodes)} entities, {len(result.edges)} relationships")

# Extract + load to Neo4j
result = graphaide.ingest(file_path=pdf_path, ontology_path=ontology_path)
print(f"✓ Loaded: {result.message}")

# Query the graph
answer = graphaide.query("What organizations are mentioned?")
print(f"✓ Answer: {answer.answer}")
```

**CLI:**
```bash
# Get sample paths first (print to console)
python -c "from graphaide import get_sample_data_path; print(get_sample_data_path())"

# Extract to JSON
graphaide extract /path/to/PNNL_About.pdf \
  --ontology /path/to/ontology_cyber.nt \
  --log-level INFO

# Extract and load to Neo4j
graphaide ingest /path/to/PNNL_About.pdf \
  --ontology /path/to/ontology_cyber.nt

# Query the graph
graphaide query "What is the main focus?"
```

### With Your Own Documents

```python
# Use any PDF or text file
result = graphaide.extract(
    file_path="your_document.pdf",
    ontology_path="your_schema.ttl"
)
```

---

## Common Commands

### CLI Help

```bash
graphaide --help
graphaide extract --help
graphaide ingest --help
graphaide query --help
```

### Logging Control

```bash
# INFO level (default) - progress messages
graphaide extract document.pdf --log-level INFO

# DEBUG level - detailed output including context
graphaide extract document.pdf --log-level DEBUG

# Custom log file
graphaide extract document.pdf --log-file my_run.log
```

### Supported File Formats

- **Text**: `.txt`, `.md`
- **Documents**: `.pdf`
- **Data**: `.json`, `.yaml`, `.yml`, `.csv`
- **Images**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`
- **Ontologies**: `.owl`, `.ttl`, `.nt`

### Document Chunking

```bash
# Control token size per chunk (default 4096)
graphaide extract document.pdf --max-tokens-per-segment 2048

# Use section-based chunking for markdown
graphaide extract document.md --section-chunking
```

---

## Deployment Options

### Docker Setup (5 min)

```bash
# 1. Start all services (Neo4j, GraphAide API)
docker compose up -d

# 2. Verify services
curl http://localhost:8000/health

# 3. Access Neo4j browser
# http://localhost:17474
# Credentials: neo4j / graphaide123
```

### Services Running

| Service | URL | Purpose |
|---------|-----|---------|
| GraphAide API | http://localhost:8000 | REST endpoints |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Neo4j Browser | http://localhost:17474 | Graph visualization |
| Neo4j Bolt | bolt://localhost:17687 | Graph database |

### REST API Quick Start

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Extract Knowledge Graph:**
```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "document.pdf",
    "log_level": "INFO"
  }'
```

**Query the Graph:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main topics?"
  }'
```

---

## Python API - Simple & Advanced

### Simple Facade (Recommended)

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig

model_config = ModelConfig(
    provider="openai",
    model_name="gpt-4o",
    api_key="sk-...",
    embedding_model_name="text-embedding-3-small",
)

graphdb_config = GraphDBConfig(
    uri="neo4j://localhost:7687",
    username="neo4j",
    password="graphaide123",
)

graphaide = GraphAide(model_config=model_config, graphdb_config=graphdb_config)

# Extract with options
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.ttl",
    use_chunk_aware=True,              # Track chunk provenance
    max_tokens_per_segment=2048,       # Control chunk size
    filter_by_ontology=True,           # Filter by ontology types
)

# Ingest to Neo4j
result = graphaide.ingest(file_path="document.pdf", ontology_path="ontology.ttl")

# Query
result = graphaide.query(question="What are the main topics?")
print(result.answer)

# Load pre-extracted JSON
result = graphaide.load_json(json_path="GraphAide_KG_Extract_2026-07-31_14-23-45.json")
```

### Advanced (Direct WorkflowManager)

```python
from graphgen.v2.workflows.manager import WorkflowManager
from graphgen.v2.workflows.schemas import WorkflowConfig
from graphgen.v2.ModelManager import ModelConfig
from graphgen.v2.GraphDBManager import GraphDBConfig

model_config = ModelConfig(provider="openai", model_name="gpt-4o")
graphdb_config = GraphDBConfig(
    uri="neo4j://localhost:7687",
    username="neo4j",
    password="graphaide123"
)
workflow_config = WorkflowConfig(model_config=model_config, graphdb_config=graphdb_config)
manager = WorkflowManager(global_config=workflow_config)

# Extract
result = manager.run("kg_extract", {
    "file_path": "document.pdf",
    "ontology_path": "ontology.ttl",
})

# Load to Neo4j
result = manager.run("kg_load_json", {
    "json_file": "GraphAide_KG_Extract_2026-07-31_14-23-45.json"
})

# Query
result = manager.run("kg_query", {
    "question": "What are the main topics?",
})
```

---

## Troubleshooting

### "No LLM provider configured"

```bash
# Check .env file
cat .env | grep OPENAI_API_KEY

# Or set inline
export OPENAI_API_KEY=sk-...
graphaide extract document.pdf
```

### "Cannot connect to Neo4j"

```bash
# Verify running and accessible
curl bolt://localhost:7687

# Check credentials
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=correct_password
```

### "Vector store error"

```bash
# Clear cache
rm -rf ./chroma_data ./qdrant_data

# Restart
graphaide extract document.pdf
```

### Slow extraction

```bash
# Use DEBUG to identify bottleneck
graphaide extract document.pdf --log-level DEBUG

# Reduce chunk size
graphaide extract document.pdf --max-tokens-per-segment 1024

# Use faster model
export OPENAI_MODEL_NAME=gpt-4o-mini
```

---

## More Resources

- **[README.md](https://github.com/pnnl-int/GraphAide)** — Overview and use cases
- **[ARCHITECTURE.md](https://github.com/pnnl-int/GraphAide/blob/develop/ARCHITECTURE.md)** — Technical deep dive (agents, workflows, patterns)
- **[REFERENCE.md](https://github.com/pnnl-int/GraphAide/blob/develop/REFERENCE.md)** — Complete API/CLI reference
- **[CLAUDE.md](https://github.com/pnnl-int/GraphAide/blob/develop/CLAUDE.md)** — Python API details and workflow documentation

---

## Architecture Overview

GraphAide uses a **multi-agent architecture** orchestrated by [LangGraph](https://langchain.com/docs/langgraph):

```
Document → [FileLoader] → [Extractor] → [Nodes4EdgesLoader] 
         → [NodesLoader] → [EdgesLoader] → Neo4j
         ↓
      [VectorDB] ← [Embeddings] ← RAG Context
```

**Factory Pattern** manages:
- `ModelFactory` — Loads LLMs (OpenAI, Anthropic, Google, AWS Bedrock, LMStudio)
- `GraphDBFactory` — Manages Neo4j/Neptune connections
- `VectorStoreFactory` — Manages ChromaDB or Qdrant indices
- `AgentFactory` — Builds extraction, loading, and query agents

**State Management** via `KGGenerationState`:
- `raw_text`, `file_path` — Input document
- `nodes`, `edges` — Extracted entities and relationships
- `rag_context` — Ontology constraints and metadata
- `messages` — Status and debug info

---

## Setup from Source

```bash
git clone https://github.com/pnnl-int/GraphAide.git
cd graphaide
pip install .              # Install
pip install .[testing]     # With tests
```

---

**Ready to get started! 🚀**
