# Configuration

Learn how to configure GraphAide for your specific needs.

## Basic Configuration

### Minimal Setup

```python
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key="sk-..."
    )
)
```

This uses defaults for Neo4j (localhost:7687) and vector storage.

## LLM Configuration

### Supported Providers

| Provider | Models | Setup |
|----------|--------|-------|
| **OpenAI** | gpt-4o, gpt-4o-mini | Requires API key |
| **Anthropic** | claude-3-5-sonnet | Requires API key |
| **Google** | gemini-pro | Requires API key |
| **AWS Bedrock** | claude, llama | Requires AWS credentials |
| **LM Studio** | Local models | Requires running server |

### OpenAI Configuration

```python
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key="sk-your-key-here",
        temperature=0.7,
        max_output_tokens_limit_llm=16000
    )
)
```

### Anthropic Configuration

```python
model_config=ModelConfig(
    provider="anthropic",
    model_name="claude-3-5-sonnet",
    api_key="sk-ant-...",
    temperature=0.5
)
```

### Local Model with LM Studio

```python
model_config=ModelConfig(
    provider="lmstudio",
    model_name="google/gemma-3-27b:2",
    temperature=0.7,
    base_url="http://localhost:1234/v1"
)
```

## Graph Database Configuration

### Default Neo4j (localhost)

```python
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="sk-...")
    # No graphdb_config needed - uses localhost:7687 with neo4j:password
)
```

### Custom Neo4j Server

```python
from graphaide import GraphAide, ModelConfig, GraphDBConfig

graphaide = GraphAide(
    model_config=ModelConfig(...),
    graphdb_config=GraphDBConfig(
        uri="neo4j://production-server:7687",
        username="neo4j",
        password="your-password"
    )
)
```

### Neo4j Cloud

```python
graphdb_config=GraphDBConfig(
    uri="neo4j+s://your-instance.databases.neo4j.io",
    username="neo4j",
    password="your-password"
)
```

## Vector Database Configuration

### ChromaDB (Default)

```python
from graphaide import GraphAide, VectorDBConfig

graphaide = GraphAide(
    model_config=ModelConfig(...),
    vectordb_config=VectorDBConfig(
        provider="chromadb",
        path="/path/to/chroma"
    )
)
```

### Qdrant (Remote)

```python
vectordb_config=VectorDBConfig(
    provider="qdrant",
    url="http://localhost:6333",
    api_key="optional-key"
)
```

### Qdrant (In-Memory)

```python
vectordb_config=VectorDBConfig(
    provider="qdrant",
    path=":memory:"
)
```

## Embedding Model Configuration

### OpenAI Embeddings

```python
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-4o",
        embedding_model="text-embedding-3-small",
        api_key="sk-..."
    )
)
```

### Sentence Transformers (Local)

```python
model_config=ModelConfig(
    provider="openai",
    model_name="gpt-4o",
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    api_key="sk-..."
)
```

### AWS Bedrock Embeddings

```python
model_config=ModelConfig(
    provider="bedrock",
    model_name="anthropic.claude-3-5-sonnet",
    embedding_model="amazon.titan-embed-text-v1"
)
```

## Advanced Configuration

### Context Window Size

Control how much text is processed per segment:

```python
result = graphaide.extract(
    file_path="document.pdf",
    max_tokens_per_segment=8192,  # Options: 4096, 8192, 16384, 32768
    context_window_mode="medium"
)
```

**Presets:**
- `small` (4096) — For resource-limited deployments
- `medium` (8192) — Balanced, supports richer context
- `large` (16384) — For models like GPT-4 and Claude 3
- `xlarge` (32768) — For cutting-edge models with massive windows

### Temperature Settings

Control randomness in LLM responses:

```python
ModelConfig(
    temperature=0.3   # More deterministic, best for extraction
    # temperature=0.7   # More creative, for reasoning tasks
    # temperature=0.0   # Most deterministic
)
```

### Output Tokens Limit

Set maximum output tokens for LLM responses:

```python
ModelConfig(
    max_output_tokens_limit_llm=16000  # Adjust based on your needs
)
```

## Environment Variables

Set configuration via environment variables:

```bash
# .env file
OPENAI_API_KEY=sk-...
GRAPHAIDE_NEO4J_URI=neo4j://localhost:7687
GRAPHAIDE_NEO4J_USER=neo4j
GRAPHAIDE_NEO4J_PASSWORD=password
```

Then load in code:

```python
import os
from dotenv import load_dotenv

load_dotenv()

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        api_key=os.getenv("OPENAI_API_KEY")
    )
)
```

## Complete Example

```python
from graphaide import (
    GraphAide,
    ModelConfig,
    GraphDBConfig,
    VectorDBConfig
)

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key="sk-...",
        embedding_model="text-embedding-3-small",
        temperature=0.3,
        max_output_tokens_limit_llm=16000
    ),
    graphdb_config=GraphDBConfig(
        uri="neo4j://localhost:7687",
        username="neo4j",
        password="password"
    ),
    vectordb_config=VectorDBConfig(
        provider="chromadb",
        path="./chroma"
    )
)
```

## Next Steps

- **[Extract Knowledge Graphs](../extraction/)** — Use your configuration for extraction
- **[Configure Vector Stores](../vector-stores/setup.md)** — Set up advanced retrieval
- **[See Examples](../resources.md)** — Learn from real-world examples
