# GraphAide Web App - Configuration Loading Flow

## How Configuration Works on Startup

When the web app starts, it automatically loads all settings from the `.env` file.

```
┌─────────────────────────────────┐
│ .env File (Root Directory)      │
│ OPENAI_API_KEY=sk-...           │
│ NEO4J_URI=bolt://localhost      │
│ LANGFUSE_PUBLIC_KEY=pk-lf-...   │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Backend (api.py) Starts         │
│ core.py loads .env              │
│ os.environ populated            │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Frontend (React) Starts         │
│ App.tsx useEffect() on mount    │
│ Calls /get-config endpoint      │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Backend /get-config Endpoint    │
│ Reads all os.environ vars       │
│ Returns as JSON                 │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Frontend Receives Config        │
│ Updates React state             │
│ ConfigPanel auto-populated      │
└─────────────────────────────────┘
```

## Configuration Values Loaded from .env

### LLM Configuration
```env
OPENAI_PROVIDER=openai                    # or: anthropic, google, bedrock
OPENAI_MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-your-key
OPENAI_TEMPERATURE=0.0
OPENAI_MAX_TOKENS=8192
HTTP_PROXY=http://proxy.example.com:8080  # Optional
```

### Neo4j Configuration
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

### Vector Store Configuration
```env
VECTOR_STORE_PROVIDER=ChromaDB
VECTOR_STORE_NAME=GA_VDB
VECTOR_STORE_BASEDIR=./chroma
```

### Observability: Langfuse
```env
LANGFUSE_PUBLIC_KEY=pk-lf-279aeaf3-ca53-4cd5-a185-c3c387292aa5
LANGFUSE_SECRET_KEY=sk-lf-7be19877-9dda-412f-9dd2-38e8150869dc
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_DEBUG=true
OTEL_SERVICE_NAME=graphaide
LANGFUSE_SESSION_NAME=GraphAide-Development
LANGFUSE_ENVIRONMENT=development
```

## Left Panel (ConfigPanel) - Auto-Populated on Startup

When you open the web app at http://localhost:5173, the ConfigPanel shows:

```
⚙️ Configuration
  ▼ LLM Settings
    Provider: openai                    ← From .env
    Model Name: gpt-4o                  ← From .env
    API Key: ••••••                     ← From .env (masked)
    Temperature: 0.0                    ← From .env
    Max Tokens: 8192                    ← From .env
    Proxy URL: (empty)                  ← From .env

  ▶ Neo4j Configuration
    URI: bolt://localhost:7687          ← From .env
    Username: neo4j                     ← From .env
    Password: ••••••                    ← From .env (masked)

  ▶ Vector Store Config
    Provider: ChromaDB                  ← From .env
    Store Name: GA_VDB                  ← From .env
    Store Path: ./chroma                ← From .env

  ▶ Observability: Langfuse
    Enable Langfuse: ☑                  ← From .env (auto-detected)
    Public Key: ••••••                  ← From .env (masked)
    Secret Key: ••••••                  ← From .env (masked)
    Base URL: https://us...             ← From .env
    Service Name: graphaide             ← From .env
    Session Name: GraphAide-Dev...      ← From .env
    Environment: development            ← From .env
    Debug Mode: ☑                       ← From .env
```

## Three Ways to Use Configuration

### 1. Use .env Defaults (Recommended)

**Setup:**
```bash
mkdir ~/.graphaide
cat > ~/.graphaide/.env << 'EOF'
OPENAI_API_KEY=sk-your-key
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
EOF
```

**Runtime:**
```bash
graphaide serve --port 8000
# Terminal 2
npm run dev
# Open http://localhost:5173
# ConfigPanel auto-populated from .env
```

### 2. Override Values in UI (Per Session)

**Setup:** Same as above

**Runtime:**
```bash
graphaide serve --port 8000
npm run dev
# Open http://localhost:5173
# ConfigPanel loaded from .env
# User can change values in UI
# Changes apply to current session only
# Reload page → reverts to .env values
```

### 3. Change .env and Restart (Persistent)

**Setup:**
```bash
# Edit .env
cat > ~/.graphaide/.env << 'EOF'
OPENAI_API_KEY=sk-new-key
LANGFUSE_PUBLIC_KEY=pk-lf-new
EOF
```

