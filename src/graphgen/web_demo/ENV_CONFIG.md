# GraphAide Environment Configuration

## Single .env File for All Entry Points

All GraphAide interfaces use the **same .env file** and configuration loading.

### Where to Put `.env` File

GraphAide looks for `.env` in **multiple locations** (in this priority order):

1. **Current Working Directory** (where you run the command)
   ```
   ./.env
   ```
   Example:
   ```bash
   cd C:\my-project
   echo "OPENAI_API_KEY=sk-..." > .env
   graphaide extract document.pdf
   ```

2. **User Home Directory** (Recommended for pip installs)
   ```
   ~/.graphaide/.env
   ```
   Example (Windows PowerShell):
   ```powershell
   mkdir $HOME\.graphaide
   echo "OPENAI_API_KEY=sk-..." | Out-File $HOME\.graphaide\.env
   ```
   
   Example (Linux/Mac):
   ```bash
   mkdir -p ~/.graphaide
   echo "OPENAI_API_KEY=sk-..." > ~/.graphaide/.env
   ```

3. **User Home Directory** (Fallback)
   ```
   ~/.env
   ```

4. **GraphAide Repo Root** (Development only)
   ```
   C:\Users\puro755\localcode\GraphAideV2\graphaide\.env
   ```

### How Configuration Works

**Step 1: .env File (One Source of Truth)**
```bash
# .env (GraphAide root)
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...

# Observability - Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_DEBUG=true
OTEL_SERVICE_NAME=graphaide
LANGFUSE_SESSION_NAME=GraphAide-Development
LANGFUSE_ENVIRONMENT=development
```

**Step 2: Backend Loads .env**
```python
# src/graphgen/core.py (line 8-11)
from dotenv import load_dotenv
load_dotenv()  # Reads .env into os.environ
```

**Step 3: All Entry Points Use Same Config**

### CLI
```bash
graphaide extract document.pdf
```
- Imports from `graphgen.core`
- `load_dotenv()` already called
- Reads `os.environ['LANGFUSE_PUBLIC_KEY']` etc.

### Notebook
```python
from graphgen.core import extract_graph
result = extract_graph(file_path="document.pdf")
```
- Imports from `graphen.core`
- `load_dotenv()` already called
- Reads same env vars

### Web App (REST API)
```python
# src/graphgen/api.py
# Backend loads .env via core.py imports
# Web app calls /get-observability-config
# Backend returns os.environ values
```
- Backend (`api.py`) calls `core.py` functions
- `core.py` loads `.env` on import
- Web UI fetches config from `/get-observability-config`
- Frontend auto-populates UI fields

## Configuration Priority

**For all entry points, config is read in this order:**

1. **Environment Variables** (`.env` file)
   - Loaded by `core.py` at startup
   - Available in `os.environ`
   - Highest priority

2. **Config JSON** (optional)
   - `config.json` or `--config-path` flag
   - Merged with env vars
   - Overrides env defaults

3. **CLI Flags** (CLI only)
   - `--openai-api-key`, `--neo4j-uri`, etc.
   - Highest priority for CLI
   - Not available for web app/notebook

## Installation Methods and .env Location

### Method 1: Local Development (From Repo)
```bash
cd C:\Users\puro755\localcode\GraphAideV2\graphaide
# Put .env here:
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
EOF

# Run any command
graphaide extract document.pdf
```

### Method 2: Pip Install (Production)
```bash
pip install graphaide

# Create .env in home directory
mkdir ~/.graphaide
cat > ~/.graphaide/.env << 'EOF'
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
EOF

# Run from any directory
graphaide extract document.pdf
# or
graphaide serve --port 8000
```

### Method 3: Docker (With Volume)
```bash
docker run -v ~/.graphaide/.env:/root/.graphaide/.env graphaide
```

### Method 4: Project-Specific
```bash
# In your project directory
cd my-knowledge-graph-project
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
EOF

# Run from project directory
graphaide extract document.pdf
```

## .env Template

