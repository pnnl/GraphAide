# Knowledge Graph Extraction

Learn how to automatically extract entities and relationships from your documents.

## What is Extraction?

Extraction is the process of analyzing a document and identifying:

- **Entities** — Things like people, organizations, locations, concepts
- **Relationships** — Connections between entities (e.g., "works for", "located in")

GraphAide uses LLMs to understand document context and extract this structured information.

## Quick Start: Extract from a PDF

### Simplest Example

```python
from graphaide import GraphAide, ModelConfig, get_sample_data_path

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-5.6-luna",
        api_key="..."
    )
)

# Extract entities and relationships
result = graphaide.extract(file_path="document.pdf")

print(f"Found {len(result.nodes)} entities")
print(f"Found {len(result.edges)} relationships")

# View extracted data
for node in result.nodes:
    print(f"- {node.label}: {node.properties}")
```

### With Sample Data

```python
from graphaide import get_sample_data_path

sample_pdf = get_sample_data_path("PNNL_About.pdf")
sample_ontology = get_sample_data_path("ontology_cyber.nt")

result = graphaide.extract(
    file_path=sample_pdf,
    ontology_path=sample_ontology
)
```

## Input Formats

GraphAide can extract from multiple input types:

### From a File

```python
result = graphaide.extract(file_path="document.pdf")
# or .txt, .docx, .md, etc.
```

### From Text String

```python
text = """
GraphAide is developed by Sumit Purohit at PNNL.
It extracts knowledge from documents and loads it into Neo4j.
"""

result = graphaide.extract(input_text=text)
```

### From Multiple Files (JSONL)

For batch processing multiple documents:

```python
# Create JSONL file: one JSON object per line
# {"text": "Document content here"}
# {"text": "Another document"}

result = graphaide.extract(
    jsonl_file_path="documents.jsonl",
    jsonl_field_name="text",
    jsonl_lines_per_batch=4
)
```

## Output: Understanding Results

### Access Extracted Data

```python
result = graphaide.extract(file_path="document.pdf")

# Nodes (entities)
for node in result.nodes:
    print(f"Type: {node.type}")
    print(f"Label: {node.label}")
    print(f"Properties: {node.properties}")

# Edges (relationships)
for edge in result.edges:
    print(f"Relationship: {edge.type}")
    print(f"From: {edge.source} → To: {edge.target}")
    print(f"Properties: {edge.properties}")
```

### Save Results to JSON

```python
result = graphaide.extract(file_path="document.pdf")

# Results are automatically saved to:
# GraphAide_KG_Extract_YYYYMMDD_HHMMSS.json
```

## Advanced Options

### Control Context Window

```python
result = graphaide.extract(
    file_path="document.pdf",
    max_tokens_per_segment=8192,
    context_window_mode="large"
)
```

### Filter by Ontology

Keep only entities and relationships that match your ontology:

```python
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.nt",
    filter_by_ontology=True  # Only keep types defined in ontology
)
```

### Merge Results

Automatically deduplicate and consolidate extracted data:

```python
result = graphaide.extract(
    file_path="document.pdf",
    merge_output=True  # Combine duplicate entities
)
```

## Processing Steps

Here's what GraphAide does internally:

```
1. Load Document
   ↓
2. Split into Segments (chunks)
   ↓
3. For Each Segment:
   - Retrieve Context (from Vector Store/Ontology)
   - Send to LLM for Extraction
   - Parse Entities & Relationships
   ↓
4. Combine Results
   ↓
5. Save to JSON
```

## Common Extraction Patterns

### Business Documents

```python
result = graphaide.extract(
    file_path="contract.pdf",
    ontology_path="ontology_business.nt"
)
```

### Scientific Papers

```python
result = graphaide.extract(
    file_path="research_paper.pdf",
    ontology_path="ontology_science.nt",
    filter_by_ontology=True
)
```

### Internal Documentation

```python
result = graphaide.extract(
    file_path="procedure.txt",
    merge_output=True  # Deduplicate for cleaner results
)
```

## Next Steps

- **[Use Ontologies](ontology.md)** — Guide extraction with domain knowledge
- **[Ingest to Neo4j](../ingestion/)** — Load extracted data into a graph database
- **[Vector Store RAG](../vector-stores/usage.md)** — Enhance with semantic search
