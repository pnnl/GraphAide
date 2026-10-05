# GraphAide - First Time Setup (After Pip Install)

After installing GraphAide via `pip install graphaide`, follow these steps.

## Step 1: Create `.env` File

GraphAide looks for `.env` in your home directory: `~/.graphaide/.env`

### Windows (PowerShell)
```powershell
# Create directory
mkdir $HOME\.graphaide

# Create .env file
$env_content = @'
# LLM Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_NAME=gpt-4o

# Neo4j (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Langfuse (optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_ENVIRONMENT=development
'@

$env_content | Out-File $HOME\.graphaide\.env -Encoding utf8
```

### Linux/Mac (Bash)
```bash
# Create directory
mkdir -p ~/.graphaide

# Create .env file
cat > ~/.graphaide/.env << 'EOF'
# LLM Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_NAME=gpt-4o

# Neo4j (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Langfuse (optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_ENVIRONMENT=development
EOF
```

## Step 2: Verify Setup

### Test CLI
```bash
graphaide extract --help
# Should show usage without errors
```

### Test Extraction
```bash
# Create a test file
echo "Apple is a technology company. Microsoft makes software." > test.txt

# Extract
graphaide extract test.txt
# Should print nodes and edges
```

## Step 3: Optional - Start Web App

If you want the web UI:

### Terminal 1 - Start API
```bash
graphaide serve --port 8000
```

You should see:
```
[INFO] Starting GraphAide API server on 0.0.0.0:8000
```

### Terminal 2 - Start Web App
```bash
# Navigate to web app directory (if installed from source)
cd src/graphgen/web_demo/frontend
npm run dev
```

Then open browser: **http://localhost:5173**

## Step 4: Test Integration

### CLI + Langfuse
```bash
graphaide extract test.txt
# If LANGFUSE_PUBLIC_KEY is set, it automatically logs to Langfuse
```

### Web App + Langfuse
1. Open http://localhost:5173
2. Upload a file
3. Click "Extract"
4. Check Langfuse dashboard at https://us.cloud.langfuse.com

## Configuration Priority

GraphAide looks for `.env` in this order:

1. **Current working directory**
   ```
   ./.env
   ```

2. **Home directory** (Recommended)
   ```
   ~/.graphaide/.env     ← Put your config here
   ```

3. **Fallback home**
   ```
   ~/.env
   ```

## Troubleshooting

### "OPENAI_API_KEY not found"
- Verify `.env` file exists: `~/.graphaide/.env`
- Check path:
  ```bash
  # Windows PowerShell
  ls $HOME\.graphaide\.env
  
  # Linux/Mac
  ls ~/.graphaide/.env
  ```
- Verify content:
  ```bash
  # Windows PowerShell
  cat $HOME\.graphaide\.env
  
  # Linux/Mac
  cat ~/.graphaide/.env
  ```

### "Neo4j connection failed"
- Either set `NEO4J_*` variables OR
- Start Neo4j: `docker run -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest`

### "Web app won't load Langfuse config"
- Verify API is running: `curl http://localhost:8000/health`
- Check API has `.env` loaded:
  ```bash
  # Terminal where API is running, should show:
  # [GraphAide] Loaded environment from: ~/.graphaide/.env
  ```
- Refresh web app page

### "Different settings in CLI vs Web App"
- Both read from same `.env` file
- Restart API after editing `.env`: `graphaide serve --port 8000`
- Refresh web app in browser

## Next Steps

1. **CLI Usage**: `graphaide --help`
2. **Extract from file**: `graphaide extract document.pdf -o results.json`
3. **Ingest to Neo4j**: `graphaide ingest document.pdf`
4. **Query**: `graphaide query "What companies are mentioned?"`
5. **Web App**: http://localhost:5173 (after starting API and frontend)

## Advanced: Project-Specific Config

You can also use `.env` in specific project directories:

```bash
# Create project
mkdir my-kg-project
cd my-kg-project

# Create project-specific .env
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
EOF

# GraphAide will find this .env when running from this directory
graphaide extract document.pdf
```

Priority: `project/.env` → `~/.graphaide/.env` → `~/.env`

## Environment Variables Reference

| Variable | Required | Example | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | ✅ Yes | `sk-...` | OpenAI API key |
| `OPENAI_MODEL_NAME` | ✅ Yes | `gpt-4o` | Model to use |
| `NEO4J_URI` | ❌ No | `bolt://localhost:7687` | Neo4j server |
| `NEO4J_USERNAME` | ❌ No | `neo4j` | Neo4j user |
| `NEO4J_PASSWORD` | ❌ No | `password` | Neo4j password |
| `LANGFUSE_PUBLIC_KEY` | ❌ No | `pk-lf-...` | Langfuse observability |
| `LANGFUSE_SECRET_KEY` | ❌ No | `sk-lf-...` | Langfuse observability |
| `LANGFUSE_BASE_URL` | ❌ No | `https://us.cloud.langfuse.com` | Langfuse server |
| `OTEL_SERVICE_NAME` | ❌ No | `graphaide` | Service name for tracing |
| `LANGFUSE_ENVIRONMENT` | ❌ No | `development` | Environment tag |

## Support

- **GraphAide Docs**: [README.md](./README.md)
- **Env Config Guide**: [ENV_CONFIG.md](./ENV_CONFIG.md)
- **GitHub Issues**: https://github.com/pnnl-int/GraphAide/issues
