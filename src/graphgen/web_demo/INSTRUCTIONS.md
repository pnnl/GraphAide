# 🧬 GraphAide Web Demo - Complete Instructions

## What You Get

A **professional, responsive web app** for GraphAide with:

```
┌─────────────────────────────────────────┐
│ GraphAide Web Demo Interface            │
├──────────────┬──────────────────────────┤
│ ⚙️ Config    │ 📁 Upload & Operations   │
│ • LLM        │ • Extract                │
│ • Neo4j      │ • Ingest                 │
│ • VectorDB   │ • Query                  │
│              │ • Visualize              │
│              │ 💬 Results               │
└──────────────┴──────────────────────────┘
```

## Installation (Copy-Paste)

### Step 1: Install Dependencies

```bash
# Navigate to web demo frontend
cd src/graphgen/web_demo/frontend

# Install Node packages
npm install
```

Takes ~2 minutes. Downloads ~500MB.

### Step 2: Set Environment Variables

Create `.env` file in your home or project root:

```bash
export OPENAI_API_KEY=sk-your-key-here
export OPENAI_MODEL_NAME=gpt-4o
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=neo4j
```

Or save to `.env` file and `source .env` before running.

## Running the Web App

### Terminal 1 - Start GraphAide API

```bash
graphaide serve --port 8000
```

You should see:
```
[INFO] Starting GraphAide API server on 0.0.0.0:8000
```

### Terminal 2 - Start React Dev Server

```bash
cd src/graphgen/web_demo/frontend
npm run dev
```

You should see:
```
  ➜  Local:   http://localhost:5173/
```

### Terminal 3 (Optional) - Start Neo4j (for ingest)

```bash
docker run --name neo4j -p 7687:7687 -e NEO4J_AUTH=neo4j/neo4j neo4j:latest
```

Or if Neo4j is already running locally, skip this.

## Using the Web App

### Open Browser

Navigate to: **`http://localhost:5173`**

### First Time Setup

1. **Configure on sidebar (left)**:
   - Click "LLM Settings" → paste your API key
   - Click "Neo4j Configuration" → verify URI, username, password
   - Click "Vector Store" (optional) → set path

2. **Upload a file**:
   - Drag-drop a PDF/TXT onto the upload area
   - Or click to browse

3. **Extract**:
   - Click "🔄 Extract Nodes & Edges"
   - Wait 30 seconds to 5 minutes
   - View results below

### Available Operations

| Button | What It Does | Requires | Output |
|--------|-------------|----------|--------|
| 🔄 Extract Nodes & Edges | Extract KG from file | API key | Nodes, edges |
| ⚡ Extract & Merge | Extract + deduplication | API key | Deduplicated nodes/edges |
| 💾 Ingest to Neo4j | Extract + save to database | API key + Neo4j | Stored in Neo4j |
| 📥 Load Pre-extracted JSON | Load existing KG JSON | Neo4j | Stored in Neo4j |
| 📊 Load to Vector Store | Load for RAG queries | API key + ChromaDB | Vectors stored |

### Query the Graph

1. Go to **"💬 Query"** tab
2. Type a question: "What companies are mentioned?"
3. Choose:
   - ☑️ Use Vector Store (RAG + Graph) ← Slower, more accurate
   - ☐ Graph Only ← Faster, requires explicit graph structure
4. Click **"Send"**
5. Read the LLM-generated answer

### Visualize Results

1. Go to **"📈 Visualize"** tab
2. See:
   - Interactive graph layout
   - Node and edge statistics
   - Toggle between Force-Directed and Hierarchical layouts

## File Structure

```
src/graphgen/web_demo/
├── frontend/                     # React app
│   ├── src/
│   │   ├── components/          # 7 React components (ConfigPanel, etc.)
│   │   ├── services/
│   │   │   └── graphaideAPI.ts  # Calls existing GraphAide API
│   │   ├── types/
│   │   │   └── api.ts           # TypeScript interfaces
│   │   ├── App.tsx              # Main component
│   │   ├── main.tsx             # Entry point
│   │   └── *.css                # Styling
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
├── README.md                     # Full documentation
├── SETUP.md                      # Detailed setup guide
├── QUICKSTART.md                 # 5-minute quick start
├── INSTRUCTIONS.md              # This file
├── start.sh                      # Production start script
└── start-dev.sh                  # Development start script
```

## Key Features

### 1. Configuration Management
- **Collapsible sidebar** with sections for:
  - LLM provider (OpenAI, Anthropic, Google, Bedrock)
  - Neo4j connection settings
  - Vector store configuration
- **Copy-to-clipboard** for API keys
- **Test connection** buttons to verify setup

