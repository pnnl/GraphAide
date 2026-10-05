# LangFuse v3/v4 Tracing - Troubleshooting Guide

## Current Status
- ✅ KG extraction works
- ✅ LangFuse SDK initializes  
- ✅ Traces are flushed to cloud
- ❓ Traces not appearing on dashboard

## Most Likely Issue: Env Vars Set AFTER Import

**This is the #1 issue!**

In Jupyter notebooks, if you set env vars AFTER importing graphaide, the callback will be None.

### ✅ CORRECT Order:
```python
# Cell 1: Set env vars FIRST
import os
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."

# Cell 2: Import graphaide
from graphaide import GraphAide, ModelConfig, GraphDBConfig

# Cell 3: Use GraphAide (traces will be captured)
result = graphaide.extract(...)
```

### ❌ WRONG Order:
```python
# Cell 1: Import first
from graphaide import GraphAide, ModelConfig

# Cell 2: Set env vars AFTER
import os
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."  # Too late!

# Cell 3: Extract (no tracing!)
result = graphaide.extract(...)
```

## Diagnostic Steps

### 1. Verify Your Setup
```bash
python validate_langfuse_setup.py
```
Should show:
```
✓ LANGFUSE_PUBLIC_KEY: pk-lf-...
✓ LANGFUSE_SECRET_KEY: ***sk-lf
✓ Langfuse client created
✓ CallbackHandler created successfully
```

### 2. Check in Notebook
Run this FIRST in a notebook cell:
```python
# Cell 1: Set env vars
import os
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."

# Then run diagnostic
exec(open('diagnose_langfuse_in_notebook.py').read())
```

Should show:
```
✓ Keys are set
✓ graphaide not yet imported
✓ Config loaded: enabled=True
✓ Callback created: LangchainCallbackHandler
```

### 3. Run Full Extraction Test
```bash
python test_extraction_with_langfuse.py
```

### 4. Watch Logs During Extraction
Look for these INFO logs:
```
✓ [ExtractorAgent] Using LangFuse callback for tracing
✓ LangFuse traces flushed to cloud
```

If you see instead:
```
⚠️  [ExtractorAgent] LangFuse callback not available - no tracing
```

Then the callback initialization failed.

## Step-by-Step Fix

1. **Restart Jupyter kernel** (important!)
   - Kernel → Restart & Clear Output

2. **Create new first cell:**
   ```python
   import os
   os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-279aeaf3-ca53-..."
   os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-7be19877-9dda-..."
   os.environ["LANGFUSE_BASE_URL"] = "https://us.cloud.langfuse.com"
   print("✓ Env vars set")
   ```

3. **In next cell, import GraphAide:**
   ```python
   from graphaide import GraphAide, ModelConfig, GraphDBConfig
   print("✓ GraphAide imported")
   ```

4. **In next cell, create GraphAide instance:**
   ```python
   graphaide = GraphAide(
       model_config=ModelConfig(...),
       graphdb_config=GraphDBConfig(...)
   )
   print("✓ GraphAide ready")
   ```

5. **In next cell, run extraction:**
   ```python
   result = graphaide.extract(file_path="...")
   print(f"✓ Extracted {len(result.nodes)} nodes")
   ```

6. **Check dashboard:**
   - Wait 2-3 seconds
   - Open https://us.cloud.langfuse.com
   - Look for session "GraphAide-Development"
   - Should see kg_extract trace with LLM calls

## If Traces Still Don't Appear

Check these in order:

### 1. Credentials Issue
- Go to LangFuse dashboard → Settings → API Keys
- Copy fresh `pk-lf-...` and `sk-lf-...` keys
- Update env vars with new keys
- Restart kernel and retry

### 2. Project Mismatch
- Confirm you're looking at correct LangFuse project
- Check which project your API key belongs to
- Dashboard URL should match your base_url (us.cloud.langfuse.com)

### 3. Network Issue
```bash
# Test connectivity
curl -I https://us.cloud.langfuse.com
# Should return 200 OK
```

### 4. Version Mismatch
```bash
python -c "import langfuse; print(f'LangFuse: {langfuse.__version__}')"
python -c "import langchain; print(f'LangChain: {langchain.__version__}')"
```

Expected:
- LangFuse: 4.15.4+
- LangChain: 0.1.x or 0.2.x

If versions seem old:
```bash
pip install -U "langfuse>=4.0.0" "langchain>=0.1.0"
```

## Debug Logs

Enable maximum verbosity:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Watch for these patterns:
# 🔍 [ExtractorAgent] Using LangFuse callback for tracing
# 🔍 [ExtractorChain] Invoking with N callbacks  
# ✓ LangFuse traces flushed to cloud
```

If you DON'T see these, the issue is in the initialization phase.

## Common Scenarios

### Scenario: "I see logs but traces not on dashboard"
**Most likely**: Traces are being created but callback isn't actually being invoked.

**Check**:
- See `✓ [ExtractorAgent] Using LangFuse callback for tracing` log?
- See `🔍 [ExtractorChain] Invoking with N callbacks` log?
- If both yes, but still no traces: may be LangFuse SDK issue, check public_key is correct

### Scenario: "Callback is None"
**Most likely**: Env vars not set before import.

**Fix**: Restart kernel, set env vars first, then import.

### Scenario: "TypeError: unexpected keyword argument"
**Status**: Already fixed in latest version

**Check**: Make sure you have latest code from branch
```bash
git pull origin 115-add-langfuse-support
```

## Still Stuck?

Run this command to save all diagnostic output:
```bash
python validate_langfuse_setup.py > /tmp/langfuse_diag.txt 2>&1
```

Then check `/tmp/langfuse_diag.txt` and share with support.

## Files Available for Testing

- `validate_langfuse_setup.py` - Test each component
- `debug_langfuse.py` - Step-by-step initialization test  
- `test_langchain_callbacks.py` - Test LangChain integration
- `test_extraction_with_langfuse.py` - Full extraction test
- `test_langfuse_v3_api.py` - Check v3 API details
- `diagnose_langfuse_in_notebook.py` - Run inside notebook

## Success Indicators

After running extraction, you should see:
1. ✓ Logs with "Using LangFuse callback for tracing"
2. ✓ Logs with "traces flushed to cloud"
3. ✓ Dashboard shows new "kg_extract" trace
4. ✓ Trace shows LLM call(s) with token counts
5. ✓ Session name is "GraphAide-Development"

If all 5 are true, LangFuse is working! 🎉
