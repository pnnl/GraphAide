"""GraphAide Core - Shared business logic for CLI and API."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from graphgen.v2 import globalconfig

# Load environment variables from multiple locations
# Priority: repo root → current dir → home/.graphaide → home/
def _load_env():
    """Load .env file from multiple locations in priority order."""

    # Build list of paths to check
    env_paths = []

    # 1. Try to find repo root (src/graphgen/core.py -> graphaide/.env)
    try:
        core_file = Path(__file__)  # /path/to/graphaide/src/graphgen/core.py
        repo_root = core_file.parent.parent.parent  # /path/to/graphaide/
        env_file = repo_root / '.env'
        env_paths.append(env_file)
    except:
        pass

    # 2. Current working directory
    env_paths.append(Path.cwd() / '.env')

    # 3. User home directory ~/.graphaide/.env
    env_paths.append(Path.home() / '.graphaide' / '.env')

    # 4. User home directory ~/.env
    env_paths.append(Path.home() / '.env')

    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for path in env_paths:
        path_str = str(path.resolve())
        if path_str not in seen:
            seen.add(path_str)
            unique_paths.append(path)

    loaded = False
    for env_file in unique_paths:
        if env_file.exists():
            try:
                load_dotenv(str(env_file), override=False)
                if not loaded:
                    print(f"[GraphAide] ✅ Loaded .env from: {env_file}")
                    loaded = True
            except Exception as e:
                print(f"[GraphAide] ⚠️  Failed to load .env from {env_file}: {e}")

    if not loaded:
        print(f"[GraphAide] ℹ️  No .env file found. Checked:")
        for path in unique_paths:
            print(f"  - {path}")

_load_env()


def load_config(config_path: str) -> dict[str, Any]:
    """Load configuration from JSON file and merge with .env secrets.

    Args:
        config_path: Path to JSON config file

    Returns:
        Merged configuration dictionary

    Config file structure:
    {
        "model": {
            "provider": "openai",
            "model_name": "gpt-4o",
            "max_tokens": 8192,
            "temperature": 0.0
        },
        "vector_db": {
            "provider": "ChromaDB",
            "store_name": "GA_VDB",
            "store_path": "./chroma"
        },
        "graph_db": {
            "provider": "neo4j",
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "database": "neo4j"
        },
        "defaults": {
            "ontology_path": "./ontology.owl",
            "max_tokens_per_segment": 4096
        }
    }

    Secrets from .env (not in config file):
        - OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
        - NEO4J_PASSWORD
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Inject secrets from .env into config
    if "model" in config:
        provider = config["model"].get("provider", "").lower()
        if provider == "openai":
            config["model"]["api_key"] = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            config["model"]["api_key"] = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "google":
            config["model"]["api_key"] = os.getenv("GOOGLE_API_KEY")
        elif provider == "bedrock":
            # Bedrock uses AWS credentials from environment
            pass

    if "graph_db" in config:
        config["graph_db"]["password"] = os.getenv("NEO4J_PASSWORD")

    return config


