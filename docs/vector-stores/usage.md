# Using Vector Stores in Extraction

Learn how to enhance extraction with semantic search from vector stores.

## Why Use Vector Stores in Extraction?

During extraction, GraphAide can automatically retrieve relevant context from your vector store:

- **Better Decisions** — LLM sees related entities and patterns
- **Consistency** — Extracted entities match existing ones in your knowledge base
- **Efficiency** — No need to manually provide context
- **Scale** — Handle thousands of documents automatically

## Single Vector Store Retrieval

### Basic Usage

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig

# First, load documents into vector store
graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="..."),
    vectordb_config=VectorDBConfig(provider="chromadb", path="./chroma")
)

# Load your knowledge base
graphaide.ingest_to_vectordb(
    file_paths=["knowledge_base.pdf"],
    split_docs=True
)

# Now extract from new documents, using knowledge base for context
result = graphaide.extract(
    file_path="new_document.pdf",
    # Vector store is automatically used for context retrieval
)

print(f"Extracted with context: {len(result.nodes)} entities")
```

### Specify Vector Store Behavior

```python
from graphaide.workflows.schemas import VectorStoreConfig

result = graphaide.extract(
    file_path="document.pdf",
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./chroma",
            collection_name="documents",
            retrieve_type="entities",  # Retrieve similar entities
            description="Entity knowledge base"
        )
    ]
)
```

## Multi-Retriever RAG

Use **multiple vector stores** simultaneously for richer context.

### Example: Entity + Document Retrieval

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig
from graphaide.workflows.schemas import VectorStoreConfig

# Setup GraphAide
graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="..."),
    vectordb_config=VectorDBConfig(provider="chromadb", path="./chroma")
)

# Load knowledge bases
# Store 1: Entities and patterns
graphaide.ingest_to_vectordb(
    file_paths=["entities_reference.pdf"],
    split_docs=True
)

# Extract with multi-retriever (would need separate stores setup)
result = graphaide.extract(
    file_path="document.pdf",
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./chroma_entities",
            collection_name="entities",
            retrieve_type="entities",
            description="Entity patterns and known entities"
        ),
        VectorStoreConfig(
            type="chromadb",
            path="./chroma_docs",
            collection_name="documents",
            retrieve_type="documents",
            description="Related documents for context"
        )
    ]
)
```

## Retrieval Types

Control what kind of context is retrieved:

### Entity Retrieval

Retrieves similar entities from your knowledge base:

```python
VectorStoreConfig(
    type="chromadb",
    path="./chroma",
    retrieve_type="entities"  # Find similar entities
)
```

### Document Retrieval

Retrieves relevant document chunks:

```python
VectorStoreConfig(
    type="chromadb",
    path="./chroma",
    retrieve_type="documents"  # Find relevant passages
)
```

### Ontology Retrieval

Retrieves ontology type definitions:

```python
VectorStoreConfig(
    type="chromadb",
    path="./chroma",
    retrieve_type="ontology"  # Get type definitions
)
```

### Custom Retrieval

```python
VectorStoreConfig(
    type="chromadb",
    path="./chroma",
    retrieve_type="custom",
    description="Your custom retrieval logic"
)
```

## Complete Example: Extraction with Vector Store

### Step 1: Build Knowledge Base

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="..."),
    vectordb_config=VectorDBConfig(provider="chromadb", path="./kb")
)

# Load reference documents
print("Building knowledge base...")
result = graphaide.ingest_to_vectordb(
    file_paths=[
        "company_structure.pdf",
        "personnel_list.txt",
        "technology_stack.pdf"
    ],
    split_docs=True
)

print(f"Knowledge base ready: {result.chunks_created} chunks")
```

### Step 2: Extract from New Document with Context

```python
from graphaide.workflows.schemas import VectorStoreConfig

# Extract new document, using knowledge base for context
result = graphaide.extract(
    file_path="meeting_notes.pdf",
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./kb",
            collection_name="langchain",  # Default collection name
            retrieve_type="documents",
            description="Company knowledge base with context"
        )
    ]
)

