# Querying Your Knowledge Graph

After ingesting data into Neo4j, query your knowledge graph using natural language with GraphAide.

## Quick Start: Query with GraphAide

### Using GraphAide Query

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig

# Setup
graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-5.6-luna",
        api_key="..."
    ),
    graphdb_config=GraphDBConfig(
        uri="neo4j://localhost:7687",
        username="neo4j",
        password="password"
    )
)

# Query your knowledge graph

result = graphaide.query("What organizations are mentioned?")
print(result.answer)
```

## Query Examples

### Entity Queries

```python
# Find all people
result = graphaide.query("Who are all the people mentioned?")
print(result.answer)

# Find specific relationships
result = graphaide.query("What companies does John Smith work for?")
print(result.answer)

# Find connected entities
result = graphaide.query("What projects are associated with AI research?")
print(result.answer)
```

### Relationship Queries

```python
# Explore relationships
result = graphaide.query("What relationships exist between companies and technologies?")
print(result.answer)

# Find connections
result = graphaide.query("How are cybersecurity concepts connected?")
print(result.answer)

# Path finding
result = graphaide.query("What's the connection between AI and natural language processing?")
print(result.answer)
```

### Aggregation Queries

```python
# Count entities
result = graphaide.query("How many different organizations are in the knowledge graph?")
print(result.answer)

# List operations
result = graphaide.query("List all the technologies mentioned and their uses")
print(result.answer)

# Statistical queries
result = graphaide.query("What are the most frequently mentioned concepts?")
print(result.answer)
```

## Query Parameters

The `query()` method accepts additional parameters:

```python
result = graphaide.query(
    question="What organizations are mentioned?",
    log_level="DEBUG"  # Optional: Set logging level
)
```

## Query Process

Here's what happens internally when you query:

```
1. Intent Prediction
   - Determine if query is subjective, locality-based, or analytical
   ↓
2. Neo4j Cypher Generation
   - Generate Cypher query from natural language
   ↓
3. Vector Store Context (RAG)
   - Retrieve relevant document context if configured
   ↓
4. Graph Query Execution
   - Execute Cypher against Neo4j
   ↓
5. LLM Response Generation
   - Generate natural language answer with context
   ↓
6. Return Answer
```

## Query with Vector Store Context

If you've configured a vector store, queries automatically retrieve relevant document context:

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig, VectorDBConfig

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-5.6-luna", api_key="..."),
    graphdb_config=GraphDBConfig(uri="neo4j://localhost:7687", username="neo4j", password="password"),
    vector_configs=VectorDBConfig(
        provider="chromadb",
        store_name="documents",
        store_path="./chroma"
    )
)

# Query now includes both graph data AND document context
result = graphaide.query("What specific technologies are mentioned for cybersecurity?")
print(result.answer)
```

## Understanding Query Results

The query result includes:

- **Answer**: Natural language response to your question
- **Context**: Relevant graph data and document passages
- **Confidence**: How well the answer is grounded in the data
- **Sources**: Where the information came from (nodes, documents)


## Troubleshooting

### No Results from Query

Check that:
1. Data has been successfully ingested to Neo4j
2. Neo4j connection is working
3. Query is specific enough (avoid overly broad questions)

```python
# Verify data exists
if graphaide.vector_configs:
    vector_config = graphaide.vector_configs if isinstance(graphaide.vector_configs, VectorDBConfig) else graphaide.vector_configs[0]
    doc_count = graphaide._get_vector_store_doc_count(vector_config)
else:
    doc_count = "N/A"
print(f"Documents in vector store: {doc_count}")

# Try a simpler query
result = graphaide.query("What entities are in the graph?")
print(result.answer)
```

### Query Execution Errors

```python
# Enable debug logging to see detailed execution
result = graphaide.query(
    "Your question here?",
    log_level="DEBUG"
)
print(result.answer)
```

## Next Steps

- **[Build Vector Stores](../vector-stores/setup.md)** — Add semantic search context
- **[Visualize Embeddings](../vector-stores/setup.md#visualizing-vector-embeddings)** — See 2D projections of your data
- **[See More Examples](../resources.md)** — Explore real-world use cases