def _build_workflow_config(config: dict[str, Any]):
    """Build WorkflowConfig from config dictionary.

    Args:
        config: Configuration dictionary from load_config()

    Returns:
        WorkflowConfig object
    """
    from graphgen.v2.workflows.base import WorkflowConfig
    from graphgen.v2.ModelManager import ModelConfig
    from graphgen.v2.GraphDBManager import GraphDBConfig
    from graphgen.v2.VectorStoreManager import VectorDBConfig

    workflow_config_kwargs = {}

    # Model config
    if "model" in config:
        model_cfg = config["model"]
        workflow_config_kwargs["model_config"] = ModelConfig(
            provider=model_cfg.get("provider", "openai"),
            model_name=model_cfg.get("model_name", "gpt-4o"),
            api_key=model_cfg.get("api_key"),
            base_url=model_cfg.get("base_url"),
            temperature=model_cfg.get("temperature", 0.0),
            max_output_tokens_limit_llm=model_cfg.get("max_output_tokens_limit_llm", globalconfig.DEFAULT_MAX_OUTPUT_TOKENS_LIMIT_LLM),
        )

    # Graph DB config (optional - use defaults if not provided)
    if "graph_db" in config:
        gdb_cfg = config["graph_db"]
        workflow_config_kwargs["graphdb_config"] = GraphDBConfig(
            provider=gdb_cfg.get("provider", "neo4j"),
            uri=gdb_cfg.get("uri", "bolt://localhost:7687"),
            username=gdb_cfg.get("username", "neo4j"),
            password=gdb_cfg.get("password"),
            database=gdb_cfg.get("database", "neo4j"),
        )
    else:
        # Provide default GraphDB config even if not in config file
        # (allows kg_extract to work without Neo4j)
        workflow_config_kwargs["graphdb_config"] = GraphDBConfig(
            provider="neo4j",
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )

    # Vector DB config
    if "vector_db" in config:
        vdb_cfg = config["vector_db"]
        workflow_config_kwargs["vector_config"] = VectorDBConfig(
            provider=vdb_cfg.get("provider", "ChromaDB"),
            store_name=vdb_cfg.get("store_name", "GA_VDB"),
            store_path=vdb_cfg.get("store_path", "./chroma"),
        )

    # Workflow settings
    if "defaults" in config:
        defaults = config["defaults"]
        if "retry_max_attempts" in defaults:
            workflow_config_kwargs["retry_max_attempts"] = defaults["retry_max_attempts"]

    return WorkflowConfig(**workflow_config_kwargs)