print(f"Extracted: {len(result.nodes)} entities, {len(result.edges)} relationships")
```

### Step 3: Verify Results

```python
# Check if extraction used context effectively
for node in result.nodes[:5]:
    print(f"- {node.label} ({node.type})")
    if node.properties:
        print(f"  Properties: {node.properties}")
```

## Combining Vector Stores with Ontology

Use ontology + vector stores together for maximum guidance:

```python
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.nt",           # Define types
    vector_stores=[                         # Provide context
        VectorStoreConfig(
            type="chromadb",
            path="./chroma",
            retrieve_type="entities",
            description="Known entities matching ontology"
        )
    ],
    filter_by_ontology=True                # Keep only ontology types
)
```

## Performance Considerations

### Control Retrieval Amount

```python
# More retrieval = slower but better context
VectorStoreConfig(
    type="chromadb",
    path="./chroma",
    retrieve_type="documents",
    description="Full document context"  # Larger chunks retrieved
)

# Less retrieval = faster but less context
VectorStoreConfig(
    type="chromadb",
    path="./chroma",
    retrieve_type="entities",
    description="Just entity mentions"  # Smaller, focused retrieval
)
```

### Batch Processing with Vector Stores

```python
from pathlib import Path

# Process multiple documents
docs = list(Path("documents").glob("*.pdf"))

for doc in docs:
    print(f"Processing {doc.name}...")
    
    result = graphaide.extract(
        file_path=str(doc),
        vector_stores=[
            VectorStoreConfig(
                type="chromadb",
                path="./kb",
                retrieve_type="documents"
            )
        ]
    )
    
    print(f"  → {len(result.nodes)} entities extracted")
```

## Common Patterns

### Incremental Learning

```python
# Start with core knowledge base
graphaide.ingest_to_vectordb(
    file_paths=["core_data.pdf"],
    append=False
)

# Extract from document, learning from core
result1 = graphaide.extract(
    file_path="doc1.pdf",
    vector_stores=[...]
)

# Add learned entities back to knowledge base
graphaide.ingest_to_vectordb(
    file_paths=["extracted_entities.json"],
    append=True  # Add to existing knowledge base
)

# Extract next document with richer context
result2 = graphaide.extract(
    file_path="doc2.pdf",
    vector_stores=[...]  # Now has more context
)
```

### Domain-Specific Retrieval

```python
# For cybersecurity: retrieve threat patterns
security_result = graphaide.extract(
    file_path="threat_report.pdf",
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./security_patterns",
            retrieve_type="entities",
            description="Known malware, CVEs, attack patterns"
        )
    ]
)

# For business: retrieve organizational context
business_result = graphaide.extract(
    file_path="news.txt",
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./org_structure",
            retrieve_type="documents",
            description="Company organization, people, products"
        )
    ]
)
```

## Troubleshooting

### Vector Store Not Being Used

```python
# Verify vector store exists and has data
result = graphaide.ingest_to_vectordb(
    file_paths=["knowledge.pdf"],
    split_docs=True
)

# Check it was created
print(f"Created {result.chunks_created} chunks")

# Then extract with explicit config
result = graphaide.extract(
    file_path="document.pdf",
    vector_stores=[
        VectorStoreConfig(
            type="chromadb",
            path="./chroma",
            retrieve_type="documents"
        )
    ]
)
```

### Slow Extraction with Vector Stores

```python
# Reduce retrieval scope
VectorStoreConfig(
    type="chromadb",
    path="./chroma",
    retrieve_type="entities",  # Smaller than "documents"
    description="Just entity mentions"
)

# Or reduce context window
result = graphaide.extract(
    file_path="document.pdf",
    max_tokens_per_segment=4096  # Smaller chunks
)
```

### Inconsistent Results

Vector store retrieval may return different results for similar queries. To improve consistency:

```python
# Use ontology + vector stores together
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.nt",        # Constraints
    vector_stores=[VectorStoreConfig(   # Examples
        type="chromadb",
        path="./chroma",
        retrieve_type="entities"
    )]
)
```

## Next Steps

- **[Advanced Configuration](../configuration/)** — Tune retrieval parameters
- **[Query Your Graph](../resources.md)** — Analyze extracted results
- **[Batch Processing](../ingestion/)** — Process many documents
