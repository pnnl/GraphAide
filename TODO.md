# GraphAide Refactoring TODO

## Code Duplication Analysis
- **File:** `src/graphgen/v2/graphaide_api.py` (672 LOC)
- **Duplication:** ~144 lines (18% of endpoint code)
- **Potential Savings:** ~300 lines (60% reduction)
- **Quick Wins:** ~85 lines (Phase 1, 30 min)

---

## Phase 1: Quick Wins (30 min, -85 LOC, LOW RISK)

### ✅ Task 1.1: Extract log_level handler
- [ ] Create `_setup_log_level(kwargs)` helper method
- [ ] Remove log_level setup from extract(), ingest(), ingest_vectors(), query()
- [ ] **Savings:** -10 LOC

### ✅ Task 1.2: Extract vector_store builder
- [ ] Create `_build_vector_store_configs()` helper method
- [ ] Use in both extract() and ingest()
- [ ] Handles: store_path / store_name, collection_name=None (consistent)
- [ ] **Savings:** -35 LOC

### ✅ Task 1.3: Extract JSONL router
- [ ] Create `_route_jsonl_workflow(mode, file_path, ...)` helper
- [ ] Takes mode="extract" or mode="ingest" for workflow routing
- [ ] Remove duplicate JSONL logic from extract() and ingest()
- [ ] **Savings:** -30 LOC

### ✅ Task 1.4: Extract workflow selector
- [ ] Create `_select_workflow_name(base_workflow, merge, use_chunk_aware)` helper
- [ ] Returns: kg_extract_merge, kg_extract_chunk_aware, or kg_extract
- [ ] Use in both extract() and ingest()
- [ ] **Savings:** -10 LOC

---

## Phase 2: Unification (2-3 hours, -240 LOC, MEDIUM RISK)

### 🔄 Task 2.1: Unify extract() and ingest()
- [ ] Create `_extract_or_ingest(mode, file_path, input_text, ...)` internal method
- [ ] Consolidate all common logic
- [ ] Keep extract() and ingest() as thin public wrappers
- [ ] **Savings:** -240 LOC
- [ ] **Risk:** Medium — requires thorough test coverage

### ✅ Task 2.2: Test coverage for Phase 2
- [ ] Unit tests for `_extract_or_ingest()`
- [ ] Integration tests for extract() with all parameter combinations
- [ ] Integration tests for ingest() with all parameter combinations
- [ ] JSONL tests with merge=True/False
- [ ] Vector store tests with/without configs

---

## Phase 3: Future Enhancements (BACKLOG)

### 📋 Task 3.1: Decorator-based parameter injection
- [ ] Consider @with_log_level decorator
- [ ] Consider @with_vector_stores decorator
- [ ] Reduces boilerplate further

### 📋 Task 3.2: Configuration-driven workflow selection
- [ ] Move hardcoded workflow names to config
- [ ] Enable plugin architecture for custom workflows

### 📋 Task 3.3: Support query() and load_json() in refactoring
- [ ] Note: query() is read-only (RAG), may not need merge logic
- [ ] Note: load_json() loads existing JSON (no extraction)
- [ ] Decision: Evaluate if these need unified code path

---

## Duplication Matrix

| Pattern | extract | ingest | ingest_vectors | LOC | Task |
|---------|---------|--------|-----------------|-----|------|
| Log level handling | ✓ | ✓ | ✓ | 6 | 1.1 |
| Vector store building | ✓ | ✓ | ✗ | 35 | 1.2 |
| JSONL detection/routing | ✓ | ✓ | ✗ | 20 | 1.3 |
| Workflow selection | ✓ | ✓ | ✗ | 8 | 1.4 |
| Unified logic | ✓ | ✓ | ✗ | 150 | 2.1 |

---

## Implementation Notes

### Keep (Good Patterns)
- ✅ Consistent vector store path: `store_path / store_name`
- ✅ Parameter validation in schemas
- ✅ Workflow naming convention: `kg_*_*`
- ✅ Logging at decision points

