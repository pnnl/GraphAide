# GraphAide Web Demo - Quick Start (5 minutes)

## For the Impatient

### Prerequisites
- Python 3.11+
- Node.js 16+
- `pip install graphaide>=0.5.0`

### Go

**Terminal 1** (API):
```bash
export OPENAI_API_KEY=sk-your-key
graphaide serve --port 8000
```

**Terminal 2** (Web App):
```bash
cd src/graphgen/web_demo/frontend
npm install
npm run dev
```

**Browser**:
Open `http://localhost:5173`

---

## That's It!

You now have:
- ✅ GraphAide API running on `http://localhost:8000`
- ✅ React web app running on `http://localhost:5173`
- ✅ Live hot reload enabled

## First Test

1. Upload any PDF or TXT file
2. Click **"🔄 Extract Nodes & Edges"**
3. See results in 30 seconds to 5 minutes

## Configure for Full Features

### Option A: Use `.env` file (Recommended)

**For Development (from repo):**
```bash
# Create at: C:\Users\puro755\localcode\GraphAideV2\graphaide\.env
cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL_NAME=gpt-4o
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Observability (Optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_DEBUG=true
OTEL_SERVICE_NAME=graphaide
LANGFUSE_SESSION_NAME=GraphAide-Development
LANGFUSE_ENVIRONMENT=development
EOF
```

**For Pip Install (Production):**
```bash
# Create at: ~/.graphaide/.env (user home)
mkdir ~/.graphaide
cat > ~/.graphaide/.env << 'EOF'
OPENAI_API_KEY=sk-your-key
LANGFUSE_PUBLIC_KEY=pk-lf-...
# ... rest of config
EOF
```

Web app will auto-load on startup!

### Option B: Use Web UI
Click the sidebar (left side) to:
- **Set API Key** (required)
- **Set Model Name** (default: `gpt-4o`)
- **Configure Neo4j** (for ingest operations)
- **Set Vector Store** (for RAG queries)
- **Observability: Langfuse** (optional)

## Common Operations

| Goal | Step |
|------|------|
| Extract graph from file | Upload file → Click "🔄 Extract" |
| Store in database | Upload file → Click "💾 Ingest" |
| Query the graph | Extract first → Go to "Query" tab |
| See graph structure | Extract first → Go to "Visualize" tab |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot connect to API" | Ensure Terminal 1 is running `graphaide serve` |
| Port 8000 in use | `graphaide serve --port 9000` |
| Port 5173 in use | Edit `frontend/vite.config.ts` and change port |
| "Module not found" | Run `npm install` in `frontend/` directory |

---

For detailed setup, see [SETUP.md](./SETUP.md)
For features & usage, see [README.md](./README.md)