### 2. File Upload
- **Drag-and-drop** interface
- Supports: PDF, TXT, JSON, JSONL
- Shows file name and size

### 3. Multiple Operations
- Extract (no database)
- Extract + merge duplicates
- Ingest (save to Neo4j)
- Load pre-extracted JSON
- Load to vector store

### 4. Results Viewer
- **Tabbed interface**: Nodes, Edges, JSON
- **Search/filter** within results
- **Export** to CSV or download JSON
- Shows extraction stats (nodes, edges, execution time)

### 5. Query Interface
- Natural language questions
- Option to use Vector Store (RAG) or Graph only
- Shows LLM-generated answer
- Related nodes and edges displayed

### 6. Visualization
- **Interactive graph** (force-directed layout)
- **Graph statistics** (node count, edge count, node types)
- **Responsive** design (works on mobile too)

## Architecture

```
React Frontend (http://localhost:5173)
    ↓ HTTP calls
    ↓
GraphAide API (http://localhost:8000)
    ↓ Uses existing endpoints
    ↓
core.py functions (extract_graph, ingest_to_neo4j, query_graph)
    ↓
Neo4j, Vector Store, LLM APIs
```

**Key point**: The web app **does NOT add new backend code**. It only calls the existing GraphAide REST API (`/extract`, `/ingest`, `/query`, etc.).

## Troubleshooting

### "Cannot connect to API"
```
Error: fetch error network error
```
**Solution**:
- Ensure Terminal 1 is running: `graphaide serve --port 8000`
- Check: `curl http://localhost:8000/health`
- Verify firewall isn't blocking port 8000

### Port 8000 or 5173 in Use
```
Address already in use
```
**Solution** - For API:
```bash
graphaide serve --port 9000
```
Then update in `frontend/.env.local`:
```
VITE_API_BASE_URL=http://127.0.0.1:9000
```

**Solution** - For frontend:
Edit `frontend/vite.config.ts`:
```typescript
server: { port: 5174, ... }
```

### Module Not Found
```
error: ERR! code ERESOLVE
```
**Solution**:
```bash
cd frontend
npm install
```

### File Upload Fails
**Solution**:
- Check file format (PDF, TXT, JSON, JSONL)
- Check file size (keep under 50MB for testing)
- Ensure API is running and accessible

### Slow Performance
**Solution**:
- Large files take longer (expected: 1-5 minutes)
- Reduce `max_tokens` in LLM settings
- Check Neo4j and LLM API response times
- Try with smaller test files first

## Development

### Make Changes

Edit files in `frontend/src/`:
- Components: `frontend/src/components/*.tsx`
- Styles: `frontend/src/components/*.css`
- API: `frontend/src/services/graphaideAPI.ts`
- Types: `frontend/src/types/api.ts`

**Changes auto-reload** (hot reload enabled).

### Rebuild

```bash
npm run build
```

Output in `frontend/dist/`

### Production Deployment

```bash
npm run build
npm run preview
```

Then open `http://localhost:4173`

Or deploy `dist/` folder to any static hosting (Netlify, Vercel, etc.)

## Performance Tips

### For Large Documents
- Use CLI for batch processing: `graphaide extract file.pdf -o output.json`
- Then load JSON via web app: Upload JSON → Click "Load Pre-extracted JSON"

### For RAG Queries
- First populate vector store: Click "📊 Load to Vector Store"
- Then query with Vector Store enabled: Go to "Query" tab, check "Use Vector Store"

### For Multiple Files
- Process locally with CLI (faster)
- Ingest results via web UI

## Advanced: Custom Configuration

### Load Config from JSON

Create `config.json`:
```json
{
  "modelProvider": "openai",
  "modelName": "gpt-4o",
  "apiKey": "sk-...",
  "neoUri": "bolt://localhost:7687",
  "neoUsername": "neo4j",
  "neoPassword": "neo4j",
  "vectorStoreProvider": "ChromaDB",
  "vectorStorePath": "./chroma",
  "vectorStoreName": "GA_VDB"
}
```

Then in web app: Click "Load Config" and select the file.

## Next Steps

1. **Read** [README.md](./README.md) for full feature documentation
2. **Check** [SETUP.md](./SETUP.md) for detailed setup instructions
3. **Explore** GraphAide CLI: `graphaide --help`
4. **Try** batch processing: `graphaide extract document.pdf -o result.json`

## Support

- **Browser Console**: Press F12 for error messages
- **API Logs**: Check Terminal 1 output
- **Debug Mode**: Run `graphaide serve --log-level DEBUG`
- **GitHub**: [GraphAide Issues](https://github.com/pnnl-int/GraphAide/issues)

---

**Ready to go!** 🚀 Open http://localhost:5173 and start extracting knowledge graphs.