**Runtime:**
```bash
# Restart API (Ctrl+C, then run again)
graphaide serve --port 8000
# Restart web app (Ctrl+C, then run again)
npm run dev
# Open http://localhost:5173
# ConfigPanel shows NEW values from updated .env
```

## Key Points

✅ **Auto-Loading**: Web app loads .env values on startup  
✅ **No Manual Copy-Paste**: All values loaded automatically  
✅ **Masked Secrets**: API keys shown as `••••••` in UI  
✅ **Editable**: User can override values in UI for current session  
✅ **Persistent Storage**: Edit .env to persist changes  
✅ **All Interfaces Use Same .env**: CLI, Notebook, Web App all read from same file  

## Endpoints

### `/get-config` (Main Endpoint)
Returns all configuration from environment variables:
```bash
curl http://localhost:8000/get-config
```

Response:
```json
{
  "modelProvider": "openai",
  "modelName": "gpt-4o",
  "apiKey": "sk-...",
  "temperature": 0.0,
  "maxTokens": 8192,
  "proxyUrl": "",
  "neoUri": "bolt://localhost:7687",
  "neoUsername": "neo4j",
  "neoPassword": "...",
  "vectorStoreProvider": "ChromaDB",
  "vectorStorePath": "./chroma",
  "vectorStoreName": "GA_VDB",
  "langfuseEnabled": true,
  "langfusePublicKey": "pk-lf-...",
  "langfuseSecretKey": "sk-lf-...",
  "langfuseBaseUrl": "https://us.cloud.langfuse.com",
  "langfuseDebug": true,
  "langfuseServiceName": "graphaide",
  "langfuseSessionName": "GraphAide-Development",
  "langfuseEnvironment": "development"
}
```

### `/get-observability-config` (Legacy)
Returns only Langfuse config (deprecated, kept for backward compatibility)

## Environment Variable Fallbacks

If an environment variable is not set, these defaults are used:

| Variable | Default |
|----------|---------|
| `OPENAI_PROVIDER` | `openai` |
| `OPENAI_MODEL_NAME` | `gpt-4o` |
| `OPENAI_TEMPERATURE` | `0.0` |
| `OPENAI_MAX_TOKENS` | `8192` |
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | `neo4j` |
| `VECTOR_STORE_PROVIDER` | `ChromaDB` |
| `VECTOR_STORE_NAME` | `GA_VDB` |
| `VECTOR_STORE_BASEDIR` | `./chroma` |
| `LANGFUSE_BASE_URL` | `https://us.cloud.langfuse.com` |
| `OTEL_SERVICE_NAME` | `graphaide` |
| `LANGFUSE_SESSION_NAME` | `GraphAide-Development` |
| `LANGFUSE_ENVIRONMENT` | `development` |

## Troubleshooting

### ConfigPanel shows empty values
- ✅ Check if API is running: `curl http://localhost:8000/health`
- ✅ Check if .env file exists at `~/.graphaide/.env`
- ✅ Check browser console (F12) for errors
- ✅ Try visiting `http://localhost:8000/get-config` directly to verify backend

### Changed .env but UI not updated
- ✅ Restart API: `graphaide serve --port 8000`
- ✅ Refresh web page: `F5` in browser
- ✅ API must reload .env on startup

### Different values in CLI vs Web App
- ✅ Both read from same .env file
- ✅ Restart API after editing .env
- ✅ CLI may use different .env if running from different directory
- ✅ Priority: `./` → `~/.graphaide/` → `~/`

## Example Complete Setup

```bash
# 1. Create .env in home directory
mkdir ~/.graphaide
cat > ~/.graphaide/.env << 'EOF'
# LLM
OPENAI_API_KEY=sk-proj-abcdef123456
OPENAI_MODEL_NAME=gpt-4o
OPENAI_TEMPERATURE=0.0
OPENAI_MAX_TOKENS=8192

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=mypassword

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-279aeaf3-ca53-4cd5-a185-c3c387292aa5
LANGFUSE_SECRET_KEY=sk-lf-7be19877-9dda-412f-9dd2-38e8150869dc
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_DEBUG=true
EOF

# 2. Start API (Terminal 1)
graphaide serve --port 8000

# 3. Start Web App (Terminal 2)
cd src/graphgen/web_demo/frontend
npm run dev

# 4. Open browser (Terminal 3)
open http://localhost:5173
# ConfigPanel is already populated with values from .env!
```

Now the web app loads all your settings automatically! 🎉
