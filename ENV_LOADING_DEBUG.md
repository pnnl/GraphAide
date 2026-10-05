# GraphAide .env Loading - Debug Guide

## Path Structure

```
C:\Users\puro755\localcode\GraphAideV2\graphaide\
├── .env                           ← Your config file should be HERE
├── src/
│   └── graphgen/
│       └── core.py                ← This file loads .env
```

## How .env Loading Works

When `graphaide serve` or `npm run dev` starts, the backend does this:

```python
# In src/graphgen/core.py

core_file = Path(__file__)  
# Result: C:\Users\puro755\localcode\GraphAideV2\graphaide\src\graphgen\core.py

repo_root = core_file.parent.parent.parent
# parent:     C:\Users\puro755\localcode\GraphAideV2\graphaide\src\graphgen\
# parent:     C:\Users\puro755\localcode\GraphAideV2\graphaide\src\
# parent:     C:\Users\puro755\localcode\GraphAideV2\graphaide\
# Result: C:\Users\puro755\localcode\GraphAideV2\graphaide\

env_file = repo_root / '.env'
# Result: C:\Users\puro755\localcode\GraphAideV2\graphaide\.env ✅
```

## .env Search Order

The code looks for `.env` in this order:

1. **Repo root** ← `C:\Users\puro755\localcode\GraphAideV2\graphaide\.env` ✅
2. Current working directory
3. Home directory `.graphaide/` → `~/.graphaide/.env`
4. Home directory → `~/.env`

## Verification Steps

### Step 1: Verify .env Exists
```bash
ls -la C:\Users\puro755\localcode\GraphAideV2\graphaide\.env
# Should show the file exists
```

### Step 2: Check .env Content
```bash
cat C:\Users\puro755\localcode\GraphAideV2\graphaide\.env
# Should show:
# OPENAI_API_KEY=sk-...
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# etc.
```

### Step 3: Watch API Output for Loading Message
```bash
# Terminal 1
graphaide serve --port 8000

# Should print:
# [GraphAide] ✅ Loaded .env from: C:\Users\puro755\localcode\GraphAideV2\graphaide\.env
```

If you see `✅ Loaded .env from:` message, it's working!

### Step 4: Test API Endpoint
```bash
# Terminal 2
curl http://localhost:8000/get-config

# Should return JSON with your config values
```

### Step 5: Test Web App
```bash
# Terminal 3
cd src/graphgen/web_demo/frontend
npm run dev

# Open http://localhost:5173
# Left panel (ConfigPanel) should show all your .env values
```

## Troubleshooting

### Issue: `❌ No .env file found`

**Check 1: File Exists**
```bash
ls -la .env
# If not found, create it:
cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-key
LANGFUSE_PUBLIC_KEY=pk-lf-your-key
EOF
```

**Check 2: File Format**
- Make sure it's `.env` (not `.env.txt` or `.env.example`)
- Make sure it's in the repo root: `C:\Users\puro755\localcode\GraphAideV2\graphaide\`

**Check 3: API Started From Correct Directory**
```bash
# Correct - from repo root
cd C:\Users\puro755\localcode\GraphAideV2\graphaide
graphaide serve --port 8000

# Wrong - from frontend directory
cd src/graphgen/web_demo/frontend
graphaide serve --port 8000  # This might look in wrong directory!
```

### Issue: ConfigPanel Shows Empty Values

**Solution 1: Restart API**
```bash
# Stop: Ctrl+C in terminal where API is running
# Start: graphaide serve --port 8000
# The API must reload .env on startup
```

**Solution 2: Refresh Browser**
```bash
# Open http://localhost:5173
# Press F5 or Ctrl+R to refresh
```

**Solution 3: Verify API Endpoint**
```bash
# Test if API has the config
curl http://localhost:8000/get-config

# Should return something like:
# {
#   "modelProvider": "openai",
#   "modelName": "gpt-4o",
#   "apiKey": "sk-...",
#   "langfusePublicKey": "pk-lf-...",
#   ...
# }

# If you get 404, API doesn't have the new endpoint
# → Restart API with fresh code
```

## Full Testing Sequence

```bash
# 1. Verify .env file exists
ls -la .env
# ✅ Should show: -rw-r--r-- 1 puro755 1049089 1582 Sep 21 15:18 .env

# 2. Check .env content
cat .env
# ✅ Should show your config values

# 3. Start API - watch for loading message
graphaide serve --port 8000
# ✅ Should print: [GraphAide] ✅ Loaded .env from: ...

# 4. In another terminal, test API
curl http://localhost:8000/get-config | head -10
# ✅ Should return JSON config

# 5. In another terminal, start web app
cd src/graphgen/web_demo/frontend
npm run dev
# ✅ Should say: ➜  Local:   http://localhost:5173/

# 6. Open browser
# ✅ http://localhost:5173 should load
# ✅ Left sidebar (ConfigPanel) should show all values from .env
```

## Expected Output

When everything works, you should see:

**API Terminal Output:**
```
[GraphAide] ✅ Loaded .env from: C:\Users\puro755\localcode\GraphAideV2\graphaide\.env
[INFO] Uvicorn running on http://0.0.0.0:8000
```

**Web Browser (http://localhost:5173):**
```
⚙️ Configuration
  ▼ LLM Settings
    Provider: openai              ← Loaded from .env
    Model Name: gpt-4o            ← Loaded from .env
    API Key: ••••••               ← Loaded from .env (masked)
    Temperature: 0.0              ← Loaded from .env
    ...
```

## Still Not Working?

1. **Clear any environment variable overrides**
   ```bash
   # On Windows PowerShell
   $env:OPENAI_API_KEY = $null
   $env:LANGFUSE_PUBLIC_KEY = $null
   # Then restart terminal and API
   ```

2. **Check if .env is being ignored by git**
   ```bash
   git status
   # If .env is listed under "ignored files", it might have wrong permissions
   ```

3. **Manually test Python loading**
   ```python
   from pathlib import Path
   from dotenv import load_dotenv
   import os

   env_file = Path("C:\\Users\\puro755\\localcode\\GraphAideV2\\graphaide\\.env")
   print(f"File exists: {env_file.exists()}")
   
   if env_file.exists():
       load_dotenv(str(env_file))
       print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
   ```

## Summary

✅ **Path is correct**: `C:\Users\puro755\localcode\GraphAideV2\graphaide\.env`  
✅ **Loading logic is automatic**: API loads it on startup  
✅ **Config is passed to web app**: Via `/get-config` endpoint  
✅ **UI is auto-populated**: ConfigPanel shows values from .env  

Just make sure:
1. `.env` file exists in repo root
2. API is restarted after editing `.env`
3. Browser is refreshed after restarting API
