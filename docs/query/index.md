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

answer = graphaide.query("What organizations are mentioned?")
print(answer)
```

## Query Examples

### Entity Queries

```python
# Find all people
answer = graphaide.query("Who are all the people mentioned?")

# Find specific relationships
answer = graphaide.query("What companies does John Smith work for?")

# Find connected entities
answer = graphaide.query("What projects are associated with AI research?")
```

### Relationship Queries

```python
# Explore relationships
answer = graphaide.query("What relationships exist between companies and technologies?")

# Find connections
answer = graphaide.query("How are cybersecurity concepts connected?")

# Path finding
answer = graphaide.query("What's the connection between AI and natural language processing?")
```

### Aggregation Queries

```python
# Count entities
answer = graphaide.query("How many different organizations are in the knowledge graph?")

# List operations
answer = graphaide.query("List all the technologies mentioned and their uses")

# Statistical queries
answer = graphaide.query("What are the most frequently mentioned concepts?")
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
answer = graphaide.query("What specific technologies are mentioned for cybersecurity?")
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
doc_count = graphaide._get_vector_store_doc_count() if graphaide.vector_configs else "N/A"
print(f"Documents in vector store: {doc_count}")

# Try a simpler query
answer = graphaide.query("What entities are in the graph?")
```

### Query Execution Errors

```python
# Enable debug logging to see detailed execution
answer = graphaide.query(
    "Your question here?",
    log_level="DEBUG"
)
```

## Next Steps

- **[Build Vector Stores](../vector-stores/setup.md)** — Add semantic search context
- **[Visualize Embeddings](../vector-stores/setup.md#visualizing-vector-embeddings)** — See 2D projections of your data
- **[See More Examples](../resources.md)** — Explore real-world use cases