def extract_graph_merge(
    file_path: str,
    ontology_path: Optional[str] = None,
    max_tokens_per_segment: int = 4096,
    filter_by_ontology: bool = True,
    config_path: Optional[str] = None,
) -> dict[str, Any]:
    """Extract knowledge graph and merge duplicate nodes by node_id.

    Args:
        file_path: Path to input text or PDF file
        ontology_path: Optional path to ontology file (.owl, .ttl, .nt)
        max_tokens_per_segment: Max tokens per segment (reduce if LLM fails)
        filter_by_ontology: Filter extracted entities by ontology types (default: True)
        config_path: Optional path to JSON config file

    Returns:
        Dictionary with 'nodes', 'edges', 'stats', and 'output_json_path'
    """
    from graphgen.v2.workflows import WorkflowManager
    from graphgen.v2.workflows.base import WorkflowConfig
    from graphgen.v2.ModelManager import ModelConfig

    # Build workflow config from file if provided
    workflow_config = None
    if config_path:
        config = load_config(config_path)
        # For extract, only use model config (no GraphDB needed)
        if "model" in config:
            model_cfg = config["model"]
            workflow_config = WorkflowConfig(
                model_config=ModelConfig(
                    provider=model_cfg.get("provider", "openai"),
                    model_name=model_cfg.get("model_name", "gpt-4o"),
                    api_key=model_cfg.get("api_key"),
                    base_url=model_cfg.get("base_url") or model_cfg.get("api_endpoint"),
                    temperature=model_cfg.get("temperature", 0.0),
                    max_output_tokens_limit_llm=model_cfg.get("max_output_tokens_limit_llm", globalconfig.DEFAULT_MAX_OUTPUT_TOKENS_LIMIT_LLM),
                    embedding_model_name=model_cfg.get("embedding_model_name"),
                )
            )

    manager = WorkflowManager(global_config=workflow_config)

    result = manager.run(
        "kg_extract_merge",
        inputs={
            "file_path": file_path,
            "ontology_path": ontology_path,
            "max_tokens_per_segment": max_tokens_per_segment,
            "filter_by_ontology": filter_by_ontology,
        },
    )

    # Check if failure is only due to GraphDB connection (not needed for extract)
    if not result.success and result.errors:
        errors = result.errors if isinstance(result.errors, list) else [result.errors]
        graphdb_errors = [e for e in errors if "Neo4j" in str(e) or "Could not connect" in str(e)]

        if graphdb_errors and len(errors) == 1:
            # Only GraphDB error - mark as warning but continue
            sys.stderr.write(f"Warning: GraphDB not available but not needed for extraction. Continuing.\n")
            # If we have partial results, that's okay
            if result.data is None:
                result.data = {}

    if not result.success:
        sys.stderr.write(f"Extract merge failed: {result.errors}\n")

    # Extract metadata from workflow config or environment
    load_dotenv(override=True)  # Reload .env to pick up any updates
    metadata = {}

    # Get model config from workflow_config
    if workflow_config and workflow_config.model_config:
        model_cfg = workflow_config.model_config
        metadata["model_name"] = model_cfg.model_name
        metadata["provider"] = model_cfg.provider
        metadata["api_endpoint"] = model_cfg.base_url or "default"
        if model_cfg.api_key:
            metadata["api_key"] = f"***{model_cfg.api_key[-4:]}" if len(model_cfg.api_key) > 4 else model_cfg.api_key
        else:
            metadata["api_key"] = None
        metadata["temperature"] = model_cfg.temperature
        metadata["max_output_tokens_limit_llm"] = model_cfg.max_output_tokens_limit_llm

        if workflow_config.vector_config:
            vec_cfg = workflow_config.vector_config
            metadata["vector_store_name"] = vec_cfg.store_name
            metadata["vector_store_provider"] = vec_cfg.provider
            metadata["vector_store_path"] = vec_cfg.store_path
    else:
        # Fallback: read directly from environment variables
        provider = None
        for p in ["openai", "anthropic", "google", "bedrock"]:
            if os.getenv(f"{p.upper()}_API_KEY"):
                provider = p
                break

        if provider:
            metadata["provider"] = provider
            metadata["model_name"] = os.getenv(f"{provider.upper()}_MODEL_NAME", "unknown")
            api_key = os.getenv(f"{provider.upper()}_API_KEY")
            metadata["api_key"] = f"***{api_key[-4:]}" if len(api_key) > 4 else api_key
            metadata["api_endpoint"] = os.getenv(f"{provider.upper()}_BASE_URL", "default")
            metadata["temperature"] = float(os.getenv(f"{provider.upper()}_TEMPERATURE", 0.0))
            metadata["max_tokens"] = int(os.getenv(f"{provider.upper()}_MAX_TOKENS", 8192))

        metadata["vector_store_path"] = os.getenv("VECTOR_STORE_PATH", "./chroma")
        metadata["vector_store_name"] = os.getenv("VECTOR_STORE_NAME", "GA_VDB")
        metadata["vector_store_provider"] = "ChromaDB"

    # Convert to dict format (WorkflowResult.data now returns "nodes"/"edges" instead of "merged_nodes"/"merged_edges")
    nodes = result.data.get("nodes", []) if result.data else []
    edges = result.data.get("edges", []) if result.data else []

    return {
        "success": result.success,
        "metadata": metadata,
        "nodes": [_node_to_dict(n) for n in nodes] if nodes else [],
        "edges": [_edge_to_dict(e) for e in edges] if edges else [],
        "segments_processed": result.stats.get("segments_processed", 0),
        "nodes_merged": result.stats.get("nodes_merged", 0),
        "edges_merged": result.stats.get("edges_merged", 0),
        "output_json_path": result.stats.get("output_json_path"),
        "execution_time_seconds": result.execution_time_seconds,
        "errors": result.errors,
    }


