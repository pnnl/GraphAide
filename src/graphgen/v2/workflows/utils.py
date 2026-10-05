"""Utility functions for workflow system."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from graphgen.v2.ModelManager import ModelFactory, ModelConfig
from graphgen.v2.VectorStoreManager import VectorFactory
from graphgen.v2.GraphDBManager import GraphDBFactory
from graphgen.v2.agents.AgentManager import AgentFactory
from graphgen.v2.state import KGGenerationState, KGQuestionAnswerState, RAGContext

from .base import WorkflowConfig


# ============================================================================
# FACTORY INITIALIZATION
# ============================================================================

def get_agent_factory(config: Optional[WorkflowConfig] = None) -> AgentFactory:
    """Initialize and return the AgentFactory with all required dependencies.

    Args:
        config: Optional WorkflowConfig with model/db overrides

    Returns:
        Initialized AgentFactory
    """
    load_dotenv()

    # Create model factory with optional config override
    model_factory = ModelFactory(model_config=config.model_config if config else None)

    # Create vector store factory
    vector_factory = VectorFactory(model_factory=model_factory,
                                  vectordb_config=config.vector_config if config else None)

    # Create graph database factory
    graphdb_factory = GraphDBFactory(graphdb_config=config.graphdb_config if config else None)

    # Create agent factory
    return AgentFactory(
        model_factory=model_factory,
        vector_store_factory=vector_factory,
        graphdb_factory=graphdb_factory,
    )


# ============================================================================
# STATE INITIALIZATION
# ============================================================================

def init_kg_generation_state(
    file_path: Optional[str] = None,
    input_text: Optional[str] = None,
    ontology_path: Optional[str] = None,
    ontology_node_types: Optional[list[str]] = None,
    ontology_edge_types: Optional[list[str]] = None,
    max_tokens_per_segment: int = 4096,
    nodes: Optional[list] = None,
    edges: Optional[list] = None,
    filter_by_ontology: bool = False,
) -> KGGenerationState:
    """Initialize a KGGenerationState for knowledge graph workflows.

    Args:
        file_path: Optional path to input file
        input_text: Optional raw text to process (used if file_path not provided)
        ontology_path: Optional path to ontology file
        ontology_node_types: Optional list of node types from ontology (migrated to rag_context)
        ontology_edge_types: Optional list of edge types from ontology (migrated to rag_context)
        max_tokens_per_segment: Max tokens per segment (default 4096, reduce if LLM fails)
        nodes: Optional pre-extracted nodes (for kg_load_json workflow)
        edges: Optional pre-extracted edges (for kg_load_json workflow)

    Returns:
        Initialized KGGenerationState
    """
    # Generate output JSON path in same directory as input file (or cwd if input_text)
    input_dir = Path(file_path).parent.absolute() if file_path else Path.cwd()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_json_path = str(input_dir / f"GraphAide_KG_Extract_{timestamp}.json")

    # Initialize RAG context with ontology types if provided
    rag_context = RAGContext(
        ontology_node_types=ontology_node_types or [],
        ontology_edge_types=ontology_edge_types or [],
    ) if (ontology_node_types or ontology_edge_types) else None

    return {
        "file_path": file_path,
        "input_text": input_text,
        "raw_text": "",
        "segments": [],
        "unstructured_response": [],
        "nodes": nodes or [],
        "edges": edges or [],
        "merged_nodes": [],
        "merged_edges": [],
        "messages": [],
        "ontology_file_path": ontology_path,
        "filter_by_ontology": filter_by_ontology,
        "rag_context": rag_context,
        "node_types": [],
        "edge_types": [],
        "output_path": "ontology.nt",
        "batch_index": None,
        "total_batches": None,
        "current_agent": [],
        "agent_status": {},
        "is_raw_embedding": False,
        "embedding_file_path": None,
        "reuse_embedding_file_path": False,
        "append": False,
        "section_chunking": False,
        "max_characters": None,
        "max_tokens_per_segment": max_tokens_per_segment,
        "output_json_path": output_json_path,
    }


def init_kg_qa_state(question: str) -> KGQuestionAnswerState:
    """Initialize a KGQuestionAnswerState for query workflows.

    Args:
        question: The question to ask

    Returns:
        Initialized KGQuestionAnswerState
    """
    return {
        "question": question,
        "extended_QA_pairs": [],
        "extended_QC_pairs": [],
        "answer": None,
        "graph_question": None,
        "graph_answer": None,
        "graph_answer_text": None,
        "intent_scores": None,
        "related_nodes": [],
        "related_edges": [],
        "is_answered": False,
        "messages": [],
    }


# ============================================================================
# CONFIGURATION UTILITIES
# ============================================================================

def merge_configs(
    global_config: Optional[WorkflowConfig],
    override_config: Optional[WorkflowConfig],
) -> WorkflowConfig:
    """Merge two workflow configs (override takes precedence).

    Args:
        global_config: Base/global configuration
        override_config: Overrides to apply

    Returns:
        Merged WorkflowConfig
    """
    if global_config is None:
        global_config = WorkflowConfig()

    if override_config is None:
        return WorkflowConfig(**global_config.__dict__)

    return global_config.merge_with(override_config)


# ============================================================================
# FILE HANDLING UTILITIES
# ============================================================================

def file_exists(file_path: str) -> bool:
    """Check if file exists.

    Args:
        file_path: Path to check

    Returns:
        True if file exists and is readable
    """
    return os.path.exists(file_path) and os.path.isfile(file_path)


def validate_file_path(file_path: str, extensions: Optional[list[str]] = None) -> bool:
    """Validate that file exists and optionally has allowed extension.

    Args:
        file_path: Path to validate
        extensions: Optional list of allowed extensions (e.g., [".pdf", ".txt"])

    Returns:
        True if valid

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If extension not allowed
    """
    if not file_exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if extensions:
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in [e.lower() for e in extensions]:
            raise ValueError(
                f"File extension '{ext}' not in allowed: {extensions}"
            )

    return True


# ============================================================================
# RESULT AGGREGATION
# ============================================================================

def aggregate_stats(
    stats_list: list[Dict[str, Any]],
    numeric_keys: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """Aggregate statistics from multiple workflow runs.

    Args:
        stats_list: List of stats dictionaries
        numeric_keys: List of keys to sum (default: auto-detect)

    Returns:
        Aggregated stats dictionary
    """
    if not stats_list:
        return {}

    # Auto-detect numeric keys if not provided
    if numeric_keys is None:
        numeric_keys = []
        if stats_list:
            first = stats_list[0]
            for k, v in first.items():
                if isinstance(v, (int, float)):
                    numeric_keys.append(k)

    aggregated = {}
    for key in numeric_keys:
        aggregated[key] = sum(s.get(key, 0) for s in stats_list)

    return aggregated


# ============================================================================
# ENVIRONMENT UTILITIES
# ============================================================================

def ensure_env_loaded() -> None:
    """Ensure environment variables are loaded from .env file."""
    load_dotenv()


def get_env_or_raise(key: str) -> str:
    """Get environment variable or raise error if missing.

    Args:
        key: Environment variable name

    Returns:
        Environment variable value

    Raises:
        ValueError: If environment variable not set
    """
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Required environment variable '{key}' not set")
    return value
