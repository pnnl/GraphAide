# Debugging Multi-Retriever Extraction

## Quick Test

Run this to see detailed debug output for multi-retriever extraction:

```bash
python test_debug_extraction.py
```

This will show comprehensive logging at DEBUG level, including:
1. **State initialization** - What keys are in the state
2. **Vector store detection** - Whether vector_store_configs are present
3. **Embeddings retrieval** - How embeddings function is obtained
4. **Each retriever** - Individual retriever execution and results
5. **Context building** - How context is assembled from retrieval results
6. **Fallback logic** - Why fallback to default store (if triggered)

## What to Look For

### SUCCESS Indicators (you should see these):

```
DEBUG ExtractorAgent.__call__: State keys present: [... 'vector_store_configs' ...]
DEBUG ExtractorAgent: vector_store_configs from state = [<VectorStoreConfig ...>]
DEBUG ExtractorAgent: vector_store_configs type = <class 'list'>, len = 1
INFO Multi-retrieval: Running 1 retriever(s) - entities
DEBUG ExtractorAgent: [Retriever 1/1] Creating retriever...
DEBUG   Retriever function created, calling with state...
DEBUG   Result dict keys: ['retrieval_results', 'messages']
DEBUG   Raw retrieval_results: 5 items
INFO   ✓ 5 result(s) from hypersonic_store2
DEBUG   Total accumulated results so far: 5
INFO ✓ Retrieved 5 result(s): 1 entities
DEBUG ExtractorAgent: all_retrieval_results count = 5
DEBUG   Before extend: 0 items in rag_context.retrieval_results
DEBUG   After extend: 5 items in rag_context.retrieval_results
```

### FAILURE Indicators (these indicate problems):

```
DEBUG ExtractorAgent: vector_store_configs from state = []
DEBUG ExtractorAgent: No vector_store_configs in state, skipping dynamic retrievers
WARNING No retrieval results found, falling back to default vector store.
```

## Enable DEBUG Logging

In your code, add:

```python
from graphgen.v2.utils import setup_logging

# Enable DEBUG logging
setup_logging(log_level="DEBUG")

# Then run your extraction
result = graphaide.extract(...)
```

## Troubleshooting Checklist

1. **Vector stores not showing in logs?**
   - Check: Is vector_stores parameter being passed to manager.run()?
   - Check: Is the workflow input schema (KGExtractInput) accepting vector_stores?
   - Check: Is initial_state["vector_store_configs"] being set in manager.py?

2. **Retrievers created but return 0 results?**
   - Check: Does the vector store have data? (Look for "X vectors" in logs)
   - Check: Is the query text empty? (Check raw_text in logs)
   - Check: Is retriever_factory.py actually connecting to the store?

3. **Context still shows "1 chars"?**
   - Check: Are retrieval_results being attached to rag_context?
   - Check: Are retrieval_results being read back during context building?
   - Check: Do results have the expected result_type (ENTITIES, DOCUMENTS, TYPES)?

4. **Falling back to default store?**
   - Check: previous steps - why are retrieval_results empty?
   - Check: Is rag_context.retrieval_results being populated?

## Log Levels

- **INFO**: High-level workflow progress (what users should see)
- **DEBUG**: Detailed troubleshooting info (what developers need)
- **WARNING**: Issues that don't stop execution (missing data, fallbacks)
- **ERROR**: Exceptions and failures

## Sample Full Debug Output

To see a complete example, run:

```bash
python test_debug_extraction.py 2>&1 | tee debug_output.log
```

Then search the log for "ExtractorAgent" to find all debug points.