def extract_graph(
    file_path: str,
    ontology_path: Optional[str] = None,
    max_tokens_per_segment: int = 4096,
    filter_by_ontology: bool = True,
    config_path: Optional[str] = None,
) -> dict[str, Any]:
    """Extract a knowledge graph from a text/PDF file.

    Args:
        file_path: Path to input text or PDF file
        ontology_path: Optional path to ontology file (.owl, .ttl, .nt)
        max_tokens_per_segment: Max tokens per segment (reduce if LLM fails)
        filter_by_ontology: Filter extracted entities by ontology types (default: True)
        config_path: Optional path to JSON config file

    Returns:
        Dictionary with 'nodes', 'edges', 'stats', and 'output_json_path'
    """
    from graphgen.v2.workflows import WorkflowManager
    from graphgen.v2.workflows.base import WorkflowConfig
    from graphgen.v2.ModelManager import ModelConfig

    # Build workflow config - from file if provided, OR from environment variables
    workflow_config = None

    if config_path:
        # Load from config file
        config = load_config(config_path)
        if "model" in config:
            model_cfg = config["model"]
            workflow_config = WorkflowConfig(
                model_config=ModelConfig(
                    provider=model_cfg.get("provider", "openai"),
                    model_name=model_cfg.get("model_name", "gpt-4o"),
                    api_key=model_cfg.get("api_key"),
                    base_url=model_cfg.get("base_url") or model_cfg.get("api_endpoint"),
                    temperature=model_cfg.get("temperature", 0.0),
                    max_output_tokens_limit_llm=model_cfg.get("max_output_tokens_limit_llm", globalconfig.DEFAULT_MAX_OUTPUT_TOKENS_LIMIT_LLM),
                    embedding_model_name=model_cfg.get("embedding_model_name"),
                )
            )
    else:
        # Load from environment variables (set by load_dotenv() at module startup)
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            provider = "openai" if os.getenv("OPENAI_API_KEY") else \
                      "anthropic" if os.getenv("ANTHROPIC_API_KEY") else \
                      "google"
            model_name = os.getenv(f"{provider.upper()}_MODEL_NAME", "gpt-4o" if provider == "openai" else "claude-opus-4-7")

            workflow_config = WorkflowConfig(
                model_config=ModelConfig(
                    provider=provider,
                    model_name=model_name,
                    api_key=api_key,
                    base_url=os.getenv(f"{provider.upper()}_BASE_URL"),
                    temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.0")),
                    max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "8192")),
                    embedding_model_name=os.getenv("OPENAI_EMBEDDING_MODEL_NAME"),
                )
            )

    manager = WorkflowManager(global_config=workflow_config)

    result = manager.run(
        "kg_extract",
        inputs={
            "file_path": file_path,
            "ontology_path": ontology_path,
            "max_tokens_per_segment": max_tokens_per_segment,
            "filter_by_ontology": filter_by_ontology,
        },
    )

    # Check if failure is only due to GraphDB connection (not needed for extract)
    if not result.success and result.errors:
        errors = result.errors if isinstance(result.errors, list) else [result.errors]
        graphdb_errors = [e for e in errors if "Neo4j" in str(e) or "Could not connect" in str(e)]

        if graphdb_errors and len(errors) == 1:
            # Only GraphDB error - mark as warning but continue
            sys.stderr.write(f"Warning: GraphDB not available but not needed for extraction. Continuing.\n")
            # If we have partial results, that's okay
            if result.nodes is None:
                result.nodes = []
            if result.edges is None:
                result.edges = []

    if not result.success:
        sys.stderr.write(f"Extract failed: {result.errors}\n")

    # Extract metadata from workflow config or environment
    load_dotenv(override=True)  # Reload .env to pick up any updates
    metadata = {}

    # Get model config from workflow_config
    if workflow_config and workflow_config.model_config:
        model_cfg = workflow_config.model_config
        metadata["model_name"] = model_cfg.model_name
        metadata["provider"] = model_cfg.provider
        metadata["api_endpoint"] = model_cfg.base_url or "default"
        if model_cfg.api_key:
            metadata["api_key"] = f"***{model_cfg.api_key[-4:]}" if len(model_cfg.api_key) > 4 else model_cfg.api_key
        else:
            metadata["api_key"] = None
        metadata["temperature"] = model_cfg.temperature
        metadata["max_output_tokens_limit_llm"] = model_cfg.max_output_tokens_limit_llm

        if workflow_config.vector_config:
            vec_cfg = workflow_config.vector_config
            metadata["vector_store_name"] = vec_cfg.store_name
            metadata["vector_store_provider"] = vec_cfg.provider
            metadata["vector_store_path"] = vec_cfg.store_path
    else:
        # Fallback: read directly from environment variables
        provider = None
        for p in ["openai", "anthropic", "google", "bedrock"]:
            if os.getenv(f"{p.upper()}_API_KEY"):
                provider = p
                break

        if provider:
            metadata["provider"] = provider
            metadata["model_name"] = os.getenv(f"{provider.upper()}_MODEL_NAME", "unknown")
            api_key = os.getenv(f"{provider.upper()}_API_KEY")
            metadata["api_key"] = f"***{api_key[-4:]}" if len(api_key) > 4 else api_key
            metadata["api_endpoint"] = os.getenv(f"{provider.upper()}_BASE_URL", "default")
            metadata["temperature"] = float(os.getenv(f"{provider.upper()}_TEMPERATURE", 0.0))
            metadata["max_tokens"] = int(os.getenv(f"{provider.upper()}_MAX_TOKENS", 8192))

        metadata["vector_store_path"] = os.getenv("VECTOR_STORE_PATH", "./chroma")
        metadata["vector_store_name"] = os.getenv("VECTOR_STORE_NAME", "GA_VDB")
        metadata["vector_store_provider"] = "ChromaDB"

    # Convert to dict format
    return {
        "success": result.success,
        "metadata": metadata,
        "nodes": [_node_to_dict(n) for n in result.nodes] if result.nodes else [],
        "edges": [_edge_to_dict(e) for e in result.edges] if result.edges else [],
        "segments_processed": result.stats.get("segments_processed", 0),
        "nodes_extracted": result.stats.get("nodes_extracted", 0),
        "edges_extracted": result.stats.get("edges_extracted", 0),
        "output_json_path": result.stats.get("output_json_path"),
        "execution_time_seconds": result.execution_time_seconds,
        "errors": result.errors,
    }


