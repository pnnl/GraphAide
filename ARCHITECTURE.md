# GraphAide Architecture & Design

Deep technical overview of GraphAide's multi-agent system, factories, state management, and design patterns.

---

## Table of Contents

1. [Core Architecture](#core-architecture)
2. [Factory Pattern](#factory-pattern)
3. [Agent System](#agent-system)
4. [State Management](#state-management)
5. [Workflow Orchestration](#workflow-orchestration)
6. [Design Patterns](#design-patterns)
7. [Data Flow](#data-flow)
8. [Extension Points](#extension-points)

---

## Core Architecture

GraphAide v2 is built on three pillars:

### 1. **Factory Pattern for Dependency Injection**

Factories create and manage instances of LLMs, vector stores, and graph databases:

```
User Code
    ↓
WorkflowManager (high-level API)
    ↓
AgentFactory, VectorFactory, GraphDBFactory
    ↓
ModelFactory (OpenAI, Anthropic, Bedrock, LMStudio)
    ↓
Agents (each has injected model, vector store, graph driver)
```

### 2. **LangGraph for Workflow Orchestration**

Workflows are LangGraph state graphs where:
- **Nodes** = Agents that process state
- **Edges** = Data flow between agents
- **State** = `KGGenerationState` (TypedDict with Annotated reducers)

```
FileLoader → Extractor → NodesLoader → EdgesLoader → Neo4jPostProcessor
     ↓
 Segments
     ↓
   Raw KG
```

### 3. **Structured State with Type-Safe Updates**

State is a TypedDict with special reducer fields for append-only accumulation:

```python
KGGenerationState = TypedDict({
    "file_path": str,                    # mutable
    "nodes": Annotated[List[Node], operator.add],  # append-only
    "edges": Annotated[List[Edge], operator.add],  # append-only
    "messages": Annotated[List[str], operator.add],  # append-only
})
```

When agents update state, `nodes`, `edges`, and `messages` **accumulate** across all agent runs.

---

## Factory Pattern

### ModelFactory

**Responsibility**: Create LLM instances from environment variables or config.

```python
from graphgen.v2.ModelManager import ModelFactory, ModelConfig

# From config
config = ModelConfig(
    provider="openai",
    model_name="gpt-4o",
    api_key="sk-..."
)
factory = ModelFactory(model_config=config)

# Get model instance
model = factory.get_model("openai", "gpt-4o")

# Model already has:
# - Chat interface (invoke, batch, stream)
# - Structured output support (with_structured_output)
# - Vision capabilities (for gpt-4o, claude-3.5)
```

**Supported Providers:**
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- AWS Bedrock (Claude, Llama)
- LMStudio (local models)

### VectorFactory

**Responsibility**: Create and cache vector stores (ChromaDB or Qdrant).

```python
from graphgen.v2.VectorStoreManager import VectorFactory, VectorDBConfig

config = VectorDBConfig(
    provider="chroma",  # or "qdrant"
    store_name="my_store",
    store_path="./chroma_data"
)
factory = VectorFactory(model_factory, config)
store = factory.get_store()

# Vector store interface (same for both):
# - add_documents(docs)
# - similarity_search(query, k=5)
# - delete(ids)
```

### GraphDBFactory

**Responsibility**: Create graph database drivers (Neo4j or Neptune).

```python
from graphgen.v2.GraphDBManager import GraphDBFactory, GraphDBConfig

config = GraphDBConfig(
    provider="neo4j",
    uri="bolt://localhost:7687",
    username="neo4j",
    password="graphaide123"
)
factory = GraphDBFactory(config)
driver = factory.get_driver()

# Driver methods:
# - execute(cypher_query, params)
# - close()
```

### AgentFactory

**Responsibility**: Build agents with injected dependencies.

```python
from graphgen.v2.agents.AgentManager import AgentFactory
from graphgen.v2.agents.extractor import ExtractorAgent

factory = AgentFactory(
    model_factory=model_factory,
    vector_store_factory=vector_factory,
    graphdb_factory=graphdb_factory
)

# Build a configured agent
extractor = factory.build(
    agent_class=ExtractorAgent,
    agent_id="extractor",
    partials={"format_instructions": "..."}
)
```

---

## Agent System

### Base Agent Class

All agents inherit from `GraphAideAgent`:

```python
class GraphAideAgent(BaseModel):
    model: BaseChatModel              # LLM instance
    prompt: ChatPromptTemplate        # Prompt template
    settings: Dict[str, Any]          # vector_store, graph_store, model_config, etc.
    
    tool_schema: BaseModel            # Input schema for tool calling
    tool_description: str             # Agent's role description
    tool_output_keys: List[str]       # State fields updated by this agent
    
    def __call__(self, state: KGGenerationState) -> dict:
        """Process state and return updates."""
        # 1. Extract inputs from state
        # 2. Call LLM with prompt
        # 3. Parse structured output
        # 4. Return dict with state updates
```

### Agent Lifecycle

```python
# 1. Initialize with dependencies injected
agent = factory.build(ExtractorAgent, "extractor")

# 2. Agent receives state via __call__()
state = {
    "raw_text": "Text to extract from",
    "rag_context": ontology_and_wikidata,
}

# 3. Agent processes state
result = agent(state)  # Returns dict with updates

# 4. Workflow merges result into state
# Annotated reducers accumulate values:
# - state["nodes"] += result["nodes"]
# - state["edges"] += result["edges"]
# - state["messages"] += result["messages"]

# 5. Next agent in pipeline receives updated state
```

### Built-in Agents

| Agent | Input | Output | Role |
|-------|-------|--------|------|
| **FileLoaderAgent** | file_path | segments | Split text/PDF into chunks |
| **OntologyLoaderAgent** | ontology_file_path | rag_context | Load ontology types from OWL/TTL |
| **ExtractorAgent** | raw_text | nodes, edges | Extract entities & relationships via LLM |
| **NodesLoaderAgent** | nodes | - | Insert nodes into Neo4j via MERGE |
| **EdgesLoaderAgent** | edges | - | Insert edges into Neo4j via MATCH |
| **Neo4jPostProcessorAgent** | - | - | Apply node labels, deduplicate, optimize |
| **IntentPredictorAgent** | question | intent | Predict query intent (subjectivity, locality, etc.) |
| **SimpleRAGAgent** | question, graph | answer | Retrieve context + generate answer |
| **VectorDBLoaderAgent** | file_paths | - | Embed documents into vector store |

---

## State Management

### KGGenerationState TypedDict

```python
class KGGenerationState(TypedDict):
    # Input fields
    file_path: str
    file_paths: List[str]
    raw_text: str
    question: str
    
    # Processing fields
    segments: Annotated[List[str], operator.add]           # Mutable, accumulates
    rag_context: Optional[RAGContext]                       # Ontology + Wikidata
    
    # Output fields (append-only)
    nodes: Annotated[List[Node], operator.add]             # Accumulates
    edges: Annotated[List[Edge], operator.add]             # Accumulates
    messages: Annotated[List[str], operator.add]           # Debug messages
    
    # Optional fields
    ontology_file_path: Optional[str]
    extract_pdf_images: Optional[bool]
    use_vision_extraction: Optional[bool]
    vector_store_provider: Optional[str]
    log_level: Optional[str]
    
    # Neo4j fields
    neo4j_uri: Optional[str]
    neo4j_username: Optional[str]
    neo4j_password: Optional[str]
```

### RAGContext Class

Consolidates ontology and retrieval data:

```python
class RAGContext:
    ontology_node_types: List[str]       # ["Person", "Organization", ...]
    ontology_edge_types: List[str]       # ["knows", "works_for", ...]
    wikidata_context: Dict[str, Dict]    # {"Q42": {"label": "Douglas Adams"}}
    retrieval_results: List[RetrievalResult]  # Multi-retriever results
```

### Reducer Pattern for Parallel Execution

Annotated fields use `operator.add` to merge results from parallel agents:

```python
# Bad: returns string instead of list
def extract(state):
    return {"current_agent": "ExtractorAgent"}  # ❌ TypeError!

# Good: returns list
def extract(state):
    return {"current_agent": ["ExtractorAgent"]}  # ✓ Merges correctly
```

When `Send()` dispatches to multiple subgraph instances in parallel, each updates the same list field. The reducer combines them:

```python
[Node(...), Node(...)] + [Node(...), Node(...)] = [Node(...), Node(...), Node(...), Node(...)]
```

---

## Workflow Orchestration

### LangGraph State Graph

Workflows are compiled LangGraph `StateGraph` instances:

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(KGGenerationState)

# Add nodes (agents)
graph.add_node("FileLoader", fileloader_agent)
graph.add_node("Extractor", extractor_agent)
graph.add_node("NodesLoader", nodes_loader_agent)
graph.add_node("EdgesLoader", edges_loader_agent)

# Add edges (routing)
graph.add_edge(START, "FileLoader")
graph.add_edge("FileLoader", "Extractor")
graph.add_edge("Extractor", "NodesLoader")
graph.add_edge("NodesLoader", "EdgesLoader")
graph.add_edge("EdgesLoader", END)

# Compile
app = graph.compile()

# Execute
result = app.invoke(initial_state)
```

### Parallel Execution with Send()

For segment-level parallelism:

```python
from langgraph.constants import Send

def dispatch_segments(state: KGGenerationState) -> list[Send]:
    """Send each segment to extractor in parallel."""
    segments = state.get("segments", [])
    return [
        Send("extractor", {
            "raw_text": segment,
            "rag_context": state.get("rag_context"),
            ...
        })
        for segment in segments
    ]

graph.add_conditional_edges("FileLoader", dispatch_segments)
# Extractor runs N times in parallel (one per segment)
# Results merge via Annotated[List, operator.add] reducer
```

### Subgraphs for Code Organization

Complex workflows use subgraphs to organize related agents:

```python
# kg_ingest_subgraph.py
def create_kg_ingest_subgraph():
    graph = StateGraph(KGGenerationState)
    graph.add_node("NodesLoader", nodes_loader)
    graph.add_node("EdgesLoader", edges_loader)
    graph.add_node("Neo4jPostProcessor", postprocessor)
    # ... edges ...
    return graph.compile()

# manager.py
main_graph.add_node("KGIngest", create_kg_ingest_subgraph())
main_graph.add_edge("Extractor", "KGIngest")
```

---

## Design Patterns

### 1. Dependency Injection via Constructor

```python
class ExtractorAgent(GraphAideAgent):
    def __init__(self, model, template_str, settings):
        self.model = model                    # Injected LLM
        self.settings = settings              # Contains vector_store, graph_store
        self.prompt = ChatPromptTemplate.from_template(template_str)
```

Enables:
- **Easy testing** - Mock any dependency
- **Configuration** - Use different models, stores, templates per context
- **Swappability** - Replace vector store at runtime

### 2. Tool Schemas for Structured Output

```python
class ExtractorToolSchema(BaseModel):
    nodes: List[Node] = Field(description="Extracted entities")
    edges: List[Edge] = Field(description="Extracted relationships")

# In agent:
structured_llm = self.model.with_structured_output(ExtractorToolSchema)
result = chain.invoke(inputs)  # Returns ExtractorSchema instance
```

Benefits:
- **Type safety** - Pydantic validates LLM output
- **Auto-parsing** - LangChain handles JSON parsing
- **API clarity** - Tool schema documents what LLM outputs

### 3. State-Driven Routing

```python
def route_based_state(state) -> str:
    if state.get("use_vision_extraction"):
        return "LoadImagesWithVision"
    else:
        return "LoadImagesPlain"

graph.add_conditional_edges("ImageLoader", route_based_state)
```

Enables:
- **Runtime decisions** - Route based on input parameters
- **Optional workflows** - Skip steps if not needed
- **Reusable graphs** - Same graph handles different scenarios

### 4. Annotation Reducers for Accumulation

```python
# Instead of replacing state fields, accumulate them
nodes: Annotated[List[Node], operator.add]  # Appends to list

# In agent:
return {"nodes": [new_node1, new_node2]}  # ✓ Merges

# Multiple agents can update nodes safely:
# Agent 1 adds [node1, node2]
# Agent 2 adds [node3, node4]
# Final state has [node1, node2, node3, node4]
```

---

## Data Flow

### End-to-End: Extract → Load → Query

```
1. USER PROVIDES INPUT
   ↓ file_path="document.pdf"

2. FILELOADER AGENT
   ↓ Splits into segments
   ↓ state["segments"] = [text_1, text_2, ...]

3. EXTRACTOR AGENT (parallel per segment)
   ↓ Calls LLM with each segment
   ↓ state["nodes"] += [node_1, node_2, ...]  (accumulates)
   ↓ state["edges"] += [edge_1, edge_2, ...]  (accumulates)

4. NODESLOADER AGENT
   ↓ Executes Cypher: MERGE (n:Node {node_id: row.node_id}) ...
   ↓ Creates/updates nodes in Neo4j

5. EDGESLOADER AGENT
   ↓ Executes Cypher: MATCH (src), (tgt) CREATE (src)-[r:REL]-(tgt)
   ↓ Creates relationships between nodes

6. NEO4JPOSTPROCESSOR AGENT
   ↓ Applies node_type labels: CALL apoc.create.addLabels(id(n), [type])
   ↓ Deduplicates, optimizes

7. OUTPUT
   ↓ state["messages"] = [log_1, log_2, ...]
   ↓ state["nodes"], state["edges"] saved to JSON (optional)
   ↓ Neo4j now contains knowledge graph

8. QUERY PHASE
   ↓ Question comes in
   ↓ IntentPredictorAgent scores query dimensions
   ↓ SimpleRAGAgent retrieves from graph + vector store
   ↓ LLM generates answer
   ↓ Return to user
```

---

## Extension Points

### Create a Custom Agent

```python
from graphgen.v2.agents.base import GraphAideAgent
from pydantic import BaseModel, Field

# 1. Define input schema
class MyAgentToolSchema(BaseModel):
    input_field: str = Field(description="What I need")

# 2. Create agent class
class MyCustomAgent(GraphAideAgent):
    tool_schema = MyAgentToolSchema
    tool_description = "My custom agent does X"
    tool_output_keys = ["my_output_field"]
    
    def __call__(self, state: KGGenerationState) -> dict:
        # Read from state
        data = state.get("my_input")
        
        # Use injected model
        result = self.model.invoke(...)
        
        # Return state updates
        return {
            "my_output_field": result,
            "messages": [f"Agent completed: {result}"]
        }

# 3. Build and use
agent = factory.build(MyCustomAgent, "my_agent")

# 4. Add to workflow
graph.add_node("MyAgent", agent)
graph.add_edge("PreviousNode", "MyAgent")
```

### Register Custom Workflow

```python
from graphgen.v2.workflows.manager import WorkflowManager

manager = WorkflowManager()

# Define workflow function
def my_custom_workflow(manager, inputs):
    # Build graph
    graph = StateGraph(KGGenerationState)
    # ... add nodes, edges ...
    app = graph.compile()
    
    # Execute
    result = app.invoke(initial_state)
    return result

# Register
manager.register_workflow("my_workflow", my_custom_workflow)

# Use
result = manager.my_workflow({"file_path": "doc.pdf"})
```

### Customize Extraction Prompts

Prompts are loaded from `.template` files:

```bash
src/graphgen/v2/templates/
├── extractor.template
├── intentpredictor.template
├── simplerag.template
└── ...
```

To customize:

1. **Modify existing template** (affects all extractions)
2. **Pass custom template to agent factory**:

```python
agent = factory.build(
    ExtractorAgent,
    "extractor",
    template_path="my_custom_extractor.template"
)
```

---

## Performance Considerations

### Parallelization

Segments processed in parallel (one LLM call per segment):

```python
# If document has 10 segments:
# Sequential: 10 * 2s = 20s
# Parallel: max(2s, 2s, 2s, ...) = 2s (limited by LangGraph concurrency)
```

### Batching for Neo4j Loading

Nodes/edges batched to avoid timeout on large graphs:

```python
# BatchSize = 30 nodes, 50 edges
# If 1000 nodes: 34 batches, each batch runs workflow
# Parallel loading per batch: 2-3x faster than sequential
```

### Vector Store Indexing

Qdrant faster than ChromaDB for large datasets (1M+ vectors):

```
ChromaDB: In-memory + disk
Qdrant: Optimized C++ with HNSW indexing
```

---

## Summary

GraphAide's architecture combines:

1. **Factory Pattern** - Flexible dependency injection
2. **LangGraph** - Scalable workflow orchestration  
3. **Typed State** - Type-safe, structured data flow
4. **Agents** - Reusable, testable processing units
5. **Parallel Execution** - Send() for segment-level parallelism
6. **Extensibility** - Custom agents, workflows, prompts

Result: **Scalable, maintainable, extensible** multi-agent KG construction system.

---

## Architecture ASCII Diagrams

### Layer 1: User API & Configuration

```
┌─────────────────────────────────────────────────────────────┐
│                    GraphAide Facade API                      │
│  - extract(file_path, ontology_path, ...)                   │
│  - ingest(file_path, ontology_path, ...)                    │
│  - query(question)                                           │
│  - load_json(json_path)                                      │
│  - ingest_vectors(file_paths)                               │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ModelConfig      GraphDBConfig    VectorDBConfig
   ┌──────────┐     ┌──────────┐     ┌──────────┐
   │Provider: │     │URI:      │     │Provider: │
   │ openai   │     │bolt://   │     │ chroma   │
   │ claude   │     │username: │     │ qdrant   │
   │ bedrock  │     │password: │     │location: │
   └──────────┘     └──────────┘     └──────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
            ┌─────────────────────────────┐
            │   WorkflowManager (Core)    │
            │  Orchestrates all workflows │
            └────────────────┬────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
            kg_extract   kg_ingest     kg_query
               (...)        (...)        (...)
```

### Layer 2: Factory Pattern - Dependency Injection

```
                        WorkflowManager
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
    ModelFactory        VectorFactory       GraphDBFactory
        │                    │                    │
    ┌───┴───┐            ┌───┴───┐           ┌───┴───┐
    │       │            │       │           │       │
    ▼       ▼            ▼       ▼           ▼       ▼
  OpenAI  Claude       ChromaDB Qdrant      Neo4j  Neptune
  GPT-4o  3.5         In-Memory  HNSW      Bolt   GremlinWS
  model   model        IndexDB   Vector     Graph  Database
    │       │            │       │           │       │
    └───────┴────────────┴───────┴───────────┴───────┘
            │
            ▼
        Agents (receive injected dependencies)
        ├─ ExtractorAgent        (model)
        ├─ NodesLoaderAgent      (graphdb_driver)
        ├─ EdgesLoaderAgent      (graphdb_driver)
        ├─ VectorDBLoaderAgent   (vector_store)
        └─ SimpleRAGAgent        (model, vector_store, graphdb)
```

### Layer 3: Multi-Agent Workflow (LangGraph)

```
                        KGGenerationState
                        ┌───────────────────────┐
                        │ file_path             │
                        │ segments: [...]       │
                        │ raw_text              │
                        │ nodes: []  [ADD]      │
                        │ edges: []  [ADD]      │
                        │ rag_context           │
                        │ messages: [] [ADD]    │
                        └───────────────────────┘
                                 △
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
                ▼                ▼                ▼
         ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
         │  FileLoader  │ │ Ontology     │ │ Ontology     │
         │              │ │ Loader       │ │ Generator    │
         │ ┌──────────┐ │ │              │ │              │
         │ │ Split    │ │ │ ┌──────────┐ │ │ ┌──────────┐ │
         │ │ PDF/TXT  │ │ │ │Load OWL/ │ │ │ │Generate  │ │
         │ │ into     │ │ │ │TTL types │ │ │ │ontology  │ │
         │ │ segments │ │ │ │& edges   │ │ │ │from docs │ │
         │ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │
         └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                │                │                │
                └────────┬───────┴────────┬───────┘
                         │                │
              ┌──────────▼──────────┐     │
              │ Parallel Dispatch   │     │
              │ (Send per segment)  │     │
              └──────────┬──────────┘     │
                         │                │
            ┌────────────┴────────┬───────┘
            │                     │
     ┌──────▼──────┐      ┌──────▼──────┐      ┌──────────────┐
     │  Extractor  │      │  Extractor  │  ... │  Extractor   │
     │ (Segment 1) │      │ (Segment 2) │      │ (Segment N)  │
     │             │      │             │      │              │
     │ LLM calls   │      │ LLM calls   │      │ LLM calls   │
     │ → nodes[]   │      │ → nodes[]   │      │ → nodes[]   │
     │ → edges[]   │      │ → edges[]   │      │ → edges[]   │
     └──────┬──────┘      └──────┬──────┘      └──────┬───────┘
            │                     │                     │
            └─────────────┬───────┴──────────┬──────────┘
                          │                  │
                    [Reducer: operator.add]
                    Accumulated in state
                          │
            ┌─────────────┴────────────┐
            │                          │
     ┌──────▼──────────┐        ┌─────▼──────────┐
     │ ExtractMerger   │        │ Nodes4Edges    │
     │ (Optional)      │        │ LinkCreator    │
     │ - Dedup nodes   │        │ - Link nodes   │
     │ - Merge edges   │        │ - for edges    │
     └──────┬──────────┘        └─────┬──────────┘
            │                          │
            └──────────┬───────────────┘
                       │
            ┌──────────▼────────────┐
            │ NodesLoaderAgent      │
            │ (Batch: 30 nodes)     │
            │ MERGE (n:Node) {...}  │
            │ → Insert to Neo4j     │
            └──────────┬────────────┘
                       │
            ┌──────────▼────────────┐
            │ EdgesLoaderAgent      │
            │ (Batch: 50 edges)     │
            │ MATCH (src), (tgt)    │
            │ CREATE (src)-[r]-(tgt)│
            │ → Insert to Neo4j     │
            └──────────┬────────────┘
                       │
            ┌──────────▼────────────┐
            │ Neo4jPostProcessor    │
            │ - Apply node_type     │
            │ - Deduplicate         │
            │ - Optimize indices    │
            └──────────┬────────────┘
                       │
                       ▼
                  [Neo4j DB]
                  ┌─────────┐
                  │ Nodes   │
                  │ Edges   │
                  │ Metadata│
                  └─────────┘
```

### Layer 4: Extraction Pipeline (Detailed View)

```
┌─────────────────────────────────────────────────────────────┐
│              KG Extraction Pipeline (kg_extract)            │
└─────────────────────────────────────────────────────────────┘

Input:
  file_path: "document.pdf"
  ontology_path: "ont.ttl"
  use_chunk_aware: bool
  section_chunking: bool
  extract_pdf_images: bool

     │
     ▼
  ┌─────────────────┐
  │ FileLoader      │
  │ - PDFPlumber    │ ←─ IF PDF
  │ - PyPDF2        │
  │ - txt parser    │ ←─ IF TXT
  └────────┬────────┘
           │
           ▼
      Segments: List[str]
           │
     ┌─────┴──────┐
     │ (Optional) │
     │ chunk      │
     │ tracking?  │
     └─────┬──────┘
           │
           ▼
    [Parallel Dispatch]
    ┌───────────────────────────────┐
    │ for each segment in segments:  │
    │   Send("extractor", {...})    │
    └───────────────┬───────────────┘
                    │
        ┌───────────┴──────────┬──────────┐
        ▼                      ▼          ▼
  ┌──────────────┐    ┌──────────────┐ ┌──────────┐
  │ExtractorAgent│    │Extractor...  │ │Extractor │
  │              │    │              │ │          │
  │ + LLM        │    │ + LLM        │ │+ LLM     │
  │ + Ontology   │    │ + Ontology   │ │+ Ontology│
  │ + Wikidata   │    │ + Wikidata   │ │+ Wikidata│
  │              │    │              │ │          │
  │ Returns:     │    │ Returns:     │ │Returns:  │
  │ nodes: []    │    │ nodes: []    │ │nodes: [] │
  │ edges: []    │    │ edges: []    │ │edges: [] │
  └──────┬───────┘    └──────┬───────┘ └────┬─────┘
         │                   │              │
         └───────────┬───────┴──────────┬───┘
                     │
          [State Accumulation]
          nodes: [n1, n2, n3, ...]
          edges: [e1, e2, e3, ...]
                     │
                     ▼
          ┌──────────────────────┐
          │ ExtractMergerAgent   │
          │ (Optional)           │
          │ - Dedup by node_id   │
          │ - Merge edges        │
          │ - Combine duplicates │
          └──────────┬───────────┘
                     │
                     ▼
            Merged Nodes & Edges
                     │
                     ▼
            ┌─────────────────┐
            │ Output JSON     │
            │ GraphAide_KG_   │
            │ Extract_<ts>.json
            └─────────────────┘
```

### Layer 5: Query Pipeline (Detailed View)

```
┌─────────────────────────────────────────────────────────────┐
│              Query Pipeline (kg_query)                      │
└─────────────────────────────────────────────────────────────┘

Input:
  question: "What is X?"
  [Neo4j with loaded KG]

     │
     ▼
  ┌─────────────────────────┐
  │ IntentPredictorAgent    │
  │ - Score: subjectivity   │
  │ - Score: locality       │
  │ - Score: navigationality│
  │ - Score: causality      │
  │ - Score: procedurality  │
  └────────────┬────────────┘
               │
               ▼
        IntentSchema
        {scores: {...}}
               │
               ▼
    ┌──────────────────────┐
    │ SimpleRAGAgent       │
    │                      │
    │ ┌──────────────────┐ │
    │ │ Multi-Retriever  │ │
    │ │ - Ontology store │ │
    │ │ - Wikidata store │ │
    │ │ - Document store │ │
    │ └────────┬─────────┘ │
    │          │           │
    │          ▼           │
    │  ┌──────────────┐    │
    │  │ Neo4j Graph  │    │
    │  │ Traversal    │    │
    │  │ (Cypher QA)  │    │
    │  └────────┬─────┘    │
    │           │          │
    │      Context +        │
    │      Retrieval Results│
    │           │          │
    │           ▼          │
    │  ┌──────────────┐    │
    │  │ LLM (Claude) │    │
    │  │ Generate     │    │
    │  │ Answer       │    │
    │  └────────┬─────┘    │
    │           │          │
    └───────────┼──────────┘
                │
                ▼
            Answer String
```

### Layer 6: State Management - Annotated Reducers

```
                    KGGenerationState
                   (TypedDict with reducers)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐      ┌──────────────────┐  ┌─────────────┐
   │ Mutable │      │ Append-Only      │  │ Append-Only │
   │ Fields  │      │ (operator.add)   │  │ (operator)  │
   │         │      │                  │  │             │
   │ • file_ │      │ • nodes:         │  │ • edges:    │
   │   path  │      │   List[Node]     │  │   List[Edge]│
   │ • raw_  │      │ • segments:      │  │ • messages: │
   │   text  │      │   List[str]      │  │   List[str] │
   │ • quest │      │                  │  │             │
   │   ion   │      │ Reducer Logic:   │  │ Reducer:    │
   │         │      │ new_list +       │  │ old_list +  │
   │ Get/Set │      │ existing_list =  │  │ new_list    │
   │ freely  │      │ combined_list    │  │             │
   └─────────┘      │                  │  │ Safe for    │
                    │ [Agent1] +       │  │ parallel    │
                    │ [Agent2] +       │  │ updates     │
                    │ [Agent3] =       │  │ (Send)      │
                    │ [combined]       │  │             │
                    └──────────────────┘  └─────────────┘
                              │                    │
                    Parallel Agents                │
                    Send(target, {...})   Multiple
                                          Agents
                              │
                              ▼
                    ┌──────────────────┐
                    │ State Snapshot   │
                    │ at Workflow End  │
                    │ - All nodes      │
                    │ - All edges      │
                    │ - All messages   │
                    │ - All metadata   │
                    └──────────────────┘
```

### Layer 7: Component Interaction Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│  Component Interaction: Who talks to Whom?                      │
└─────────────────────────────────────────────────────────────────┘

Agent               │ Consumes From  │ Produces For       │ Uses
────────────────────┼────────────────┼────────────────────┼──────
FileLoader          │ file_path      │ segments           │ -
OntologyLoader      │ ontology_path  │ rag_context        │ -
ExtractorAgent      │ raw_text,      │ nodes[], edges[]   │ Model
                    │ rag_context    │                    │
NodesLoaderAgent    │ nodes[]        │ -                  │ GraphDB
EdgesLoaderAgent    │ edges[]        │ -                  │ GraphDB
Neo4jPostProcessor  │ -              │ -                  │ GraphDB
ExtractMerger       │ nodes[],       │ nodes[],           │ -
                    │ edges[]        │ edges[] (merged)   │
Nodes4Edges         │ nodes[]        │ edges[]            │ -
SimpleRAGAgent      │ question,      │ answer             │ Model,
                    │ rag_context    │                    │ VectorDB,
                    │                │                    │ GraphDB
IntentPredictor     │ question       │ intent_scores      │ Model
────────────────────┴────────────────┴────────────────────┴──────
```

### Layer 8: File Structure & Modules

```
graphaide/
├── src/graphgen/v2/
│   ├── agents/
│   │   ├── base.py                ← GraphAideAgent (base class)
│   │   ├── AgentManager.py         ← AgentFactory (builds agents)
│   │   ├── extractor.py            ← ExtractorAgent
│   │   ├── nodesloader.py          ← NodesLoaderAgent
│   │   ├── edgesloader.py          ← EdgesLoaderAgent
│   │   ├── neo4jpostprocessor.py   ← Neo4jPostProcessorAgent
│   │   ├── simplerag.py            ← SimpleRAGAgent
│   │   └── ... [other agents]
│   │
│   ├── workflows/
│   │   ├── manager.py              ← WorkflowManager (orchestrator)
│   │   ├── base.py                 ← WorkflowConfig, Registry
│   │   ├── schemas.py              ← Input/Output schemas
│   │   └── utils.py                ← Workflow utilities
│   │
│   ├── ModelManager.py             ← ModelFactory
│   ├── VectorStoreManager.py       ← VectorFactory
│   ├── GraphDBManager.py           ← GraphDBFactory
│   ├── state.py                    ← KGGenerationState
│   ├── functionnode.py             ← Helper functions
│   ├── graphaide_api.py            ← GraphAide facade
│   └── query.py                    ← Query interface
│
├── CLAUDE.md                       ← Project instructions
└── ARCHITECTURE.md                 ← This file
```

### Layer 9: Data Models

```
┌──────────────────────────────────────────────────────────────┐
│                    Data Models (Pydantic)                    │
└──────────────────────────────────────────────────────────────┘

Node (from state.py)
  ├─ node_name: str          (as found in text)
  ├─ node_type: str          (from ontology or Wikidata)
  ├─ english_name: str       (canonical form)
  ├─ wikidata_id: str?       (Q-identifier)
  ├─ node_id: str?           (= english_name, for matching)
  └─ raw_source: str?        (reference)

Edge (from state.py)
  ├─ source_id: str          (→ node_id match)
  ├─ target_id: str          (→ node_id match)
  ├─ edge_type: str          (relationship type)
  ├─ edge_name: str          (human-readable)
  └─ raw_source: str?        (reference)

ChunkMetadata (for chunk tracking)
  ├─ chunk_id: str           (SHA256[:12])
  ├─ chunk_hash: str         (full SHA256)
  ├─ file_path: str
  ├─ sequence_num: int       (0-indexed)
  ├─ content_preview: str    (500 chars)
  └─ token_count: int

RAGContext
  ├─ ontology_node_types: List[str]
  ├─ ontology_edge_types: List[str]
  ├─ wikidata_context: Dict[str, Dict]
  └─ retrieval_results: List[RetrievalResult]

IntentSchema
  ├─ subjectivity: float
  ├─ locality: float
  ├─ navigationality: float
  ├─ causality: float
  └─ procedurality: float
```

### Summary Table: Workflow Types

```
┌────────────────────────────────────────────────────────────┐
│        Workflow Types & Their Responsibilities             │
└────────────────────────────────────────────────────────────┘

Workflow          │ Input              │ Output            │ Use Case
──────────────────┼────────────────────┼───────────────────┼─────────
kg_extract        │ file_path,         │ nodes, edges,     │ Extract
                  │ ontology_path      │ JSON file         │ KG only
                  │                    │                   │
kg_ingest         │ file_path,         │ Neo4j loaded,     │ Extract
                  │ ontology_path      │ stats, JSON       │ + Load
                  │                    │                   │
kg_ingest_jsonl   │ JSONL file path    │ Neo4j loaded,     │ Batch
                  │ (multiple files)   │ stats, JSON       │ ingest
                  │                    │                   │
kg_query          │ question           │ answer,           │ Q&A
                  │ (Neo4j required)   │ intent_scores,    │ over KG
                  │                    │ context           │
                  │                    │                   │
kg_load_json      │ JSON file path     │ Neo4j loaded,     │ Load
                  │ (KG extract       │ stats, JSON       │ existing
                  │  output)          │                   │ extract
                  │                    │                   │
vector_db_ingest  │ file_paths         │ Vector store      │ Build
                  │ (documents)        │ indexed, stats    │ RAG
                  │                    │                   │
ontology_generate │ file_path          │ ontology.ttl      │ Auto-gen
                  │ (raw text/pdf)     │ (OWL format)      │ ontology
──────────────────┴────────────────────┴───────────────────┴─────────
```
