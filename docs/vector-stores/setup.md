# Setting Up Vector Stores

Learn how to load documents into vector stores for semantic retrieval during extraction.

## What is a Vector Store?

A vector store stores document chunks as embeddings (numerical representations). During extraction, it retrieves semantically relevant context to help the LLM make better decisions.

**Why use it?** Instead of sending the entire document, GraphAide can find the most relevant parts automatically.

## Supported Vector Stores

| Store | Type | Best For |
|-------|------|----------|
| **ChromaDB** | File-based | Local development, quick setup |
| **Qdrant** | Remote/In-memory | Production, distributed systems |

## Quick Start: ChromaDB

### Load Documents into ChromaDB

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key="..."
    ),
    vectordb_config=VectorDBConfig(
        provider="chromadb",
        path="./chroma"
    )
)

# Load documents into vector store
result = graphaide.ingest_to_vectordb(
    file_paths=["document1.pdf", "document2.pdf"],
    split_docs=True,
    append=False  # Replace existing, or True to add
)

print(f"✓ Loaded {result.documents_loaded} documents")
print(f"✓ Created {result.chunks_created} chunks")
```

## ChromaDB Setup

### Default Configuration (Recommended)

```python
VectorDBConfig(
    provider="chromadb",
    path="./chroma"  # Stores in local folder
)
```

### Persistent Storage

```python
VectorDBConfig(
    provider="chromadb",
    path="/data/chroma",  # Survives restarts
    collection_name="documents"
)
```

### In-Memory (Temporary)

```python
VectorDBConfig(
    provider="chromadb",
    path=":memory:"  # Cleared on exit
)
```

## Qdrant Setup

### Remote Qdrant Server

```python
VectorDBConfig(
    provider="qdrant",
    url="http://localhost:6333",
    collection_name="documents"
)
```

### With API Key

```python
VectorDBConfig(
    provider="qdrant",
    url="http://qdrant-server:6333",
    api_key="your-api-key",
    collection_name="documents"
)
```

### In-Memory Qdrant

```python
VectorDBConfig(
    provider="qdrant",
    path=":memory:"  # Temporary, in-process
)
```

## Loading Documents

### Single Document

```python
result = graphaide.ingest_to_vectordb(
    file_paths=["document.pdf"],
    split_docs=True
)
```

### Multiple Documents

```python
result = graphaide.ingest_to_vectordb(
    file_paths=[
        "report1.pdf",
        "report2.pdf",
        "guidelines.txt"
    ],
    split_docs=True,
    append=True  # Add to existing collection
)
```

### From Text

```python
# Convert text to file first, or use extraction workflow
from pathlib import Path

# Write text to temporary file
text = "Your document content here..."
text_file = Path("temp.txt")
text_file.write_text(text)

result = graphaide.ingest_to_vectordb(
    file_paths=[str(text_file)],
    split_docs=True
)
```

## Document Splitting Options

### Default Splitting

```python
result = graphaide.ingest_to_vectordb(
    file_paths=["document.pdf"],
    split_docs=True   # Auto-split into chunks
)
```

### Without Splitting

```python
result = graphaide.ingest_to_vectordb(
    file_paths=["small_document.txt"],
    split_docs=False  # Store entire document as-is
)
```

## Managing Collections

### Create Multiple Collections

```python
# Collection 1: Domain documentation
result1 = graphaide.ingest_to_vectordb(
    file_paths=["guide1.pdf", "guide2.pdf"],
)

# Collection 2: Reference material
result2 = graphaide.ingest_to_vectordb(
    file_paths=["reference.pdf"],
)
```

### Clear and Reload

```python
# Clear existing
result = graphaide.ingest_to_vectordb(
    file_paths=["new_documents.pdf"],
    append=False  # Replace everything
)
```

### Keep and Append

```python
# Add more documents
result = graphaide.ingest_to_vectordb(
    file_paths=["additional.pdf"],
    append=True  # Add to existing
)
```

## Embedding Models

Embeddings convert text into vectors. GraphAide supports:

### OpenAI Embeddings (Recommended)

```python
ModelConfig(
    provider="openai",
    model_name="gpt-4o",
    embedding_model="text-embedding-3-small",
    api_key="..."
)
```

### Sentence Transformers (Local)

```python
ModelConfig(
    provider="openai",
    model_name="gpt-4o",
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    api_key="..."
)
```

### AWS Bedrock Embeddings

```python
ModelConfig(
    provider="bedrock",
    model_name="anthropic.claude-3-5-sonnet",
    embedding_model="amazon.titan-embed-text-v1"
)
```

## Common Workflows

### Build a Knowledge Base

```python
from pathlib import Path
from graphaide import GraphAide, ModelConfig, VectorDBConfig

# Setup
graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="..."),
    vectordb_config=VectorDBConfig(provider="chromadb", path="./knowledge_base")
)

# Load all PDFs from folder
docs_folder = Path("documents")
pdf_files = list(docs_folder.glob("*.pdf"))

result = graphaide.ingest_to_vectordb(
    file_paths=[str(f) for f in pdf_files],
    split_docs=True,
    append=False  # Start fresh
)

print(f"Knowledge base ready: {result.documents_loaded} documents, {result.chunks_created} chunks")
```

### Incremental Updates

```python
# Initial load
graphaide.ingest_to_vectordb(
    file_paths=["doc1.pdf", "doc2.pdf"],
    append=False
)

# Later: add new documents
graphaide.ingest_to_vectordb(
    file_paths=["doc3.pdf"],
    append=True  # Keep existing, add new
)
```

### Production Setup

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-4o",
        embedding_model="text-embedding-3-small",
        api_key="..."
    ),
    vectordb_config=VectorDBConfig(
        provider="qdrant",
        url="http://qdrant-prod:6333",
        api_key="prod-key",
        collection_name="prod-knowledge"
    )
)

# Load documents
result = graphaide.ingest_to_vectordb(
    file_paths=get_all_documents(),
    split_docs=True,
    append=False
)
```

## Troubleshooting

### ChromaDB Connection Issues

```python
# Check path exists
import os
os.makedirs("./chroma", exist_ok=True)

# Or use absolute path
VectorDBConfig(
    provider="chromadb",
    path="/absolute/path/to/chroma"
)
```

### Qdrant Connection Failed

```bash
# Start Qdrant server
docker run -p 6333:6333 qdrant/qdrant:latest
```

Then configure:
```python
VectorDBConfig(
    provider="qdrant",
    url="http://localhost:6333"
)
```

### Embedding Model Errors

```python
# Verify API key and model name
ModelConfig(
    provider="openai",
    embedding_model="text-embedding-3-small",  # Valid model
    api_key="..."  # Valid key
)
```

## Next Steps

- **[Use Vector Stores in Extraction](usage.md)** — Enhance extraction with retrieval
- **[Configure Multiple Vector Stores](usage.md#multi-retriever-rag)** — Advanced retrieval
- **[Query Your Knowledge Base](../resources.md)** — See what's possible
