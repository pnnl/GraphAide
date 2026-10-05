# GraphAide Reference Guide

Complete reference for CLI commands, API endpoints, configuration options, and feature matrix.

---

## Table of Contents

1. [CLI Commands](#cli-commands)
2. [REST API Endpoints](#rest-api-endpoints)
3. [Environment Variables](#environment-variables)
4. [Supported File Formats](#supported-file-formats)
5. [Feature Matrix](#feature-matrix)
6. [State Fields](#state-fields)

---

## CLI Commands

### Extract Knowledge Graph

```bash
graphaide extract <file> [OPTIONS]
```

**Options:**
- `--ontology FILE` - Path to ontology file (.owl, .ttl, .nt)
- `--max-tokens N` - Max tokens for LLM output (default: 4096)
- `--max-tokens-per-segment N` - Tokens per document chunk (default: 4096)
- `--log-level LEVEL` - DEBUG, INFO, WARNING, ERROR (default: INFO)
- `--log-file PATH` - Output file for logs (default: graphaide_run_<date>.log)
- `--output FILE` - Output JSON file (auto-generated if not specified)

**Example:**
```bash
graphaide extract document.pdf \
  --ontology ontology.ttl \
  --log-level DEBUG \
  --max-tokens-per-segment 2048
```

### Ingest (Extract + Load to Neo4j)

```bash
graphaide ingest <file> [OPTIONS]
```

**Options:**
- All extract options above, plus:
- `--neo4j-uri URI` - Neo4j connection (default: from .env)
- `--neo4j-username USER` - Neo4j username (default: neo4j)
- `--neo4j-password PASS` - Neo4j password
- `--neo4j-database DB` - Database name (default: neo4j)

**Example:**
```bash
graphaide ingest document.pdf \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-username neo4j \
  --neo4j-password graphaide123
```

### Load Pre-extracted JSON

```bash
graphaide kg-load-json <json-file> [OPTIONS]
```

**Options:**
- `--neo4j-uri URI` - Neo4j connection
- `--neo4j-username USER` - Neo4j username
- `--neo4j-password PASS` - Neo4j password

**Example:**
```bash
graphaide kg-load-json GraphAide_KG_Extract_2026-07-31_14-23-45.json
```

### Query Knowledge Graph

```bash
graphaide query <question> [OPTIONS]
```

**Options:**
- `--neo4j-uri URI` - Neo4j connection
- `--neo4j-username USER` - Neo4j username
- `--neo4j-password PASS` - Neo4j password

**Example:**
```bash
graphaide query "What are the main entities?" \
  --neo4j-uri bolt://localhost:7687
```

### Populate Vector Store

```bash
graphaide vectordb-ingest <file> [OPTIONS]
```

**Options:**
- `--vector-store-provider PROVIDER` - "chroma" or "qdrant" (default: chroma)
- `--vector-store-name NAME` - Collection name
- `--vector-store-path PATH` - Store location
- `--use-vision-extraction` - Extract text from images via LLM
- `--extract-pdf-images` - Extract images from PDFs

**Example:**
```bash
graphaide vectordb-ingest document.pdf \
  --vector-store-provider qdrant \
  --use-vision-extraction
```

### Visualize Embeddings

```bash
graphaide visualize-embeddings [OPTIONS]
```

**Options:**
- `--vector-store-provider PROVIDER` - "chroma" or "qdrant"
- `--vector-store-name NAME` - Collection name
- `--output-file FILE` - HTML file to save visualization

### Generate Ontology

```bash
graphaide generate-ontology [OPTIONS]
```

**Options:**
- `--node-types FILE` - JSON file with node type definitions
- `--edge-types FILE` - JSON file with edge type definitions
- `--output FILE` - Output ontology file (.nt or .ttl)

### Start REST API Server

```bash
graphaide serve [OPTIONS]
```

**Options:**
- `--port PORT` - Server port (default: 8000)
- `--host HOST` - Bind address (default: 127.0.0.1)
- `--reload` - Auto-reload on code changes (development only)

**Example:**
```bash
graphaide serve --port 8000 --host 0.0.0.0
```

### Help

```bash
graphaide --help                    # All commands
graphaide extract --help            # Specific command
graphaide --version                 # Version info
```

---

## REST API Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{"status": "ok", "timestamp": "2026-07-31T14:23:45"}
```

### Extract Knowledge Graph

```http
POST /extract
Content-Type: application/json

{
  "file_path": "document.pdf",
  "ontology_file_path": "ontology.ttl",
  "max_tokens_per_segment": 4096,
  "log_level": "INFO"
}
```

**Response:**
```json
{
  "status": "success",
  "output_file": "GraphAide_KG_Extract_2026-07-31_14-23-45.json",
  "node_count": 42,
  "edge_count": 127,
  "messages": ["Successfully generated 10 segments...", "..."]
}
```

### Ingest & Load

```http
POST /ingest
Content-Type: application/json

{
  "file_path": "document.pdf",
  "ontology_file_path": "ontology.ttl"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Loaded 42 nodes and 127 edges to Neo4j",
  "nodes_loaded": 42,
  "edges_loaded": 127
}
```

### Load Pre-extracted JSON

```http
POST /load-json
Content-Type: application/json

{
  "json_file": "GraphAide_KG_Extract_2026-07-31_14-23-45.json"
}
```

### Query Graph

```http
POST /query
Content-Type: application/json

{
  "question": "What are the main entities?",
  "limit_context": 5
}
```

**Response:**
```json
{
  "status": "success",
  "question": "What are the main entities?",
  "intent": {
    "subjectivity": 0.3,
    "locality": 0.1,
    "navigationality": 0.8
  },
  "answer": "The main entities include...",
  "source_documents": ["doc1.pdf", "doc2.pdf"]
}
```

### Vector Store Ingest

```http
POST /vectordb-ingest
Content-Type: application/json

{
  "file_paths": ["document.pdf", "image.png"],
  "vector_store_provider": "qdrant",
  "use_vision_extraction": true
}
```

### Visualize Embeddings

```http
GET /visualize-embeddings?vector_store_provider=qdrant&vector_store_name=my_store
```

**Response:** HTML visualization page

### API Documentation

```http
GET /docs
GET /openapi.json
```

Interactive Swagger UI and OpenAPI spec.

---

## Environment Variables

### LLM Providers

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o
OPENAI_EMBEDDING_MODEL_NAME=text-embedding-3-small

# Anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022

# AWS Bedrock
BEDROCK_API_KEY=...
BEDROCK_REGION=us-west-2

# Google Generative AI
GOOGLE_API_KEY=...

# LMStudio (local)
LMSTUDIO_BASE_URL=http://localhost:1234
LMSTUDIO_MODEL_NAME=google/gemma-3-27b:2
LMSTUDIO_EMBEDDING_MODEL_NAME=text-embedding-nomic-embed-text-v1.5
```

### Graph Database

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=graphaide123
NEO4J_DATABASE=neo4j
```

### Vector Store

```bash
VECTOR_STORE_PROVIDER=chroma  # or "qdrant"
VECTOR_STORE_NAME=graphaide
VECTOR_STORE_PATH=./chroma_data

# Qdrant specific
QDRANT_PATH=./qdrant_data
QDRANT_COLLECTION_NAME=my_collection
```

### Logging

```bash
GRAPHAIDE_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
GRAPHAIDE_LOG_FILE=./logs/run.log
```

### Model Configuration

```bash
OPENAI_MODEL_MAX_TOKENS=4096
TEMPERATURE=0.7
TOP_P=0.9
```

---

## Supported File Formats

### Input Documents

| Format | Extension | Handler | Notes |
|--------|-----------|---------|-------|
| **Plain Text** | `.txt` | TextParser | Token-based chunking |
| **Markdown** | `.md` | TextParser | Treated as plain text |
| **PDF** | `.pdf` | PyPDFLoader | Per-page chunks |
| **JSON** | `.json` | JSONLoader | Flat or nested structure |
| **YAML** | `.yaml`, `.yml` | YAMLLoader | - |
| **CSV** | `.csv` | CSVLoader | One row per document |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp` | ImageLoader | Vision extraction optional |

### Ontology Files

| Format | Extension | Parser |
|--------|-----------|--------|
| **OWL/RDF-XML** | `.owl` | RDFLib |
| **Turtle** | `.ttl` | RDFLib |
| **N-Triples** | `.nt` | RDFLib |

### Output Formats

| Format | Generated By | Contains |
|--------|--------------|----------|
| **JSON** | Extractor | nodes, edges, metadata |
| **Neo4j Graph** | Loaders | Cypher-loaded nodes/edges |
| **HTML** | Visualizer | Embedding projections (UMAP) |

---

## Feature Matrix

### Workflow Availability

| Feature | CLI (Host) | CLI (Docker) | Python API | REST API |
|---------|:----------:|:------------:|:----------:|:--------:|
| KG Extraction | ✓ | ✓ | ✓ | ✓ |
| KG Ingestion | ✓ | ✓ | ✓ | ✓ |
| KG Load JSON | ✓ | ✓ | ✓ | ✓ |
| KG Query | ✓ | ✓ | ✓ | ✓ |
| Vector DB Ingest | ✓ | ✓ | ✓ | ✓ |
| Visualize Embeddings | ✓ | ✓ | ✓ | ✓ |
| Ontology Generation | ✓ | ✓ | ✓ | ✓ |

### Model Providers

| Provider | LLM Support | Embedding | Vision | Local |
|----------|:-----------:|:---------:|:------:|:-----:|
| **OpenAI** | ✓ | ✓ | ✓ (GPT-4o) | ✗ |
| **Anthropic** | ✓ | ✗ | ✓ (Claude 3.5+) | ✗ |
| **AWS Bedrock** | ✓ | ✓ | ✓ | ✗ |
| **Google** | ✓ | ✓ | ✗ | ✗ |
| **LMStudio** | ✓ | ✓ | ✗ | ✓ |

### Vector Stores

| Feature | ChromaDB | Qdrant |
|---------|:--------:|:------:|
| Similarity Search | ✓ | ✓ |
| Metadata Filtering | ✓ | ✓ |
| Batch Loading | ✓ | ✓ |
| Persistence | ✓ | ✓ |
| Local Storage | ✓ | ✓ |
| Cloud Support | ✗ | Planned |
| Performance (1M+ docs) | Good | Excellent |

### Advanced Features

| Feature | Available |
|---------|:---------:|
| Parallel Segment Processing | ✓ |
| Intent Prediction | ✓ |
| Multi-hop Reasoning | ✓ |
| RAG (Retrieval Augmented Generation) | ✓ |
| Vision Model Integration | ✓ |
| Ontology-Guided Extraction | ✓ |
| Multi-Retriever Pattern | ✓ |
| Pre-filter Graph Saves | ✓ |
| Logging Control (DEBUG/INFO/WARNING) | ✓ |
| Markdown File Support | ✓ |

---

## State Fields

### KGGenerationState TypedDict

```python
{
    # Input paths
    "file_path": str,                           # Single file
    "file_paths": List[str],                    # Multiple files
    "image_file_paths": List[str],              # Images for embedding
    "ontology_file_path": str,                  # Ontology file
    
    # Text data
    "raw_text": str,                            # Text to extract from
    "question": str,                            # Query question
    "segments": List[str],                      # Document chunks (mutable)
    
    # RAG context
    "rag_context": Optional[RAGContext],        # Ontology + Wikidata
    
    # Extracted graph (append-only)
    "nodes": List[Node],                        # Extracted entities
    "edges": List[Edge],                        # Extracted relationships
    
    # Processing options
    "extract_pdf_images": bool,                 # Extract images from PDFs
    "use_vision_extraction": bool,              # Vision model text extraction
    "section_chunking": bool,                   # Section-based chunking
    
    # Vector store config
    "vector_store_provider": Optional[str],     # "chroma" or "qdrant"
    "vector_store_configs": List[VectorStoreConfig],  # Multi-retriever
    
    # Database config
    "neo4j_uri": str,
    "neo4j_username": str,
    "neo4j_password": str,
    "neo4j_database": str,
    
    # LLM config
    "max_tokens": int,                          # LLM output max tokens
    "max_tokens_per_segment": int,              # Document chunk size
    "temperature": float,
    
    # Logging
    "log_level": str,                           # DEBUG, INFO, WARNING, ERROR
    
    # Output
    "messages": List[str],                      # Log messages (append-only)
    "filter_stats": dict,                       # Filtering statistics
    "output_json_path": str,                    # Output file path
}
```

### RAGContext Class

```python
{
    "ontology_node_types": List[str],           # Allowed node types
    "ontology_edge_types": List[str],           # Allowed edge types
    "wikidata_context": Dict[str, Dict],        # Wikidata entity data
    "retrieval_results": List[RetrievalResult], # Multi-retriever results
}
```

### Node Class (Pydantic)

```python
{
    "node_id": str,                             # Canonical unique key (English name)
    "node_type": str,                           # Entity type (Person, Organization)
    "description": Optional[str],               # Optional description
    "attributes": Dict[str, Any],               # Additional properties
}
```

### Edge Class (Pydantic)

```python
{
    "source_id": str,                           # Source node_id
    "target_id": str,                           # Target node_id
    "edge_type": str,                           # Relationship type
    "attributes": Dict[str, Any],               # Edge properties
}
```

---

## Common Patterns

### Extract, Load, Query Workflow

```python
manager = WorkflowManager(config)

# Step 1: Extract
extract_result = manager.kg_extract(file_path="doc.pdf")
print(f"Extracted {len(extract_result['nodes'])} nodes")

# Step 2: Load to Neo4j
load_result = manager.kg_load_json(
    json_file=extract_result['output_json_path']
)

# Step 3: Query
query_result = manager.kg_query(question="What are the entities?")
print(query_result['answer'])
```

### Multi-file Extraction

```bash
# Extract all PDFs in directory
for file in *.pdf; do
    graphaide extract "$file" --ontology ontology.ttl
done

# Load all generated JSON files
graphaide kg-load-json GraphAide_KG_Extract_*.json
```

### Vision-enabled Multimodal Ingestion

```python
manager.kg_ingest(
    file_path="document.pdf",
    extract_pdf_images=True,
    image_file_paths=["diagram.png"],
    use_vision_extraction=True,
    vector_store_provider="qdrant"
)
```

---

## Troubleshooting Reference

| Issue | Solution |
|-------|----------|
| No LLM provider configured | Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. in `.env` |
| Cannot connect to Neo4j | Verify `NEO4J_URI`, credentials, and Neo4j is running |
| "Vector store error" | Clear store: `rm -rf ./chroma_data` or `./qdrant_data` |
| Slow extraction | Use `--max-tokens-per-segment 1024` to reduce chunk size |
| Memory issues | Reduce batch size or use Qdrant instead of ChromaDB |
| Vision extraction failing | Ensure model supports vision (GPT-4o, Claude 3.5+) and API key is set |
| Markdown not recognized | File already supported as `.md`, treated as plain text |

---

**For more details, see QUICKSTART.md and ARCHITECTURE.md**