### Verify After Refactoring
- [ ] Backward compatibility: parameter order unchanged
- [ ] Public API docstrings still accurate
- [ ] Logging flow clear and debuggable
- [ ] All input validation still works
- [ ] JSONL auto-detection still works
- [ ] merge=True produces merged nodes only
- [ ] merge=False produces raw nodes (may have duplicates)
- [ ] Vector stores properly initialized
- [ ] log_level propagates correctly

---

## Success Criteria

- **Phase 1:** All 4 helpers extracted and tested, 85 LOC saved, 0 test failures
- **Phase 2:** extract() and ingest() unified, 240 LOC saved, full test coverage
- **Overall:** 60% code reduction, same functionality, same public API

---

## Related Tickets/Issues
- Duplicate code in extract/ingest
- Consistent parameter handling across endpoints
- Maintainability: reduce cognitive load for future changes

---

## References
- File: `src/graphgen/v2/graphaide_api.py`
- Lines: extract (167-340), ingest (342-505), ingest_vectors (567-601)
- Schemas: `src/graphgen/v2/workflows/schemas.py` (KGExtractInput, KGIngestInput)

---

# Architecture Improvement Plan (2026-09-16)

## Executive Summary

GraphAide's current design works well for multi-agent KG construction but has several limitations affecting speed, maintainability, and operational clarity. This plan identifies **11 key limitations** and proposes improvements grouped into **4 categories**: Performance, Code Complexity, State Management, and Developer Experience.

---

## KEY LIMITATIONS (Detailed Analysis)

### 1. PERFORMANCE ISSUES

#### 1a. No LLM Call Caching
- **Problem:** Same ontology context → repeated LLM calls (2-5x unnecessary)
- **Impact:** 25-40% slower extraction for domain-specific corpora
- **Fix:** Cache by (model, context_hash, prompt_hash), TTL=5min

#### 1b. Parallel Segment Dispatch is All-or-Nothing
- **Problem:** Send ALL segments in parallel; if one fails, entire batch hangs
- **Impact:** Documents with 100+ segments hit API rate limits or OOM
- **Fix:** Adaptive batching (start N=5, scale to N=20 on success; rollback on rate-limit)

#### 1c. Batch Neo4j Loading Blocks on Full Results
- **Problem:** NodesLoader waits for ALL segments to extract before loading any to Neo4j
- **Impact:** 15-30 min extra latency (should load in parallel with extraction)
- **Fix:** Streaming Neo4j loading (insert batches of 50 nodes/100 edges as they arrive)

**Timeline Comparison:**
```
Current (Sequential):
  FileLoader → Extract all → Load all nodes → Load all edges = 3+ minutes

Better (Streaming):
  FileLoader → Extract batch 1 || Load batch 1 → Complete in 1.5 minutes
```

---

### 2. CODE COMPLEXITY & MAINTAINABILITY

#### 2a. Monolithic WorkflowManager (1,781 lines)
- **Problem:** Single file contains 12+ workflows (kg_extract, kg_ingest variants, kg_query, etc.)
- **Issues:**
  - Extract_merge_workflow() duplicates 70% of extract_workflow()
  - Adding new workflow requires modifying manager.py + if-tree in build_workflow()
  - Bugs in shared patterns affect all workflows
- **Impact:** 30+ min to add new workflow; hard to read at a glance
- **Fix:** Split into workflow plugins:
```
workflows/
├── kg_extract_family.py  (extract, extract_merge, chunk_aware, jsonl)
├── kg_ingest_family.py   (ingest variants)
├── kg_query_family.py
├── vectordb_family.py
└── manager.py (registry + dispatch only)
```

#### 2b. State TypedDict is Too Large (20+ fields, mixed concerns)
- **Problem:** Mixing input config, runtime state, output, debug info in one TypedDict
- **Issues:**
  - Hard to understand what's required vs optional per workflow
  - New workflows add 3-5 optional fields ("field soup")
  - Parallel agents confuse what fields they can read/write (no docs)