def ingest_to_neo4j(
    file_path: str,
    ontology_path: Optional[str] = None,
    clear_existing: bool = False,
    max_tokens_per_segment: int = 4096,
    filter_by_ontology: bool = True,
    config_path: Optional[str] = None,
) -> dict[str, Any]:
    """Extract knowledge graph and load it into Neo4j.

    Args:
        file_path: Path to input text or PDF file
        ontology_path: Optional path to ontology file
        clear_existing: Whether to clear existing graph before ingesting
        max_tokens_per_segment: Max tokens per segment (reduce if LLM fails)
        filter_by_ontology: Filter extracted entities by ontology types (default: True)
        config_path: Optional path to JSON config file

    Returns:
        Dictionary with 'nodes_created' and 'edges_created' counts
    """
    from graphgen.v2.workflows import WorkflowManager
    from graphgen.v2.GraphDBManager import GraphDBFactory

    # Build workflow config from file if provided
    workflow_config = None
    if config_path:
        config = load_config(config_path)
        workflow_config = _build_workflow_config(config)

    # Clear graph if requested
    if clear_existing:
        try:
            graphdb_factory = GraphDBFactory()
            driver = graphdb_factory.get_driver()
            if driver:
                driver.execute_query("MATCH (n) DETACH DELETE n")
                sys.stdout.write("Cleared existing graph\n")
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to clear graph: {e}\n")

    manager = WorkflowManager(global_config=workflow_config)

    result = manager.run(
        "kg_ingest",
        inputs={
            "file_path": file_path,
            "ontology_path": ontology_path,
            "max_tokens_per_segment": max_tokens_per_segment,
            "filter_by_ontology": filter_by_ontology,
        },
    )

    if not result.success:
        sys.stderr.write(f"Ingest failed: {result.errors}\n")

    return {
        "success": result.success,
        "nodes_created": result.stats.get("nodes_created", 0),
        "edges_created": result.stats.get("edges_created", 0),
        "segments_processed": result.stats.get("segments_processed", 0),
        "execution_time_seconds": result.execution_time_seconds,
        "errors": result.errors,
    }


