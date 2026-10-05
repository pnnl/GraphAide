# LangFuse v4 Integration - Debug Guide

## Problem Summary
Traces are being logged locally but not appearing on the LangFuse cloud dashboard (https://us.cloud.langfuse.com).

## Root Causes Found & Fixed

### 1. **SDK Initialization Order** ✓
**Problem**: CallbackHandler created before Langfuse SDK client was initialized globally.
**Fix**: Initialize `Langfuse()` client first, then create `CallbackHandler()`.
```python
# WRONG
callback = CallbackHandler()

# CORRECT
lf_client = Langfuse()  # Initialize SDK first
callback = CallbackHandler(session_name=session_name)
```

### 2. **OpenAI Model Missing Callbacks** ✓
**Problem**: OpenAI provider wasn't attaching LangFuse callbacks (other providers did via `with_config()`).
**Fix**: Apply callbacks consistently across all providers (OpenAI, Anthropic, Google, Bedrock, LMStudio).
```python
# Now all providers do this:
model = model.with_config(callbacks=[self._langfuse_client])
```

### 3. **Callbacks Not Passed Through Chain.invoke()** ✓
**Problem**: `chain.invoke(inputs)` doesn't use callbacks attached via `with_config()` on the model.
**Fix**: Pass callbacks explicitly via `config` parameter:
```python
# WRONG
response = chain.invoke(inputs)

# CORRECT
response = chain.invoke(inputs, config={"callbacks": [callback]})
```

### 4. **Traces Not Flushed Before Process Exit** ✓
**Problem**: Traces are buffered by LangFuse SDK and may not be sent before the program exits.
**Fix**: Call `flush()` at the end of extraction:
```python
from graphgen.v2.LangFuseManager import flush_langfuse_traces
# ... run extraction ...
flush_langfuse_traces()  # Ensure traces reach cloud
```

## Diagnostic Tests

Run these to debug step-by-step:

### 1. Test LangFuse Manager Initialization
```bash
python debug_langfuse.py
```
Checks:
- Environment variables set correctly
- LangFuse SDK client initializes
- CallbackHandler creates successfully
- Callback object has proper methods (on_llm_start, on_llm_end)

### 2. Test LangChain Callback Integration
```bash
python test_langchain_callbacks.py
```
Verifies:
- Model.invoke() with callbacks
- Model.with_config(callbacks=...)
- Chain.invoke() with config parameter
- All 3 methods should work

### 3. Full Extraction Test with Tracing
```bash
python test_extraction_with_langfuse.py
```
Runs complete extraction and checks:
- LangFuse initialized
- Extraction completes
- Traces are flushed
- CloudI receives traces (check dashboard)

## Environment Setup

Before running any tests:

```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_BASE_URL="https://us.cloud.langfuse.com"
export OPENAI_API_KEY="sk-..."
```

## Debug Logging

Enable detailed trace logging in your extraction code:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Watch for these log patterns:
# 🔍 [ModelFactory] LangFuse callback initialized
# 🔍 [ExtractorAgent.__call__] LangFuse callback available
# 🔍 [ExtractorChain] Invoking with N callbacks
# ✓ LangFuse traces flushed to cloud
```

## Common Issues & Solutions

### "Traces not appearing after 5 minutes"
1. Check credentials in LangFuse dashboard (Settings → API Keys)
2. Verify `flush_langfuse_traces()` is called
3. Check network connectivity to `us.cloud.langfuse.com`

### "LangFuse callback is None"
1. Check `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set
2. Run `debug_langfuse.py` to test initialization
3. Check credentials are valid in LangFuse dashboard

### "CallbackHandler crashes with AttributeError"
1. Update LangFuse: `pip install -U 'langfuse>=4.0.0'`
2. Check that CallbackHandler is from `langfuse.integrations.langchain`
3. Verify session_name parameter is a string (not None)

### "Traces appear but with 0 tokens"
1. This may be normal for cached responses
2. Check LangFuse dashboard for actual token counts
3. If consistently 0, may indicate tracing not attached to LLM calls

## Architecture Overview

```
GraphAide.extract()
├── ModelFactory.__init__()
│   └── get_langfuse_callback() → CallbackHandler
│       └── Initializes Langfuse SDK client globally
│
├── Model creation for all providers
│   └── model.with_config(callbacks=[callback]) ← Attaches tracing
│
├── ExtractorAgent.__call__()
│   ├── Gets self._langfuse_client reference
│   └── Passes via callbacks parameter through chain
│
├── chain.invoke(inputs, config={"callbacks": [...]})
│   └── LLM traces are captured by CallbackHandler
│
└── flush_langfuse_traces()
    └── Sends all buffered traces to cloud
```

## Files Modified

- `src/graphgen/v2/LangFuseManager.py` - SDK initialization order, CallbackHandler creation
- `src/graphgen/v2/ModelManager.py` - Apply callbacks to all model providers
- `src/graphgen/v2/agents/base.py` - Store callback reference
- `src/graphgen/v2/agents/extractor.py` - Pass callbacks through chain invocation
- `src/graphgen/v2/graphaide_api.py` - Flush traces after extraction

## Next Steps

1. **Run diagnostic tests** to verify each layer works
2. **Check dashboard** after running any extraction
3. **Monitor logs** for 🔍 debug symbols indicating trace flow
4. **Verify traces** appear within 1-2 seconds on dashboard
5. **Contact LangFuse support** if traces still don't appear (check their status page)

## References

- LangFuse v4 Docs: https://docs.langfuse.com
- v3→v4 Migration: https://docs.langfuse.com/migration/v3-to-v4
- LangChain Callbacks: https://python.langchain.com/docs/modules/callbacks/