- **Impact:** Debugging state mutations takes 2x longer; type hints aren't enforced
- **Fix:** Separate concerns into 4 TypedDicts:
```python
class KGConfig(TypedDict):        # Input: ontology_path, vector_stores, max_tokens...
class KGRuntimeState(TypedDict):  # Runtime: segments, rag_context, current_agent...
class KGExtractionOutput(TypedDict): # Output: nodes, edges, chunk_metadata...
class KGDebugState(TypedDict):    # Debug: messages, timing_info...

# Main state inherits all:
class KGGenerationState(KGConfig, KGRuntimeState, KGExtractionOutput, KGDebugState):
    pass
```

#### 2c. Agent Boilerplate Duplication (1,500+ lines across 47 agents)
- **Problem:** Every agent repeats:
  - Template loading + prompt construction (20 lines)
  - Cypher escape logic (20 lines)
  - Structured output parsing with retry (40 lines)
  - Debug logging (80+ lines, copy-paste)
  - State extraction + merge (15 lines)
- **Example:** ExtractorAgent, IntentPredictor, SimpleRAG all have identical escape_cypher_value()
- **Impact:** Bug in escape logic requires fixing in 3+ places; 150 lines boilerplate per new agent
- **Fix:** Extract to base class mixins:
```python
class LoggingMixin:
    def log_llm_input(self, ...)      # Centralized
    def log_llm_output(self, ...)

class CypherSafeMixin:
    def escape_cypher_value(self, value)
    def escape_model_list(self, items)

# Usage:
class ExtractorAgent(GraphAideAgent, LoggingMixin, CypherSafeMixin):
    pass  # Reuse logging + escaping
```

#### 2d. Verbose Logging (80+ debug statements per agent)
- **Problem:** ExtractorAgent logs full LLM input/output + intermediate values
- **Output:** 300+ lines per extraction, 500+ lines per document ingestion
- **Impact:** Logs unreadable; developers disable DEBUG; performance impact from string formatting
- **Fix:** Centralized logging service with configurable detail levels:
  - MINIMAL: one-liner per agent
  - NORMAL: key decisions only
  - VERBOSE: full I/O (current DEBUG)
  - Result: 70% log reduction, still debuggable

---

### 3. STATE MANAGEMENT & RELIABILITY

#### 3a. Reducer Type Mismatches Go Undetected in Sequential Mode
- **Problem:** Annotated[List, operator.add] silently fails if agent returns wrong type
- **Sequential:** Bug may go unnoticed (reducer called once, field initialized late)
- **Parallel:** Crashes immediately → TypeError
- **History:** Fixed 2026-03-23 for 5 agents, but no compiler check prevents future bugs
- **Impact:** Bugs only surface during parallel workflows (hard to debug)
- **Fix:** Type validation in base agent class + CI scan for non-list returns

#### 3b. No Streaming State Updates (Waterfall Sync)
- **Problem:** Workflow phases are fully synchronous: FileLoader → ALL extract → ALL load → ALL edges
- **Cannot:** Interleave (while segments 5-10 extract, cannot load segments 1-4 to Neo4j)
- **Timeline:** Extra 30-40% latency for large documents
- **Fix:** StreamingBatch pattern + agents yield results as ready, don't wait for all-or-nothing

#### 3c. No Rollback or Error Recovery (Partial Ingestion to Neo4j)
- **Problem:** If edges fail after nodes load, no way to roll back
- **Result:** "1000 nodes loaded, 0 edges" with no context; manual Neo4j cleanup
- **Impact:** Production incidents; no audit trail (which docs fully ingested vs partial)
- **Fix:** Transaction manager tracking ingestion state per document; resume from checkpoint

---

### 4. DEVELOPER EXPERIENCE

#### 4a. No Workflow Plugin System (Hardcoded if-tree)
- **Problem:** All workflows in build_workflow() if-elif-else branches
- **Cannot:** Register custom workflows without modifying manager.py
- **Impact:** No domain-specific workflows (e.g., "kg_extract_with_custom_validation")
- **Fix:** Plugin registry:
```python
manager.register_workflow("my_workflow", builder_func)
result = manager.run("my_workflow", inputs)
```