```bash
# ========== LLM Configuration ==========
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_NAME=gpt-4o
OPENAI_EMBEDDING_MODEL_NAME=text-embedding-3-small

# ========== Neo4j Configuration ==========
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# ========== Vector Store Configuration ==========
VECTOR_STORE_PROVIDER=ChromaDB
VECTOR_STORE_NAME=GA_VDB
VECTOR_STORE_BASEDIR=./chroma

# ========== Observability: Langfuse ==========
# These enable automatic tracing/logging
LANGFUSE_PUBLIC_KEY=pk-lf-279aeaf3-ca53-4cd5-a185-c3c387292aa5
LANGFUSE_SECRET_KEY=sk-lf-7be19877-9dda-412f-9dd2-38e8150869dc
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_DEBUG=true
OTEL_SERVICE_NAME=graphaide
LANGFUSE_SESSION_NAME=GraphAide-Development
LANGFUSE_ENVIRONMENT=development
```

## How Each Interface Uses .env

### CLI Example
```bash
# .env is auto-loaded
$ graphaide extract document.pdf

# LangFuse automatically logs all operations
# No additional configuration needed
```

### Notebook Example
```python
# .env is auto-loaded when importing core.py
from graphen.core import extract_graph

result = extract_graph(file_path="document.pdf")
# LangFuse automatically logs all operations
```

### Web App Example
```
1. Backend (api.py) starts
   ↓ Imports from core.py
   ↓ load_dotenv() reads .env
   ↓ Sets os.environ

2. Frontend (React) loads
   ↓ Calls /get-observability-config
   ↓ Backend returns values from os.environ
   ↓ UI auto-populates fields

3. User clicks "Extract"
   ↓ Frontend sends API request
   ↓ Backend uses values from Step 1
   ↓ LangFuse automatically logs all operations
```

## Consistency Across All Interfaces

| Aspect | CLI | Notebook | Web App |
|--------|-----|----------|---------|
| .env location | `./graphaide/.env` | `./graphaide/.env` | `./graphaide/.env` |
| Load mechanism | `core.py` → `load_dotenv()` | `core.py` → `load_dotenv()` | `api.py` → `core.py` → `load_dotenv()` |
| Langfuse config | `os.environ` | `os.environ` | `/get-observability-config` → `os.environ` |
| Config override | CLI flags | JSON config | Web UI (optional) |
| Workflows | Same `core.py` functions | Same `core.py` functions | Same `core.py` functions |

## Setting Up Langfuse for All Interfaces

### 1. Create `.env` file
```bash
cd C:\Users\puro755\localcode\GraphAideV2\graphaide
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_DEBUG=true
OTEL_SERVICE_NAME=graphaide
LANGFUSE_SESSION_NAME=GraphAide-Development
LANGFUSE_ENVIRONMENT=development
EOF
```

### 2. Use Any Interface

**CLI:**
```bash
graphaide extract document.pdf
# Automatically logs to Langfuse
```

**Notebook:**
```python
from graphen.core import extract_graph
result = extract_graph(file_path="document.pdf")
# Automatically logs to Langfuse
```

**Web App:**
```
1. Start API: graphaide serve --port 8000
2. Start Web: npm run dev
3. Upload file and click Extract
# Automatically logs to Langfuse
```

## Verification

To verify Langfuse is working:

**Check environment variables loaded:**
```python
import os
from dotenv import load_dotenv
load_dotenv()

print(os.getenv('LANGFUSE_PUBLIC_KEY'))  # Should print pk-lf-...
print(os.getenv('LANGFUSE_SECRET_KEY'))  # Should print sk-lf-...
```

**Check Web App:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Refresh page
4. Look for request to `/get-observability-config`
5. Response should contain your Langfuse keys

## Notes

- ✅ All three interfaces use the **same .env file**
- ✅ Configuration is **centralized** in `core.py`
- ✅ **No duplication** of config logic
- ✅ **One source of truth** for all settings
- ✅ Langfuse automatically logs all operations across all interfaces
- 🔒 **Secrets are never exposed to frontend** - only `os.environ` is read on backend

## Troubleshooting

**"Langfuse not logging"**
- Check `.env` file exists: `C:\Users\puro755\localcode\GraphAideV2\graphaide\.env`
- Verify `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set
- Run `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('LANGFUSE_PUBLIC_KEY'))"`
- Check Langfuse dashboard at https://us.cloud.langfuse.com

**"Web app not loading Langfuse config"**
- Ensure API is running: `graphaide serve --port 8000`
- Check browser console for errors
- Visit `http://localhost:8000/get-observability-config` directly

**"Different config in web app vs CLI"**
- Both use same `.env` file
- Restart `graphaide serve` after editing `.env`
- Refresh web app page after restart
