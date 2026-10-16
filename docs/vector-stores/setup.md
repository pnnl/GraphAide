# Setting Up Vector Stores

Learn how to load documents into vector stores for semantic retrieval during extraction.

## What is a Vector Store?

A vector store stores document chunks as embeddings (numerical representations). During extraction, it retrieves semantically relevant context to help the LLM make better decisions.

**Why use it?** Instead of sending the entire document, GraphAide can find the most relevant parts automatically.

## Quick Start: ChromaDB with Sample Data

### Load Sample Documents into ChromaDB

```python
from pathlib import Path
from graphaide import GraphAide, ModelConfig, VectorDBConfig, get_sample_data_path

# Setup LLM
model_config = ModelConfig(
    provider="openai",
    model_name="gpt-5.6-luna",
    api_key="..."
)

# Setup ChromaDB vector store with GVD name in home directory
home = Path.home()
vectordb_config = VectorDBConfig(
    provider="chromadb",
    store_name="GVD",
    store_path=home / "GVD"
)

graphaide = GraphAide(
    model_config=model_config,
    vectordb_config=vectordb_config
)

# Load sample documents into vector store
cyber_file = get_sample_data_path("cyberkg.txt")
pdf_file = get_sample_data_path("PNNL_About.pdf")

result = graphaide.ingest_vectors(
    file_paths=[str(cyber_file), str(pdf_file)],
    split_docs=True,
    append=False
)
```


### Visualizing Vector Embeddings

After loading documents into your vector store, you can inspect the vector space and create 2D visualizations using UMAP (Uniform Manifold Approximation and Projection).

#### Check Document Count and Visualize

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig, get_sample_data_path
from pathlib import Path

# Check how many documents are stored
doc_count = graphaide._get_vector_store_doc_count()
print(f"✓ Vector store contains {doc_count} documents")

# Create 2D UMAP projection and interactive visualization
viz_result = graphaide.project_vectors(
    output_dir="./visualizations",
    reuse_embedding=False,  # Compute new projection
    category_field="source"  # Color points by source document
)

print(f"✓ Projected {viz_result.stats['num_embeddings_projected']} embeddings")
print(f"✓ Visualization saved to: {viz_result.stats['visualization_image_path']}")
```

#### Reuse Existing Projections

If you've already created a 2D projection and want to recreate the visualization with different settings:

```python
# Reuse previous UMAP projection (faster, no recomputation)
viz_result = graphaide.project_vectors(
    output_dir="./visualizations",
    reuse_embedding=True,  # Skip UMAP, reuse .npy file
    save_png=True,  # Save as static PNG image
    category_field="metadata_filter"  # Different coloring
)
```

The visualization is interactive—hover over points to see metadata, zoom, pan, and toggle categories.

## ChromaDB Configuration

### With Store Name and Path (Recommended)

```python
from pathlib import Path

home = Path.home()
VectorDBConfig(
    provider="chromadb",
    store_name="GVD",
    store_path=home / "GVD"
)
```

### Default Configuration

```python
VectorDBConfig(
    provider="chromadb",
    store_name="default",
    store_path="./chroma"
)
```

### In-Memory (Temporary)

```python
VectorDBConfig(
    provider="chromadb",
    store_name="temp",
    store_path=":memory:"  # Cleared on exit
)
```

## Loading Documents

### Load Sample Data

```python
from graphaide import get_sample_data_path

# Get sample files
cyber_file = get_sample_data_path("cyberkg.txt")
pdf_file = get_sample_data_path("PNNL_About.pdf")

# Load into vector store
result = graphaide.ingest_vectors(
    file_paths=[str(cyber_file), str(pdf_file)],
    split_docs=True
)
```

### Load Your Own Documents

```python
result = graphaide.ingest_vectors(
    file_paths=["document1.pdf", "document2.pdf"],
    split_docs=True,
    append=False  # Replace existing, or True to add
)
```

### From Text

```python
from pathlib import Path