#### 4b. No Performance Profiling Built-in
- **Problem:** No instrumentation to measure extraction time, LLM latency, Neo4j latency, vector latency
- **Impact:** Hard to identify bottlenecks
- **Fix:** Timing middleware + return in WorkflowResult:
```python
result.stats = {
    "extractor_total_time": 25.3,
    "llm_calls_count": 100,
    "neo4j_write_time": 5.2,
    "vector_store_time": 1.1,
}
```

#### 4c. No Query DSL for Workflows (Manual dict construction)
- **Problem:** Users must remember all 15+ fields, no IDE autocomplete
- **Current:** result = manager.run("kg_extract", {file_path: ..., ontology_path: ...})
- **Impact:** Runtime errors if parameter name is wrong; no validation until workflow starts
- **Fix:** Schema-driven fluent API:
```python
result = (ExtractWorkflow()
    .file_path("doc.pdf")
    .ontology_path("ont.ttl")
    .max_tokens_per_segment(4096)
    .extract_pdf_images(True)
    .build()
    .run())
```

---

## IMPROVEMENT RECOMMENDATIONS (by Priority & Effort)

### TIER 1: High Impact, Medium Effort (2-3 weeks)
✓ Split monolithic WorkflowManager
✓ Decompose State TypedDict  
✓ Centralize Logging (LoggingMixin)
**Result:** 50% easier to add workflows, 70% log reduction

### TIER 2: High Impact, Low Effort (1 week)
✓ LLM Call Caching
✓ Boilerplate Extraction (Mixins)
✓ Performance Profiling Instrumentation
**Result:** 25-35% faster extraction, 150→50 lines per agent

### TIER 3: Medium Impact, Medium Effort (2 weeks)
✓ Streaming Batch Pattern
✓ Adaptive Batch Sizing
✓ Workflow Plugin System (Fluent API)
**Result:** 30-40% latency reduction, extensible workflows

### TIER 4: Lower Impact or Complex (3+ weeks)
⚠ Reducer Type Validation (compiler-level, may need LangGraph support)
⚠ Transaction Manager & Rollback (complex rollout)
⚠ Streaming State Updates (requires async generators)

---

## PRIORITY RECOMMENDATION

**Start with Tier 1 + 2 (4-5 weeks) → 80% of benefit**

This gives:
- **Speed:** LLM caching + adaptive batching → 25-35% faster
- **Maintainability:** Split manager + decomposed state → 50% easier to add workflows
- **Clarity:** Centralized logging → 70% log reduction
- **Developer UX:** Plugin system → enable custom workflows

---

## CRITICAL FILES TO MODIFY

### High Priority
- `src/graphgen/v2/workflows/manager.py` (1,781 lines) → Split into families
- `src/graphgen/v2/state.py` → Decompose TypedDict (4-way split)
- `src/graphgen/v2/agents/base.py` → Add LoggingMixin, CypherSafeMixin
- `src/graphgen/v2/agents/extractor.py` → Reference impl for mixin usage

### Medium Priority
- `src/graphgen/v2/ModelManager.py` → Add LLM cache layer
- `src/graphgen/v2/functionnode.py` → Adaptive batch logic
- `src/graphgen/v2/agents/nodesloader.py` → Streaming batch acceptance
- `src/graphgen/v2/workflows/schemas.py` → Schema-driven builders

---

## ACCEPTANCE CRITERIA

- [ ] WorkflowManager < 400 lines (from 1,781)
- [ ] Log output per extraction < 50 lines (from 300+)
- [ ] Agent boilerplate < 50 lines (from 150+)
- [ ] Benchmark: 25% faster extraction on repeat corpus
- [ ] Plugin system allows custom workflows without modifying manager.py
- [ ] All Tier 1 + 2 improvements integrated and tested

---

## RISKS & MITIGATION

| Risk | Mitigation |
|------|-----------|
| State decomposition breaks workflows | Backward compat shim: inherit from all sub-TypedDicts |
| LLM cache invalidation too aggressive | Make TTL configurable, add cache hit metrics |
| Plugin system too flexible | Provide strict schema validation, clear docs |
| Streaming state conflicts with agents | Phase in: read-only streaming first, then opt-in |
