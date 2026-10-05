"""GraphAide Workflows Module - LangGraph-based workflow orchestration.

This module provides unified interface for all GraphAide workflows using LangGraph.
Features:
- Parallel execution with Send() and conditional routing
- Streaming and graph inspection
- Hierarchical configuration (global + per-call overrides)
- High-level run() API for simple usage
- build_workflow() for advanced users wanting full LangGraph control

Two usage patterns:

1. SIMPLE: Use run() for CLI/API/scripts
    from graphgen.v2.workflows import WorkflowManager
    manager = WorkflowManager()
    result = manager.run("kg_extract", {"file_path": "doc.pdf"})
    # Returns: WorkflowResult

2. ADVANCED: Use build_workflow() for full LangGraph power
    manager = WorkflowManager()
    app = manager.build_workflow("kg_ingest")

    # Stream execution with visibility
    for event in app.stream(state):
        print(event)

    # Inspect graph
    app.get_graph().print_ascii()

    # Invoke directly
    result_state = app.invoke(state)

Workflows:
- kg_extract: Extract nodes/edges to JSON (no database)
- kg_ingest: Extract nodes/edges + load to Neo4j (parallel loading)
- kg_query: Natural language query over knowledge graph
"""

from graphgen.v2.workflows.base import (
    WorkflowConfig,
    WorkflowResult,
    WorkflowRegistry,
    WorkflowDefinition,
    WorkflowInfo,
)
from graphgen.v2.workflows.manager import WorkflowManager
from graphgen.v2.workflows.schemas import (
    KGExtractInput,
    KGExtractOutput,
    KGIngestInput,
    KGIngestOutput,
    KGQueryInput,
    KGQueryOutput,
)

__all__ = [
    # Core abstractions
    "WorkflowConfig",
    "WorkflowResult",
    "WorkflowRegistry",
    "WorkflowDefinition",
    "WorkflowInfo",
    "WorkflowManager",
    # Input/output schemas
    "KGExtractInput",
    "KGExtractOutput",
    "KGIngestInput",
    "KGIngestOutput",
    "KGQueryInput",
    "KGQueryOutput",
]
