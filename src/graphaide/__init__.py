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
import sys

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
    # Check multiple locations: env root → site-packages → project root
    candidates = [
        Path(sys.prefix) / "data",           # Installed via data_files
        Path(sys.prefix) / "sample_data",    # Alternative install location
        Path(__file__).parent.parent.parent / "data",  # Local project root
    ]

    sample_dir = None
    for candidate in candidates:
        if candidate.exists():
            sample_dir = candidate
            break

    if not sample_dir:
        # Fallback to project root (for development)
        sample_dir = Path(__file__).parent.parent.parent / "data"

    if filename:
        return sample_dir / filename
    return sample_dir

try:
    from importlib.metadata import version
    __version__ = version("graphaide")
except Exception:
    __version__ = "0.4.8"  # fallback if package not installed

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
