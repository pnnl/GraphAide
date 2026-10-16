# Installation

Get GraphAide running in minutes. Choose the method that works best for you.

## System Requirements

- **Python:** 3.11 or later
- **Neo4j:** 4.4 or later (optional for basic usage)
- **LLM API:** OpenAI, Anthropic, Google, or AWS Bedrock account

## Setup Virtual Environment (Recommended)

Before installing GraphAide, create an isolated environment to manage dependencies:

**Option 1: Using uv (Fastest)** ⚡
```bash
uv venv graphaide-env
# On macOS/Linux:
source graphaide-env/bin/activate
# On Windows:
graphaide-env\Scripts\activate
```

**Option 2: Using Conda**
```bash
conda create -n graphaide python=3.12
conda activate graphaide
```

## Method 1: uv (Recommended for Speed)

The **fastest** way to install GraphAide. We recommend `uv` for significantly faster dependency resolution:

```bash
uv pip install graphaide
```

Verify installation:

```bash
graphaide --version
```

## Method 2: pip

Standard Python package manager approach:

```bash
pip install graphaide
```

Verify installation:

```bash
graphaide --version
```

## Method 3: Using GraphAide as a Python Library

Use GraphAide programmatically in your Python code.

```python
from graphaide import GraphAide, ModelConfig

graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai",
        model_name="gpt-5.6-luna",
        api_key="..."
    )
)

# Use GraphAide functions
result = graphaide.extract(file_path="document.pdf")
```

## Method 4: Docker

Run GraphAide in a containerized environment with all dependencies included.

```bash
git clone https://github.com/pnnl/GraphAide.git
cd GraphAide
docker compose up
```

Then access the REST API at `http://localhost:8000`.

## Method 5: Development Setup

For developers who want to contribute or modify GraphAide.

**With uv (recommended):**
```bash
git clone https://github.com/pnnl/GraphAide.git
cd GraphAide
uv venv
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
uv pip install -e ".[testing]"
```

**Or with pip:**
```bash
git clone https://github.com/pnnl/GraphAide.git
cd GraphAide
pip install -e ".[testing]"
```

## Next Steps

1. **[Configure GraphAide](../configuration/)** — Set up your LLM and databases
2. **[Extract Your First Knowledge Graph](../extraction/)** — Learn extraction basics
3. **[Explore Examples](../resources.md)** — See what's possible

## Troubleshooting

### Module not found error

If you get `ModuleNotFoundError: No module named 'graphgen'`:

```bash
# Reinstall in development mode
pip install -e .
```

### Neo4j connection error

If GraphAide can't connect to Neo4j, check:

```bash
# Neo4j should be running on default port 7687
neo4j-shell -u neo4j -p password
```

### LLM API errors

Ensure your API key is valid and has quota:

```python
from graphaide import ModelConfig

config = ModelConfig(
    provider="openai",
    model_name="gpt-5.6-luna",
    api_key="sk-your-key-here"
)
# Test connection during GraphAide initialization
graphaide = GraphAide(model_config=config)
```

**Need help?** See [Resources](../resources.md) or check [GitHub Issues](https://github.com/pnnl/GraphAide/issues).
