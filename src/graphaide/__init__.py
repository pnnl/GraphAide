"""GraphAide - Multi-agentic knowledge graph construction and querying system.

This is the primary import namespace for GraphAide. All public APIs are re-exported here.

Simple Usage:
    from graphaide import GraphAide, ModelConfig, GraphDBConfig

    graphaide = GraphAide(
        model_config=ModelConfig(provider="openai", model_name="gpt-4o"),
        graphdb_config=GraphDBConfig(uri="neo4j://localhost:7687", username="neo4j", password="pwd"),
    )
    result = graphaide.extract(file_path="doc.pdf", ontology_path="ont.ttl")

Advanced Usage:
    from graphgen.v2.workflows.manager import WorkflowManager
    manager = WorkflowManager(global_config=workflow_config)
    result = manager.run("kg_extract", {...})
"""

# Suppress verbose third-party library logs at import time (before they initialize)
import logging
_verbose_libs = [
    "langfuse",
    "langchain",
    "langchain_core",
    "langchain_community",
    "langgraph",
    "httpx",
    "httpcore",
    "urllib3",
    "asyncio",
    "neo4j",
    "chromadb",
    "sentence_transformers",
]
for _lib in _verbose_libs:
    _logger = logging.getLogger(_lib)
    _logger.setLevel(logging.WARNING)
    _logger.propagate = True
    # Remove any existing handlers to prevent them from outputting DEBUG logs
    for _handler in _logger.handlers[:]:
        _handler.setLevel(logging.WARNING)

# Core Configuration Classes
from graphgen.v2.ModelManager import ModelConfig, ModelFactory
from graphgen.v2.GraphDBManager import GraphDBConfig, GraphDBFactory
from graphgen.v2.VectorStoreManager import VectorDBConfig, VectorFactory, IngestType, RetrieveType

# Workflow Orchestration
from graphgen.v2.workflows import (
    WorkflowConfig,
    WorkflowResult,
    WorkflowManager,
)

# Data Models
from graphgen.v2.state import (
    KGGenerationState,
    KGQuestionAnswerState,
    Node,
    Edge,
    MergedNode,
    MergedEdge,
    RAGContext,
)

# Facade API
from graphgen.v2.graphaide_api import GraphAide

# Sample data access
from pathlib import Path
try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files

def get_sample_data_path(filename: str = None) -> Path:
    """Get path to sample data files for demonstrations.

    Args:
        filename: Optional filename to get (e.g., "PNNL_About.pdf").
                 If None, returns sample data directory path.

    Returns:
        Path to sample file or directory.

    Examples:
        from graphaide import get_sample_data_path

        # Get directory
        data_dir = get_sample_data_path()

        # Get specific file
        pdf_path = get_sample_data_path("PNNL_About.pdf")
    """
    try:
        # Use importlib.resources - works with wheels, editable installs, zipped packages
        data_traversable = files('graphgen') / 'data'
        data_dir = Path(str(data_traversable))
    except Exception:
        # Fallback for development: src/graphgen/data
        data_dir = Path(__file__).parent.parent / "graphgen" / "data"

    if filename:
        return data_dir / filename
    return data_dir

from graphgen._version import __version__

__all__ = [
    "__version__",
    # Facade
    "GraphAide",
    "get_sample_data_path",
    # Config Classes
    "ModelConfig",
    "ModelFactory",
    "GraphDBConfig",
    "GraphDBFactory",
    "VectorDBConfig",
    "VectorFactory",
    "IngestType",
    "RetrieveType",
    # Workflow
    "WorkflowConfig",
    "WorkflowResult",
    "WorkflowManager",
    # Data Models
    "KGGenerationState",
    "KGQuestionAnswerState",
    "Node",
    "Edge",
    "MergedNode",
    "MergedEdge",
    "RAGContext",
]
