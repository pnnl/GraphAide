"""GraphAide CLI - Command-line interface for knowledge graph operations."""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from graphgen.core import (
    extract_graph,
    extract_graph_merge,
    ingest_to_neo4j,
    load_json_to_neo4j,
    query_graph,
    ingest_to_vectordb,
    visualize_vector_store,
)
from graphgen.v2.utils import setup_logging
from graphaide import __version__

app = typer.Typer(
    name="graphaide",
    help="GraphAide - Multi-agentic knowledge graph construction and querying",
    add_completion=False,
)
console = Console()
logger = logging.getLogger("graphgen.cli")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"GraphAide version {__version__}")
        raise typer.Exit()


def print_version_callback(value: bool) -> None:
    """Print version callback for global --version option."""
    if value:
        version_callback(True)


# Note: max_tokens_per_segment controls INPUT chunk size (CLI --max-tokens-per-segment)
# For LLM output token limit, see max_output_tokens_limit_llm in ModelConfig
@app.command()
def extract(
    input_file: Path = typer.Argument(..., help="Input text or PDF file"),
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
    ontology: Optional[Path] = typer.Option(
        None, "--ontology", "-o", help="Ontology file (.owl, .ttl, .nt)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-O", help="Output JSON file (default: auto-generated)"
    ),
    max_tokens_per_segment: int = typer.Option(
        4096, "--max-tokens-per-segment", "-m", help="Max tokens per input segment (input chunk size to LLM, reduce if LLM fails)"
    ),
    max_output_tokens: Optional[int] = typer.Option(
        None, "--max-output-tokens", help="Max output tokens for LLM (default: from globalconfig). Overrides config file value"
    ),
    filter_by_ontology: bool = typer.Option(
        True, "--filter-by-ontology/--no-filter", help="Filter extracted entities by ontology types (default: True)"
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="JSON config file for model/db settings"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="LLM model name (e.g., claude-haiku-4-5-20251001-v1-project)",
    ),
    endpoint: Optional[str] = typer.Option(
        None,
        "--endpoint",
        help="API endpoint URL (e.g., https://ai-incubator-api.pnnl.gov)",
    ),
    password: Optional[str] = typer.Option(
        None, "--password", help="API key for LLM provider"
    ),
    api_key_var: Optional[str] = typer.Option(
        None, "--api-key-var", help="Environment variable name containing API key (e.g., KBASE_EVAL_API_KEY). Overrides --password"
    ),
    provider: str = typer.Option(
        "openai", "--provider", help="LLM provider (openai, anthropic, google, bedrock)"
    ),
    embedding_model: Optional[str] = typer.Option(
        None, "--embedding-model", help="Embedding model name (e.g., text-embedding-3-small)"
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    log_file: Optional[str] = typer.Option(
        None, "--log-file", help="Log file path (default: graphaide_run_<date>.log)"
    ),
    pretty: bool = typer.Option(True, "--pretty/--compact", help="Pretty-print JSON"),
):
    """Extract a knowledge graph from text/PDF and return as JSON.

    Example:
        graphaide extract document.pdf -o ontology.owl
        graphaide extract document.pdf --config config.json
        graphaide extract document.pdf --max-tokens-per-segment 2048
        graphaide extract document.pdf --log-level DEBUG
        graphaide extract document.pdf --log-level DEBUG --log-file debug.log
        graphaide extract document.pdf --model claude-haiku-4-5 --endpoint https://api.pnnl.gov --password sk-...
        graphaide extract document.pdf --embedding-model "text-embedding-multilingual-e5-base"
    """
    # Setup logging with specified level and optional log file
    setup_logging(log_level=log_level, log_file=log_file)
    logger.info(f"GraphAide version {__version__} started")

    if not input_file.exists():
        console.print(f"[red]Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    # Set dummy NEO4J vars if not already set (kg_extract doesn't use GraphDB but needs factory initialized)
    if not os.getenv("NEO4J_URI"):
        os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    if not os.getenv("NEO4J_USERNAME"):
        os.environ["NEO4J_USERNAME"] = "neo4j"
    if not os.getenv("NEO4J_PASSWORD"):
        os.environ["NEO4J_PASSWORD"] = "neo4j"

    # Resolve API key: api_key_var > password
    resolved_password = password
    if api_key_var:
        resolved_password = os.getenv(api_key_var)
        if not resolved_password:
            console.print(f"[red]Error: Environment variable '{api_key_var}' not found[/red]")
            raise typer.Exit(1)

    # Generate config file if model/endpoint/password/provider/embedding_model/max_output_tokens provided
    config_to_use = config
    if model or endpoint or resolved_password or provider != "openai" or embedding_model or max_output_tokens:
        config_data = {
            "model": {
                "provider": provider.lower(),
                "model_name": model,
                "temperature": 1.0,
            }
        }

        if embedding_model:
            config_data["model"]["embedding_model_name"] = embedding_model
        if endpoint:
            config_data["model"]["api_endpoint"] = endpoint
        if resolved_password:
            config_data["model"]["api_key"] = resolved_password
        if max_output_tokens:
            config_data["model"]["max_output_tokens_limit_llm"] = max_output_tokens
            # Set env var based on provider
            if provider.lower() == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = resolved_password
            elif provider.lower() == "openai":
                os.environ["OPENAI_API_KEY"] = resolved_password

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_to_use = Path(f.name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Extracting knowledge graph...", total=None)

        result = extract_graph(
            file_path=str(input_file),
            ontology_path=str(ontology) if ontology else None,
            max_tokens_per_segment=max_tokens_per_segment,
            filter_by_ontology=filter_by_ontology,
            config_path=str(config_to_use) if config_to_use else None,
        )

    if not result.get("success", False):
        console.print(f"[red]Extraction failed: {result.get('errors')}[/red]")
        raise typer.Exit(1)

    # Show results
    console.print("[green]Extraction complete![/green]")
    console.print(f"  Nodes: {result.get('nodes_extracted', 0)}")
    console.print(f"  Edges: {result.get('edges_extracted', 0)}")
    console.print(f"  Segments: {result.get('segments_processed', 0)}")
    console.print(f"  Time: {result.get('execution_time_seconds', 0):.2f}s")

    # Auto-saved JSON
    if result.get("output_json_path"):
        console.print(f"  Saved to: {result['output_json_path']}")

    # Additional output if requested
    if output:
        indent = 2 if pretty else None
        json_output = json.dumps(result, indent=indent, default=str)
        output.write_text(json_output)
        console.print(f"  Also saved to: {output}")


@app.command()
def extract_merge(
    input_file: Path = typer.Argument(..., help="Input text or PDF file"),
    ontology: Optional[Path] = typer.Option(
        None, "--ontology", "-o", help="Ontology file (.owl, .ttl, .nt)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-O", help="Output JSON file (default: auto-generated)"
    ),
    max_tokens_per_segment: int = typer.Option(
        4096, "--max-tokens-per-segment", "-m", help="Max tokens per input segment (input chunk size to LLM, reduce if LLM fails)"
    ),
    max_output_tokens: Optional[int] = typer.Option(
        None, "--max-output-tokens", help="Max output tokens for LLM (default: from globalconfig). Overrides config file value"
    ),
    filter_by_ontology: bool = typer.Option(
        True, "--filter-by-ontology/--no-filter", help="Filter extracted entities by ontology types (default: True)"
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="JSON config file for model/db settings"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="LLM model name (e.g., claude-haiku-4-5-20251001-v1-project)",
    ),
    endpoint: Optional[str] = typer.Option(
        None,
        "--endpoint",
        help="API endpoint URL (e.g., https://ai-incubator-api.pnnl.gov)",
    ),
    password: Optional[str] = typer.Option(
        None, "--password", help="API key for LLM provider"
    ),
    api_key_var: Optional[str] = typer.Option(
        None, "--api-key-var", help="Environment variable name containing API key (e.g., KBASE_EVAL_API_KEY). Overrides --password"
    ),
    provider: str = typer.Option(
        "openai", "--provider", help="LLM provider (openai, anthropic, google, bedrock)"
    ),
    embedding_model: Optional[str] = typer.Option(
        None, "--embedding-model", help="Embedding model name (e.g., text-embedding-3-small)"
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    log_file: Optional[str] = typer.Option(
        None, "--log-file", help="Log file path (default: graphaide_run_<date>.log)"
    ),
    pretty: bool = typer.Option(True, "--pretty/--compact", help="Pretty-print JSON"),
):
    """Extract a knowledge graph and merge duplicate nodes by node_id.

    Example:
        graphaide extract-merge document.pdf -o ontology.owl
        graphaide extract-merge document.pdf --config config.json
        graphaide extract-merge document.pdf --max-tokens-per-segment 2048
        graphaide extract-merge document.pdf --log-level DEBUG
    """
    # Setup logging with specified level and optional log file
    setup_logging(log_level=log_level, log_file=log_file)
    logger.info(f"GraphAide version {__version__} started")

    if not input_file.exists():
        console.print(f"[red]Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    # Set dummy NEO4J vars if not already set (kg_extract_merge doesn't use GraphDB but needs factory initialized)
    if not os.getenv("NEO4J_URI"):
        os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    if not os.getenv("NEO4J_USERNAME"):
        os.environ["NEO4J_USERNAME"] = "neo4j"
    if not os.getenv("NEO4J_PASSWORD"):
        os.environ["NEO4J_PASSWORD"] = "neo4j"

    # Resolve API key: api_key_var > password
    resolved_password = password
    if api_key_var:
        resolved_password = os.getenv(api_key_var)
        if not resolved_password:
            console.print(f"[red]Error: Environment variable '{api_key_var}' not found[/red]")
            raise typer.Exit(1)

    # Generate config file if model/endpoint/password/provider/embedding_model/max_output_tokens provided
    config_to_use = config
    if model or endpoint or resolved_password or provider != "openai" or embedding_model or max_output_tokens:
        config_data = {
            "model": {
                "provider": provider.lower(),
                "model_name": model,
                "temperature": 1.0,
            }
        }

        if embedding_model:
            config_data["model"]["embedding_model_name"] = embedding_model
        if endpoint:
            config_data["model"]["api_endpoint"] = endpoint
        if resolved_password:
            config_data["model"]["api_key"] = resolved_password
        if max_output_tokens:
            config_data["model"]["max_output_tokens_limit_llm"] = max_output_tokens
            # Set env var based on provider
            if provider.lower() == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = resolved_password
            elif provider.lower() == "openai":
                os.environ["OPENAI_API_KEY"] = resolved_password

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_to_use = Path(f.name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Extracting and merging knowledge graph...", total=None)

        result = extract_graph_merge(
            file_path=str(input_file),
            ontology_path=str(ontology) if ontology else None,
            max_tokens_per_segment=max_tokens_per_segment,
            filter_by_ontology=filter_by_ontology,
            config_path=str(config_to_use) if config_to_use else None,
        )

    if not result.get("success", False):
        console.print(f"[red]Extraction failed: {result.get('errors')}[/red]")
        raise typer.Exit(1)

    # Show results
    console.print("[green]Extraction and merge complete![/green]")
    console.print(f"  Nodes merged: {result.get('nodes_merged', 0)}")
    console.print(f"  Edges merged: {result.get('edges_merged', 0)}")
    console.print(f"  Segments: {result.get('segments_processed', 0)}")
    console.print(f"  Time: {result.get('execution_time_seconds', 0):.2f}s")

    # Auto-saved JSON
    if result.get("output_json_path"):
        console.print(f"  Saved to: {result['output_json_path']}")

    # Additional output if requested
    if output:
        indent = 2 if pretty else None
        json_output = json.dumps(result, indent=indent, default=str)
        output.write_text(json_output)
        console.print(f"  Also saved to: {output}")


@app.command()
def ingest(
    input_file: Path = typer.Argument(..., help="Input text or PDF file"),
    ontology: Optional[Path] = typer.Option(
        None, "--ontology", "-o", help="Ontology file (.owl, .ttl, .nt)"
    ),
    max_tokens_per_segment: int = typer.Option(
        4096, "--max-tokens-per-segment", "-m", help="Max tokens per input segment (input chunk size to LLM, reduce if LLM fails)"
    ),
    max_output_tokens: Optional[int] = typer.Option(
        None, "--max-output-tokens", help="Max output tokens for LLM (default: from globalconfig). Overrides config file value"
    ),
    filter_by_ontology: bool = typer.Option(
        True, "--filter-by-ontology/--no-filter", help="Filter extracted entities by ontology types (default: True)"
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="JSON config file for model/db settings"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="LLM model name (e.g., claude-haiku-4-5-20251001-v1-project)",
    ),
    endpoint: Optional[str] = typer.Option(
        None,
        "--endpoint",
        help="API endpoint URL (e.g., https://ai-incubator-api.pnnl.gov)",
    ),
    password: Optional[str] = typer.Option(
        None, "--password", help="API key for LLM provider"
    ),
    api_key_var: Optional[str] = typer.Option(
        None, "--api-key-var", help="Environment variable name containing API key (e.g., KBASE_EVAL_API_KEY). Overrides --password"
    ),
    provider: str = typer.Option(
        "openai", "--provider", help="LLM provider (openai, anthropic, google, bedrock)"
    ),
    embedding_model: Optional[str] = typer.Option(
        None, "--embedding-model", help="Embedding model name (e.g., text-embedding-3-small)"
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Clear existing graph before ingesting"
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    log_file: Optional[str] = typer.Option(
        None, "--log-file", help="Log file path (default: graphaide_run_<date>.log)"
    ),
):
    """Extract knowledge graph and load it into Neo4j.

    Example:
        graphaide ingest document.pdf -o ontology.owl
        graphaide ingest document.pdf --config config.json
        graphaide ingest document.pdf --max-tokens-per-segment 2048 --clear
        graphaide ingest document.pdf --embedding-model "text-embedding-multilingual-e5-base"
        graphaide ingest document.pdf --log-level DEBUG
    """
    # Setup logging with specified level and optional log file
    setup_logging(log_level=log_level, log_file=log_file)
    logger.info(f"GraphAide version {__version__} started")

    if not input_file.exists():
        console.print(f"[red]Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    # Resolve API key: api_key_var > password
    resolved_password = password
    if api_key_var:
        resolved_password = os.getenv(api_key_var)
        if not resolved_password:
            console.print(f"[red]Error: Environment variable '{api_key_var}' not found[/red]")
            raise typer.Exit(1)

    # Generate config file if model/endpoint/password/provider/embedding_model/max_output_tokens provided
    config_to_use = config
    if model or endpoint or resolved_password or provider != "openai" or embedding_model or max_output_tokens:
        config_data = {
            "model": {
                "provider": provider.lower(),
                "model_name": model,
                "temperature": 1.0,
            }
        }

        if embedding_model:
            config_data["model"]["embedding_model_name"] = embedding_model
        if endpoint:
            config_data["model"]["api_endpoint"] = endpoint
        if resolved_password:
            config_data["model"]["api_key"] = resolved_password
        if max_output_tokens:
            config_data["model"]["max_output_tokens_limit_llm"] = max_output_tokens
            # Set env var based on provider
            if provider.lower() == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = resolved_password
            elif provider.lower() == "openai":
                os.environ["OPENAI_API_KEY"] = resolved_password

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_to_use = Path(f.name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=None)

        progress.update(task, description="Extracting and loading to Neo4j...")
        result = ingest_to_neo4j(
            file_path=str(input_file),
            ontology_path=str(ontology) if ontology else None,
            clear_existing=clear,
            max_tokens_per_segment=max_tokens_per_segment,
            filter_by_ontology=filter_by_ontology,
            config_path=str(config_to_use) if config_to_use else None,
        )

    if not result.get("success", False):
        console.print(f"[red]Ingestion failed: {result.get('errors')}[/red]")
        raise typer.Exit(1)

    console.print("[green]Successfully ingested into Neo4j[/green]")
    console.print(f"  Nodes created: {result.get('nodes_created', 0)}")
    console.print(f"  Edges created: {result.get('edges_created', 0)}")
    console.print(f"  Segments: {result.get('segments_processed', 0)}")
    console.print(f"  Time: {result.get('execution_time_seconds', 0):.2f}s")


@app.command()
def load_json(
    json_file: Path = typer.Argument(..., help="JSON file from extract endpoint"),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="JSON config file for model/db settings"
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Clear existing graph before loading"
    ),
):
    """Load pre-extracted JSON file directly into Neo4j.

    The JSON file should be in the format produced by the extract command,
    containing 'nodes' and 'edges' arrays.

    Example:
        graphaide load-json GraphAide_KG_Extract_*.json
        graphaide load-json GraphAide_KG_Extract_*.json --config config.json
        graphaide load-json GraphAide_KG_Extract_*.json --clear
    """
    if not json_file.exists():
        console.print(f"[red]Error: JSON file not found: {json_file}[/red]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Loading JSON into Neo4j...", total=None)

        result = load_json_to_neo4j(
            json_path=str(json_file),
            clear_existing=clear,
            config_path=str(config) if config else None,
        )

    if not result.get("success", False):
        console.print(f"[red]Load failed: {result.get('message')}[/red]")
        raise typer.Exit(1)

    console.print("[green]Successfully loaded JSON into Neo4j![/green]")
    # console.print(f"  Total nodes in graph: {result.get('nodes_created', 0)}")
    # console.print(f"  Total edges in graph: {result.get('edges_created', 0)}")


@app.command()
def load_vector(
    file_paths: Optional[List[str]] = typer.Option(
        None,
        "--file-paths",
        "-f",
        help="Comma-separated file paths to load (e.g., 'file1.pdf,file2.pdf')",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="JSON config file for model/db settings"
    ),
    store_name: Optional[str] = typer.Option(
        None, "--store-name", "-s", help="Vector store collection name (default: GA_VDB)"
    ),
    store_path: Optional[str] = typer.Option(
        None, "--store-path", "-p", help="Vector store storage path (default: ./chroma)"
    ),
    provider: str = typer.Option(
        "ChromaDB", "--provider", help="Vector store provider (ChromaDB or Qdrant)"
    ),
    split: bool = typer.Option(
        True, "--split/--no-split", help="Split documents into chunks"
    ),
    append: bool = typer.Option(
        True, "--append/--no-append", help="Append to existing vector store"
    ),
):
    """Load documents to vector store using workflow system.

    Supports PDF, TXT, JSON, JSONL, CSV, TSV, and YAML files.
    Documents are automatically embedded using configured embedding model.

    File paths can be specified via:
    - --file-paths with comma-separated values
    - Environment variable VECTOR_STORE_NAME sets collection name
    - --store-name, --store-path, --provider override defaults

    Example:
        graphaide load-vector --file-paths document.pdf
        graphaide load-vector --file-paths "file1.pdf,file2.pdf" --store-name my_collection
        graphaide load-vector --file-paths "data/*.pdf" --store-path /data/vectors --provider ChromaDB
        graphaide load-vector --file-paths doc.pdf --config config.json --store-name project_docs
    """
    if not file_paths:
        console.print("[red]Error: --file-paths is required[/red]")
        raise typer.Exit(1)

    # Parse comma-separated file paths
    file_list = []
    for fp in file_paths:
        # Split by comma and strip whitespace
        file_list.extend([f.strip() for f in fp.split(",")])

    # Verify all files exist
    missing_files = [f for f in file_list if not Path(f).exists()]
    if missing_files:
        console.print(f"[red]Error: Files not found: {', '.join(missing_files)}[/red]")
        raise typer.Exit(1)

    # Set vector store env vars if provided via CLI
    if store_name:
        os.environ["VECTOR_STORE_NAME"] = store_name
    if store_path:
        os.environ["VECTOR_STORE_BASEDIR"] = store_path
    if provider:
        os.environ["VECTOR_STORE_PROVIDER"] = provider

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Loading documents to vector store...", total=None)

        try:
            from graphgen.core import ingest_to_vectordb

            result = ingest_to_vectordb(
                file_paths=file_list,
                split_docs=split,
                append=append,
                config_path=str(config) if config else None,
            )

            if result.get("success"):
                console.print("[green]Successfully loaded to vector store![/green]")
                console.print(f"  Files: {len(file_list)}")
                console.print(f"  Store: {result.get('vector_store_name', 'GA_VDB')}")
                console.print(f"  Path: {result.get('vector_store_path', './chroma')}")
                console.print("  Total vectors: (from ingest_to_vectordb result)")
            else:
                console.print(f"[red]Load failed: {result.get('errors')}[/red]")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]Load failed: {str(e)}[/red]")
            import traceback

            traceback.print_exc()
            raise typer.Exit(1)


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask the knowledge graph"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-O", help="Output JSON file (default: stdout)"
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="JSON config file for model/db settings"
    ),
):
    """Query the knowledge graph with a natural language question.

    Example:
        graphaide query "What organizations are mentioned?"
        graphaide query "What organizations are mentioned?" --config config.json
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Querying knowledge graph...", total=None)
        result = query_graph(
            question=question,
            config_path=str(config) if config else None,
        )

    if output:
        output.write_text(json.dumps(result, indent=2, default=str))
        console.print(f"[green]Answer saved to {output}[/green]")
    else:
        if "answer" in result:
            console.print(f"\n[bold]Answer:[/bold] {result['answer']}")
        else:
            print(json.dumps(result, indent=2, default=str))


@app.command()
def generate_ontology(
    node_types: str = typer.Option(
        ...,
        "--node-types",
        "-n",
        help="Comma-separated list of node types (e.g., 'Organization,Person,Topic')",
    ),
    edge_types: str = typer.Option(
        ...,
        "--edge-types",
        "-e",
        help="Comma-separated list of edge types (e.g., 'worksWith,relatedTo')",
    ),
    output: Optional[Path] = typer.Option(
        Path("ontology.nt"), "--output", "-O", help="Output .nt file path"
    ),
):
    """Generate N-Triple RDF ontology from node and edge types.

    Creates a valid OWL ontology in N-Triple format (.nt file).

    Example:
        graphaide generate-ontology --node-types "Organization,Person,Topic" --edge-types "worksWith,relatedTo,manages"
        graphaide generate-ontology -n "Org,Person" -e "connects" -O my_ontology.nt
    """
    # Parse comma-separated inputs
    node_list = [t.strip() for t in node_types.split(",") if t.strip()]
    edge_list = [t.strip() for t in edge_types.split(",") if t.strip()]

    if not node_list or not edge_list:
        console.print(
            "[red]Error: Both --node-types and --edge-types are required[/red]"
        )
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating ontology...", total=None)

        try:
            from graphgen.v2.workflows import WorkflowManager

            manager = WorkflowManager()
            result = manager.run(
                "ontology_generate",
                inputs={
                    "node_types": node_list,
                    "edge_types": edge_list,
                    "output_path": str(output),
                },
            )

            if result.success:
                console.print("[green]Ontology generated successfully![/green]")
                console.print(f"  Node types: {len(node_list)}")
                console.print(f"  Edge types: {len(edge_list)}")
                console.print(f"  Output: {result.stats.get('ontology_file_path')}")
            else:
                console.print(f"[red]Generation failed: {result.errors}[/red]")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            import traceback

            traceback.print_exc()
            raise typer.Exit(1)


@app.command()
def visualize(
    output: Optional[Path] = typer.Option(
        Path("./data"), "--output", "-O", help="Output directory for visualization"
    ),
    reuse_embedding: bool = typer.Option(
        False, "--reuse-embedding", help="Reuse existing UMAP projection if available"
    ),
    store_name: Optional[str] = typer.Option(
        None, "--store-name", "-s", help="Vector store collection name to visualize"
    ),
    store_path: Optional[str] = typer.Option(
        None, "--store-path", "-p", help="Vector store storage path"
    ),
    provider: str = typer.Option(
        "ChromaDB", "--provider", help="Vector store provider (ChromaDB or Qdrant)"
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="JSON config file for model/db settings"
    ),
):
    """Create 2D UMAP visualization of vector embeddings.

    Generates an interactive visualization showing vector store embeddings
    projected to 2D space. Helps understand document clustering.

    Example:
        graphaide visualize
        graphaide visualize --output ./viz --reuse-embedding
        graphaide visualize --store-name my_collection --store-path /data/vectors
        graphaide visualize --config config.json
    """
    # Set vector store env vars if provided via CLI
    if store_name:
        os.environ["VECTOR_STORE_NAME"] = store_name
    if store_path:
        os.environ["VECTOR_STORE_BASEDIR"] = store_path
    if provider:
        os.environ["VECTOR_STORE_PROVIDER"] = provider

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Creating visualization...", total=None)

        try:
            from graphgen.core import visualize_vector_store

            result = visualize_vector_store(
                reuse_embedding=reuse_embedding,
                output_dir=str(output),
                config_path=str(config) if config else None,
            )

            if result.get("success", False):
                console.print("[green]Visualization created successfully![/green]")
                console.print(f"  HTML: {result.get('projection_file_path')}")
                console.print(f"  Image: {result.get('visualization_image_path')}")
                console.print(f"  Metadata: {result.get('projection_metadata_path')}")
            else:
                console.print(
                    f"[red]Visualization failed: {result.get('errors')}[/red]"
                )
                raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            import traceback

            traceback.print_exc()
            raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the GraphAide REST API server.

    Example:
        graphaide serve --port 8000
    """
    import uvicorn

    console.print(f"[green]Starting GraphAide API server on {host}:{port}[/green]")
    uvicorn.run(
        "graphgen.api:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def dev(
    host: str = typer.Option("127.0.0.1", "--host", help="API server host"),
    port: int = typer.Option(8000, "--port", help="API server port"),
    frontend_port: int = typer.Option(5173, "--frontend-port", help="Frontend dev server port"),
):
    """Start both GraphAide API server and React frontend (development).

    This is the quickest way to get started after 'pip install graphaide'.
    Opens both services in separate processes.

    Example:
        graphaide dev
        graphaide dev --port 8000 --frontend-port 5173
    """
    import subprocess
    import time
    from pathlib import Path

    # Try both paths: source tree and pip-installed
    cli_dir = Path(__file__).parent

    # Path 1: pip-installed (web_demo is a sibling of cli.py in site-packages)
    frontend_dir = cli_dir / "web_demo" / "frontend"

    # Path 2: source tree (src/graphgen/...)
    if not frontend_dir.exists():
        frontend_dir = cli_dir.parent.parent.parent / "src" / "graphgen" / "web_demo" / "frontend"

    if not frontend_dir.exists():
        console.print(f"[yellow]Warning: Frontend directory not found at {frontend_dir}[/yellow]")
        console.print("[yellow]Starting API server only. Use 'graphaide serve' for API-only mode.[/yellow]")
        import uvicorn
        console.print(f"[green]Starting GraphAide API server on {host}:{port}[/green]")
        uvicorn.run("graphgen.api:app", host=host, port=port, reload=True)
        return

    console.print(f"[green]🚀 Starting GraphAide (API + Frontend)[/green]")
    console.print(f"[green]📡 API server: http://{host}:{port}[/green]")
    console.print(f"[green]🌐 Frontend: http://localhost:{frontend_port}[/green]")
    console.print()
    console.print("[dim]⏳ This may take a few minutes on first run:[/dim]")
    console.print("[dim]  • npm install (dependencies for React frontend)[/dim]")
    console.print("[dim]  • LLM model initialization (downloading embeddings)[/dim]")
    console.print("[dim]  • Vector store setup (ChromaDB initialization)[/dim]")
    console.print("[dim]Subsequent runs will be faster.[/dim]")
    console.print()

    try:
        # Start API server
        console.print(f"[dim]Starting: python -m uvicorn graphgen.api:app --host {host} --port {port} --reload[/dim]")
        api_proc = subprocess.Popen(
            ["python", "-m", "uvicorn", "graphgen.api:app", "--host", host, "--port", str(port), "--reload"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        console.print(f"[cyan]✓ API server started (PID: {api_proc.pid})[/cyan]")

        # Give API a moment to start
        time.sleep(2)

        # Start frontend dev server
        console.print(f"[dim]Starting: npm run dev from {frontend_dir}[/dim]")
        npm_start_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        console.print(f"[cyan]✓ Frontend dev server starting (PID: {npm_start_proc.pid})[/cyan]")

        console.print("[green]\n✨ Both servers running! Press Ctrl+C to stop.[/green]")
        console.print(f"[dim]API docs: http://{host}:{port}/docs[/dim]")

        # Wait for both processes
        api_proc.wait()
        npm_start_proc.wait()

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹ Shutting down...[/yellow]")
        try:
            api_proc.terminate()
            npm_start_proc.terminate()
            api_proc.wait(timeout=5)
            npm_start_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_proc.kill()
            npm_start_proc.kill()
        console.print("[green]✓ Servers stopped[/green]")
        raise typer.Exit(0)
    except FileNotFoundError as e:
        console.print(f"[red]❌ Error: npm command not found[/red]")
        console.print(f"[yellow]Node.js and npm are not installed or not in PATH[/yellow]")
        console.print()
        console.print("[dim]Fix:[/dim]")
        console.print("[dim]1. Download Node.js LTS from https://nodejs.org/[/dim]")
        console.print("[dim]2. Install it (npm comes with Node.js)[/dim]")
        console.print("[dim]3. Restart your terminal and try again[/dim]")
        console.print()
        console.print("[dim]Verify installation:[/dim]")
        console.print("[dim]  node --version[/dim]")
        console.print("[dim]  npm --version[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error starting servers: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


def main():
    """Entry point for the CLI."""
    app()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
):
    """Main callback for global options."""
    pass


if __name__ == "__main__":
    main()