def load_json_to_neo4j(
    json_path: str,
    clear_existing: bool = False,
    config_path: Optional[str] = None,
) -> dict[str, Any]:
    """Load pre-extracted JSON directly into Neo4j.

    The JSON file should be in the format produced by extract_graph(),
    containing 'nodes' and 'edges' arrays. Uses kg_load_json workflow
    which includes postprocessing to convert edge types and add labels.

    Args:
        json_path: Path to JSON file with nodes and edges
        clear_existing: Whether to clear existing graph before loading
        config_path: Optional path to JSON config file

    Returns:
        Dictionary with 'nodes_created' and 'edges_created' counts
    """
    from graphgen.v2.workflows import WorkflowManager
    from graphgen.v2.workflows.base import WorkflowConfig
    from graphgen.v2.ModelManager import ModelConfig
    from graphgen.v2.GraphDBManager import GraphDBConfig

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    # Load JSON to verify it's valid
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # Build workflow config
    workflow_config = None
    if config_path:
        config = load_config(config_path)
        if "model" in config:
            model_cfg = config["model"]
            workflow_config = WorkflowConfig(
                model_config=ModelConfig(
                    provider=model_cfg.get("provider", "openai"),
                    model_name=model_cfg.get("model_name", "gpt-4o"),
                    api_key=model_cfg.get("api_key"),
                    base_url=model_cfg.get("base_url") or model_cfg.get("api_endpoint"),
                    temperature=model_cfg.get("temperature", 0.0),
                    max_output_tokens_limit_llm=model_cfg.get("max_output_tokens_limit_llm", globalconfig.DEFAULT_MAX_OUTPUT_TOKENS_LIMIT_LLM),
                    embedding_model_name=model_cfg.get("embedding_model_name"),
                )
            )
        if "graph_db" in config:
            gdb_cfg = config["graph_db"]
            workflow_config.graphdb_config = GraphDBConfig(
                provider=gdb_cfg.get("provider", "neo4j"),
                uri=gdb_cfg.get("uri", os.getenv("NEO4J_URI", "bolt://localhost:7687")),
                username=gdb_cfg.get("username", os.getenv("NEO4J_USERNAME", "neo4j")),
                password=gdb_cfg.get("password", os.getenv("NEO4J_PASSWORD")),
                database=gdb_cfg.get("database", "neo4j"),
            )

    # Create workflow manager and run kg_load_json
    manager = WorkflowManager(global_config=workflow_config)

    sys.stdout.write(f"Loading {len(nodes)} nodes and {len(edges)} edges from {json_path}\n")

    # Run kg_load_json workflow (includes postprocessor for edge types + labels)
    try:
        result = manager.run(
            "kg_load_json",
            inputs={
                "json_path": json_path,
                "clear_existing": clear_existing,
            },
        )

        nodes_created = result.stats.get("nodes_created", 0)
        edges_created = result.stats.get("edges_created", 0)

        return {
            "success": result.success,
            "nodes_created": nodes_created,
            "edges_created": edges_created,
            "execution_time_seconds": result.execution_time_seconds,
            "errors": result.errors,
        }
    except Exception as e:
        sys.stderr.write(f"Error loading JSON: {e}\n")
        return {
            "success": False,
            "nodes_created": 0,
            "edges_created": 0,
            "execution_time_seconds": 0,
            "errors": str(e),
        }


def query_graph(question: str, config_path: Optional[str] = None) -> dict[str, Any]:
    """Query the knowledge graph with a natural language question.

    Args:
        question: Natural language question
        config_path: Optional path to JSON config file

    Returns:
        Dictionary with answer and related graph elements
    """
    from graphgen.v2.workflows import WorkflowManager

    # Build workflow config from file if provided
    workflow_config = None
    if config_path:
        config = load_config(config_path)
        workflow_config = _build_workflow_config(config)

    manager = WorkflowManager(global_config=workflow_config)

    result = manager.run(
        "kg_query",
        inputs={"question": question},
    )

    if not result.success:
        sys.stderr.write(f"Query failed: {result.errors}\n")

    return {
        "success": result.success,
        "question": question,
        "answer": result.answer,
        "graph_answer": result.data.get("graph_answer") if result.data else None,
        "graph_answer_text": result.data.get("graph_answer_text") if result.data else None,
        "related_nodes": [_node_to_dict(n) for n in result.nodes],
        "related_edges": [_edge_to_dict(e) for e in result.edges],
        "execution_time_seconds": result.execution_time_seconds,
        "errors": result.errors,
    }


