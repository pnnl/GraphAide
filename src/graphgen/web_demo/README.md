# GraphAide Web Demo

A modern React-based web interface for GraphAide. Upload documents, extract knowledge graphs, query them, and visualize relationships—all from a beautiful web UI.

## Features

- 📁 **File Upload**: Drag-and-drop support for PDF, TXT, JSON, JSONL files
- 🔄 **Multiple Operations**: Extract, Extract+Merge, Ingest to Neo4j, Load JSON, Load to Vector Store
- 💬 **Query Interface**: Natural language queries against the knowledge graph (with optional RAG)
- 📊 **Visualization**: Interactive graph layouts and embedding visualizations
- ⚙️ **Configuration**: Intuitive sidebar for setting LLM, Neo4j, and Vector Store config
- 📱 **Responsive**: Works on desktop, tablet, and mobile devices

## Prerequisites

- Node.js 16+ and npm
- GraphAide installed (`pip install graphaide`)
- GraphAide API running on `http://localhost:8000` (via `graphaide serve`)

## Installation

### 1. Install Frontend Dependencies

```bash
cd src/graphgen/web_demo/frontend
npm install
```

### 2. Configure Environment (Optional)

Create `.env.local` in the frontend directory:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_TIMEOUT=300000
```

## Running the Web App

### Option A: Development Mode (Hot Reload)

**Terminal 1** - Start the GraphAide API:
```bash
graphaide serve --port 8000
```

**Terminal 2** - Start the React dev server:
```bash
cd src/graphgen/web_demo/frontend
npm run dev
```

Open browser: `http://localhost:5173`

### Option B: Production Build

```bash
cd src/graphgen/web_demo/frontend
npm run build
npm run preview
```

Then open `http://localhost:4173`

## Usage Guide

### 1. Configure Settings (Left Sidebar)

- **LLM Settings**: Set provider (OpenAI, Anthropic, Google, Bedrock), model name, API key, temperature, max tokens
- **Neo4j**: Configure URI, username, password for graph database
- **Vector Store**: Set provider (ChromaDB, Qdrant), storage path, store name
- **Test Connections**: Click "Test Connection" buttons to verify setup

### 2. Upload a File

- Drag-and-drop a file or click to browse
- Supported formats: PDF, TXT, JSON, JSONL

### 3. Run Operations

- **Extract Nodes & Edges**: Extract knowledge graph without storing
- **Extract & Merge**: Extract with deduplication
- **Ingest to Neo4j**: Extract and load to database
- **Load Pre-extracted JSON**: Load pre-made JSON files
- **Load to Vector Store**: Ingest documents for RAG

### 4. Query the Graph

Switch to "Query" tab to ask natural language questions:
- Use Vector Store (RAG) or Graph-only query
- View LLM-generated answers with related nodes/edges

### 5. Visualize

Switch to "Visualize" tab to see:
- Interactive graph layout (force-directed or hierarchical)
- Graph statistics (nodes, edges, node types)

## Architecture

```
Frontend (React + TypeScript)
    ↓ HTTP requests
Backend (GraphAide API)
    ↓
GraphAide Workflows
    ↓
core.py functions
```

The web app makes HTTP calls to the existing GraphAide REST API endpoints (`/extract`, `/ingest`, `/query`, etc.). **No new backend code is added** - we only consume the existing API.

## File Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── ConfigPanel.tsx
│   │   ├── FileUpload.tsx
│   │   ├── OperationButtons.tsx
│   │   ├── ResultViewer.tsx
│   │   ├── ChatInterface.tsx
│   │   ├── Visualization.tsx
│   │   ├── LoadingSpinner.tsx
│   │   └── *.css
│   ├── services/
│   │   └── graphaideAPI.ts   # API client
│   ├── types/
│   │   └── api.ts            # TypeScript interfaces
│   ├── App.tsx               # Main app component
│   ├── main.tsx              # Entry point
│   └── index.css
├── public/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── .env.example
```

## API Endpoints Used

The web app calls these existing GraphAide endpoints:

```
POST /extract              # Extract nodes/edges from file
POST /extract-merge        # Extract with deduplication
POST /ingest               # Extract and load to Neo4j
POST /load-json            # Load pre-extracted JSON
POST /load-vector          # Load to vector store
POST /visualize-vector-db  # Visualize embeddings
POST /query                # Query knowledge graph
GET  /health               # Health check
```

## Configuration Files

### Load/Save Configuration

Click **Load Config** or **Save Config** to load/save settings from/to JSON files:

```json
{
  "modelProvider": "openai",
  "modelName": "gpt-4o",
  "apiKey": "sk-...",
  "neoUri": "bolt://localhost:7687",
  "neoUsername": "neo4j",
  "neoPassword": "...",
  "vectorStoreProvider": "ChromaDB",
  "vectorStorePath": "./chroma",
  "vectorStoreName": "GA_VDB"
}
```

## Troubleshooting

### "Cannot connect to API"
- Ensure GraphAide is running: `graphaide serve --port 8000`
- Check API is accessible: `curl http://localhost:8000/health`
- Verify firewall/proxy settings

### "File upload fails"
- Check file format (PDF, TXT, JSON, JSONL)
- Check file size isn't too large (>100MB)
- Ensure GraphAide API has write permissions

### "Query returns empty results"
- Ensure data was extracted first (run Extract or Ingest)
- Check Neo4j is running and connected
- Try with "Graph Only" mode first, then enable Vector Store

### "Slow performance"
- Reduce chunk sizes in LLM settings
- Check Neo4j performance
- Consider batch processing via CLI for large files

## Development

### Build & Lint

```bash
npm run build        # Build for production
npm run lint         # Run eslint
npm run dev          # Development with hot reload
```

### Adding New Components

1. Create component in `src/components/YourComponent.tsx`
2. Add corresponding CSS: `src/components/YourComponent.css`
3. Import and use in `App.tsx`
4. Update types in `src/types/api.ts` if needed

## Performance Tips

- For large extractions (>10MB), use CLI: `graphaide extract file.pdf`
- Batch process multiple files locally, then load JSON via web UI
- Enable Vector Store only if you have ChromaDB/Qdrant running
- Adjust temperature (0.0 = deterministic, 1.0 = creative)

## License

MIT (same as GraphAide)

## Support

For issues:
1. Check [GraphAide GitHub](https://github.com/pnnl-int/GraphAide)
2. Review error messages in browser console (F12)
3. Check GraphAide API logs: `graphaide serve --log-level DEBUG`