# Write text to temporary file
text = "Your document content here..."
text_file = Path("temp.txt")
text_file.write_text(text)

result = graphaide.ingest_vectors(
    file_paths=[str(text_file)],
    split_docs=True
)
```

## Document Splitting Options

### Default Splitting (Recommended)

```python
result = graphaide.ingest_vectors(
    file_paths=["document.pdf"],
    split_docs=True   # Auto-split into chunks
)
```

### Without Splitting

```python
result = graphaide.ingest_vectors(
    file_paths=["small_document.txt"],
    split_docs=False  # Store entire document as-is
)
```

## Managing Vector Stores

### Create Multiple Named Stores

```python
from pathlib import Path

home = Path.home()

# Store 1: Cybersecurity knowledge (GVD)
gvd_config = VectorDBConfig(
    store_name="GVD",
    store_path=home / "GVD"
)

# Store 2: General knowledge
general_config = VectorDBConfig(
    store_name="general",
    store_path=home / "general"
)

# Load different data into each
graphaide1 = GraphAide(..., vectordb_config=gvd_config)
graphaide1.ingest_vectors(
    file_paths=[get_sample_data_path("cyberkg.txt")],
    append=False
)

graphaide2 = GraphAide(..., vectordb_config=general_config)
graphaide2.ingest_vectors(
    file_paths=[get_sample_data_path("PNNL_About.pdf")],
    append=False
)
```

### Clear and Reload

```python
# Replace all documents (append=False)
result = graphaide.ingest_vectors(
    file_paths=["new_documents.pdf"],
    append=False
)
```

### Keep and Append

```python
# Add more documents to existing store
result = graphaide.ingest_vectors(
    file_paths=["additional.pdf"],
    append=True
)
```

## Embedding Models

Embeddings convert text into vectors. GraphAide supports:

### OpenAI Embeddings (Recommended)

```python
ModelConfig(
    provider="openai",
    model_name="gpt-5.6-luna",
    embedding_model="text-embedding-3-small",
    api_key="..."
)
```

### Sentence Transformers (Local)

```python
ModelConfig(
    provider="openai",
    model_name="gpt-5.6-luna",
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

### Build a Knowledge Base with Named Store

```python
from pathlib import Path
from graphaide import GraphAide, ModelConfig, VectorDBConfig, get_sample_data_path

home = Path.home()

# Setup with named GVD store
graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-5.6-luna", api_key="..."),
    vectordb_config=VectorDBConfig(
        provider="chromadb",
        store_name="GVD",
        store_path=home / "GVD"
    )
)

# Load sample data
cyber_file = get_sample_data_path("cyberkg.txt")
pdf_file = get_sample_data_path("PNNL_About.pdf")

result = graphaide.ingest_vectors(
    file_paths=[str(cyber_file), str(pdf_file)],
    split_docs=True,
    append=False
)
```

### Incremental Updates

```python
# Initial load
graphaide.ingest_vectors(
    file_paths=["doc1.pdf", "doc2.pdf"],
    append=False
)

# Later: add new documents
graphaide.ingest_vectors(
    file_paths=["doc3.pdf"],
    append=True  # Keep existing, add new
)
```


## Troubleshooting

### ChromaDB Connection Issues

```python
from pathlib import Path

home = Path.home()
store_path = home / "GVD"

# Ensure directory exists
store_path.mkdir(parents=True, exist_ok=True)

VectorDBConfig(
    store_name="GVD",
    store_path=store_path
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

### Out of Memory with Large Documents

```python
# Split into smaller batches
result = graphaide.ingest_vectors(
    file_paths=["large_document.pdf"],
    split_docs=True,  # Enables chunking
    append=True  # Add incrementally
)
```

## Next Steps

- **[Use Vector Stores in Extraction](usage.md)** — Enhance extraction with retrieval
- **[Query Your Knowledge Base](../resources.md)** — See what's possible
