# Langfuse v4 Migration Checklist

**Deadline: November 16, 2026** (59 days from September 18, 2026)

After this date, some Langfuse features may stop working if v4 migration is incomplete.

---

## What Changed in v4

- **Data Model**: Completely restructured for 165× better performance
- **API Endpoints**: New v4 endpoints with different response schemas
- **CallbackHandler**: May have moved or changed parameters
- **Environment Variables**: Some variable names may have changed
- **Database Tables**: Legacy v3 tables no longer supported
- **New Features**: Full-text search, alerts, code evaluators, Langfuse Assistant

---

## Migration Status

### ✅ Code Changes (Completed)

- [x] Updated `setup.cfg`: `langfuse>=4.0.0`
- [x] Added v4 CallbackHandler import fallback in `LangFuseManager.py`
- [x] Added support for v4 environment variable names (LANGFUSE_API_KEY, LANGFUSE_BASEURL, LANGFUSE_SESSION)
- [x] Updated `.env.example` with v4 migration notes
- [x] Code is backward-compatible with v3 until v4 is installed

### ⚠️ Testing Required (Blocked - Requires Project Access)

- [ ] Install `langfuse>=4.0.0` via `pip install -U langfuse`
- [ ] Verify CallbackHandler import succeeds: `from langfuse.integrations.langchain import CallbackHandler`
- [ ] Test extraction with DEBUG logging enabled
- [ ] Verify traces appear on https://us.cloud.langfuse.com
- [ ] Check LangFuse dashboard for v4 UI (full-text search, new filters)
- [ ] Verify no token count discrepancies (v4 may count differently)
- [ ] Test with all 5 model providers (OpenAI, Anthropic, Google, Bedrock, LMStudio)

### 🔴 Project-Level Changes (Blocked - Requires Langfuse CLI + Credentials)

- [ ] Run `langfuse migration` CLI to migrate legacy traces to v4 schema
- [ ] Update Langfuse project settings (if any custom settings exist)
- [ ] Verify data migration completed without errors
- [ ] Check API key compatibility (may need to regenerate in v4 dashboard)

---

## Installation

### Step 1: Update Dependencies

```bash
cd C:\Users\puro755\localcode\GraphAideV2\graphaide
pip install -U "langfuse>=4.0.0"
```

### Step 2: Test in Jupyter Notebook

```python
# Cell 1: Set env vars BEFORE importing GraphAide
import os
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."
os.environ["LANGFUSE_BASE_URL"] = "https://us.cloud.langfuse.com"
os.environ["LANGFUSE_SESSION_NAME"] = "GraphAide-V4-Test"
print("✓ Env vars set")

# Cell 2: Import and verify
from graphgen.v2.LangFuseManager import get_langfuse_callback
callback = get_langfuse_callback()
print(f"Callback initialized: {callback is not None}")

# Cell 3: Run extraction
from graphaide import GraphAide, ModelConfig, GraphDBConfig
graphaide = GraphAide(...)
result = graphaide.extract(file_path="...", ...)
print(f"✓ Extraction complete: {len(result.nodes)} nodes")
```

### Step 3: Verify on Dashboard

1. Open https://us.cloud.langfuse.com
2. Look for v4 UI changes (new search bar, filters, alerts)
3. Check "GraphAide-V4-Test" session appears
4. Expand traces and verify token counts are correct

---

## Troubleshooting

### Traces Not Appearing

- Check internet connectivity to `us.cloud.langfuse.com`
- Verify env vars are set BEFORE importing GraphAide
- Restart Jupyter kernel after setting env vars
- Check logs for `✓ LangFuse CallbackHandler initialized`

### Import Error: `langfuse.integrations.langchain`

- v4 may have moved CallbackHandler location
- Code falls back to v3 import automatically
- Check Langfuse release notes: https://docs.langfuse.com/migration/v3-to-v4

### Token Count Mismatch

- v4 may count tokens differently (especially reasoning tokens)
- Check LangFuse changelog for token counting changes
- This is expected behavior, not a bug

---

## References

- **Langfuse v4 Docs**: https://docs.langfuse.com
- **Migration Guide**: https://docs.langfuse.com/migration/v3-to-v4
- **CLI Docs**: https://docs.langfuse.com/cli/migration
- **Release Notes**: https://github.com/langfuse/langfuse/releases

---

## Timeline

| Date | Milestone |
|------|-----------|
| Sep 18, 2026 | v4 released; migration code added to GraphAide |
| Sep 25, 2026 | Deadline to test in dev environment |
| Oct 15, 2026 | Deadline to complete project migration |
| Nov 16, 2026 | **HARD DEADLINE** - v3 features may stop working |

---

## Rollback Plan

If v4 causes issues:

1. Revert `setup.cfg`: `langfuse>=3.3.0,<4.0.0`
2. Reinstall: `pip install -U langfuse==3.13.0`
3. Traces will continue to work with v3 until Nov 16

(Note: This is a temporary workaround only; permanent migration is required.)

---

**Owner**: puro755  
**Last Updated**: 2026-09-18  
**Status**: Code-ready, awaiting testing + project migration