def _node_to_dict(node) -> dict:
    """Convert Node to dictionary."""
    if hasattr(node, "model_dump"):
        return node.model_dump()
    elif isinstance(node, dict):
        return node
    return {"node_name": str(node)}


def _edge_to_dict(edge) -> dict:
    """Convert Edge to dictionary."""
    if hasattr(edge, "model_dump"):
        return edge.model_dump()
    elif isinstance(edge, dict):
        return edge
    return {"edge_type": str(edge)}


def ingest_to_vectordb(
    file_paths: list[str],
    split_docs: bool = True,
    append: bool = False,
    config_path: Optional[str] = None,
) -> dict[str, Any]:
    """Load documents into vector store for semantic search.

    Args:
        file_paths: List of file paths to load (PDF, TXT, JSON, CSV, YAML)
        split_docs: Whether to split documents into chunks
        append: Whether to append to existing vector store or replace
        config_path: Optional path to JSON config file

    Returns:
        Dictionary with 'documents_loaded', 'chunks_created', and vector store info
    """
    from graphgen.v2.workflows import WorkflowManager
    from graphgen.v2.workflows.base import WorkflowConfig
    from graphgen.v2.VectorStoreManager import VectorDBConfig

    # Build workflow config from file if provided
    workflow_config = None
    if config_path:
        config = load_config(config_path)
        if "vector_db" in config:
            vdb_cfg = config["vector_db"]
            workflow_config = WorkflowConfig(
                vector_config=VectorDBConfig(
                    provider=vdb_cfg.get("provider", "ChromaDB"),
                    store_name=vdb_cfg.get("store_name", "GA_VDB"),
                    store_path=vdb_cfg.get("store_path", "./chroma"),
                )
            )

    manager = WorkflowManager(global_config=workflow_config)

    result = manager.run(
        "vectordb_ingest",
        inputs={
            "file_paths": file_paths,
            "split_docs": split_docs,
            "append": append,
        },
    )

    if not result.success:
        sys.stderr.write(f"VectorDB ingest failed: {result.errors}\n")

    return {
        "success": result.success,
        "documents_loaded": result.stats.get("documents_loaded", 0),
        "chunks_created": result.stats.get("chunks_created", 0),
        "vector_store_name": result.stats.get("vector_store_name", "GA_VDB"),
        "vector_store_path": result.stats.get("vector_store_path", "./chroma"),
        "execution_time_seconds": result.execution_time_seconds,
        "errors": result.errors,
    }


def visualize_vector_store(
    reuse_embedding: bool = False,
    output_dir: str = "./data",
    config_path: Optional[str] = None,
) -> dict[str, Any]:
    """Create 2D UMAP visualization of vector embeddings.

    Generates visualization and stores it in /data folder as interactive HTML.

    Args:
        reuse_embedding: Whether to reuse existing UMAP projection if available
        output_dir: Directory to save visualization outputs (default: ./data)
        config_path: Optional path to JSON config file

    Returns:
        Dictionary with paths to projection file, visualization image, and metadata
    """
    from graphgen.v2.workflows import WorkflowManager

    manager = WorkflowManager()

    result = manager.run(
        "vectordb_visualize",
        inputs={
            "reuse_embedding": reuse_embedding,
            "output_dir": output_dir,
        },
    )

    if not result.success:
        sys.stderr.write(f"VectorDB visualization failed: {result.errors}\n")

    return {
        "success": result.success,
        "projection_file_path": result.data.get("projection_file_path", "") if result.data else "",
        "visualization_image_path": result.data.get("visualization_image_path", "") if result.data else "",
        "projection_metadata_path": result.data.get("projection_metadata_path", "") if result.data else "",
        "num_embeddings_projected": result.stats.get("num_embeddings_projected", 0),
        "execution_time_seconds": result.execution_time_seconds,
        "errors": result.errors,
    }
