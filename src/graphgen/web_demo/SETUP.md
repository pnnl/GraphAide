# GraphAide Web Demo - Setup Guide

Complete step-by-step instructions to get the GraphAide web app running.

## Prerequisites

- **Python 3.11+** (for GraphAide)
- **Node.js 16+** (for React frontend)
- **npm 7+** (comes with Node.js)

Verify installations:
```bash
python --version    # Should be 3.11+
node --version      # Should be 16+
npm --version       # Should be 7+
```

## Step 1: Ensure GraphAide is Installed

```bash
pip install graphaide>=0.5.0
```

Verify:
```bash
graphaide --version
```

## Step 2: Set Up Environment Variables

Create `.env` file in your GraphAide project root (or home directory):

```bash
# GraphAide root directory or home
cat > .env << 'EOF'
# LLM Provider Settings
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_NAME=gpt-4o
OPENAI_EMBEDDING_MODEL_NAME=text-embedding-3-small

# Neo4j Database (required for ingest operations)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j
NEO4J_DATABASE=neo4j

# Vector Store (optional, for RAG queries)
VECTOR_STORE_PROVIDER=ChromaDB
VECTOR_STORE_NAME=GA_VDB
VECTOR_STORE_BASEDIR=./chroma
EOF
```

**Required fields**:
- `OPENAI_API_KEY` (or equivalent for your LLM provider)
- `OPENAI_MODEL_NAME`
- `NEO4J_*` (if using ingest operations)

**Optional fields**:
- Vector store settings (if using RAG queries)

## Step 3: Start GraphAide API Server

Open **Terminal 1** and run:

```bash
graphaide serve --port 8000
```

Expected output:
```
[INFO] Starting GraphAide API server on 0.0.0.0:8000
[INFO] Uvicorn running on http://0.0.0.0:8000
```

Verify API is running:
```bash
curl http://localhost:8000/health
```

You should see a JSON response.

## Step 4: Install Frontend Dependencies

Open **Terminal 2** and navigate to the web demo directory:

```bash
cd src/graphgen/web_demo/frontend
npm install
```

This installs React, TypeScript, Tailwind CSS, and other dependencies (~500MB).

## Step 5: Start Frontend Dev Server

In **Terminal 2**, run:

```bash
npm run dev
```

Expected output:
```
  VITE v5.0.0  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

## Step 6: Open Web App

Open your browser and navigate to:

```
http://localhost:5173
```

You should see the GraphAide web interface with:
- Left sidebar (Configuration)
- Main area (Upload & Operations)
- Tabs for Operations, Query, and Visualize

## First Run Checklist

- [ ] GraphAide API running on Terminal 1
- [ ] React dev server running on Terminal 2
- [ ] Browser opened to http://localhost:5173
- [ ] Configuration sidebar visible
- [ ] No console errors (open browser DevTools with F12)

## Configure Settings

1. **Click "LLM Settings"** in the left sidebar
2. Enter your **API Key** (copy from `.env`)
3. Verify **Model Name** (default: `gpt-4o`)
4. **Click "Neo4j Configuration"** and verify settings match `.env`
5. Optionally test connections with **"Test Connection"** button

## Test the App

### Extract Only (No Database Required)

1. Upload a PDF or TXT file
2. Click **"🔄 Extract Nodes & Edges"**
3. Wait for results (30 seconds to 5 minutes depending on file size)
4. View extracted nodes and edges in Results tab

### Full Workflow (Requires Neo4j)

1. Ensure Neo4j is running (default: `bolt://localhost:7687`)
2. Upload a file
3. Click **"💾 Ingest to Neo4j"**
4. View results
5. Switch to **"Query"** tab and ask questions

## Troubleshooting

### Port Already in Use

If `8000` or `5173` is already in use:

**For API**:
```bash
graphaide serve --port 9000
```
Then update `VITE_API_BASE_URL` in `frontend/.env.local`:
```
VITE_API_BASE_URL=http://127.0.0.1:9000
```

**For Frontend**:
Edit `frontend/vite.config.ts` and change port:
```typescript
server: {
  port: 5174,
  ...
}
```

### "Cannot connect to API"

- Ensure GraphAide is running: `curl http://localhost:8000/health`
- Check firewall/proxy settings
- Verify `.env` settings are correct

### "Module not found" error

Ensure `node_modules` is installed:
```bash
cd frontend
npm install
```

### File Upload Fails

- Check file format (must be PDF, TXT, JSON, or JSONL)
- Check file size (keep under 50MB for initial testing)
- Check API is accessible

## Production Build

To create an optimized production build:

```bash
cd frontend
npm run build
```

Output is in `frontend/dist/`. To serve:

```bash
npm run preview
```

Then open http://localhost:4173

## Next Steps

- Read [README.md](./README.md) for feature details
- Check [GraphAide CLI docs](../../cli.py) for command-line usage
- Review [GraphAide GitHub](https://github.com/pnnl-int/GraphAide) for advanced options

## Getting Help

1. **Browser Console**: Open DevTools (F12) → Console tab for client errors
2. **API Logs**: Check Terminal 1 output for server errors
3. **GraphAide Debug Mode**: Run API with `graphaide serve --log-level DEBUG`
4. **Issue Tracker**: [GraphAide GitHub Issues](https://github.com/pnnl-int/GraphAide/issues)

## Development

To modify the web app:

1. Edit React components in `frontend/src/components/`
2. Edit styles in `frontend/src/components/*.css`
3. Changes reload automatically (hot reload enabled)

To rebuild after changes:

```bash
npm run build
```

## Environment Variables Summary

| Variable | Required | Example | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | `sk-...` | LLM API authentication |
| `OPENAI_MODEL_NAME` | Yes | `gpt-4o` | LLM model to use |
| `NEO4J_URI` | For ingest | `bolt://localhost:7687` | Graph database connection |
| `NEO4J_USERNAME` | For ingest | `neo4j` | Graph database user |
| `NEO4J_PASSWORD` | For ingest | `password` | Graph database password |
| `VECTOR_STORE_PROVIDER` | Optional | `ChromaDB` | Vector store type |
| `VECTOR_STORE_BASEDIR` | Optional | `./chroma` | Vector store path |

---

**You're all set!** 🎉 The GraphAide web app is now running.
