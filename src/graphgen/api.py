"""GraphAide REST API - FastAPI service for knowledge graph operations."""

import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from graphgen.core import (
    extract_graph,
    extract_graph_merge,
    ingest_to_neo4j,
    ingest_to_vectordb,
    query_graph,
    visualize_vector_store,
)

app = FastAPI(
    title="GraphAide API",
    description="Multi-agentic knowledge graph construction and querying service",
    version="1.0.0",
)

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ExtractRequest(BaseModel):
    """Request model for text-based extraction."""

    text: str = Field(..., description="Raw text to extract knowledge graph from")
    ontology_text: str | None = Field(None, description="Ontology content (OWL/TTL/NT)")


class ExtractResponse(BaseModel):
    """Response model for extraction."""

    success: bool = True
    nodes: list = Field(default_factory=list, description="Extracted nodes")
    edges: list = Field(default_factory=list, description="Extracted edges")
    metadata: dict = Field(default_factory=dict, description="Extraction metadata")
    errors: list = Field(default_factory=list, description="Error messages if any")


class IngestResponse(BaseModel):
    """Response model for ingestion."""

    success: bool
    nodes_created: int = 0
    edges_created: int = 0
    message: str = ""


class QueryRequest(BaseModel):
    """Request model for querying."""

    question: str = Field(..., description="Natural language question")


class QueryResponse(BaseModel):
    """Response model for queries."""

    question: str
    answer: str | None = None
    graph_answer: str | None = None
    related_nodes: list = Field(default_factory=list)
    related_edges: list = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    neo4j_connected: bool
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and connectivity."""
    from graphgen.v2.GraphDBManager import GraphDBFactory

    neo4j_ok = False
    try:
        factory = GraphDBFactory()
        driver = factory.get_driver()
        if driver:
            # Neo4jGraph doesn't have verify_connectivity, just check it exists
            neo4j_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        neo4j_connected=neo4j_ok,
        version="1.0.0",
    )


@app.get("/get-config")
async def get_config():
    """Get all configuration from environment variables.

    Web app calls this on startup to populate ConfigPanel with .env values.
    """
    return {
        # LLM Configuration
        "modelProvider": os.getenv("OPENAI_PROVIDER", "openai"),
        "modelName": os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
        "apiKey": os.getenv("OPENAI_API_KEY", ""),
        "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.0")),
        "maxTokens": int(os.getenv("OPENAI_MAX_TOKENS", "8192")),
        "proxyUrl": os.getenv("HTTP_PROXY", ""),
        # Neo4j Configuration
        "neoUri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "neoUsername": os.getenv("NEO4J_USERNAME", "neo4j"),
        "neoPassword": os.getenv("NEO4J_PASSWORD", ""),
        # Vector Store Configuration
        "vectorStoreProvider": os.getenv("VECTOR_STORE_PROVIDER", "ChromaDB"),
        "vectorStorePath": os.getenv("VECTOR_STORE_BASEDIR", "./chroma"),
        "vectorStoreName": os.getenv("VECTOR_STORE_NAME", "GA_VDB"),
        # Observability: Langfuse
        "langfuseEnabled": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
        "langfusePublicKey": os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        "langfuseSecretKey": os.getenv("LANGFUSE_SECRET_KEY", ""),
        "langfuseBaseUrl": os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com"),
        "langfuseDebug": os.getenv("LANGFUSE_DEBUG", "false").lower() == "true",
        "langfuseServiceName": os.getenv("OTEL_SERVICE_NAME", "graphaide"),
        "langfuseSessionName": os.getenv("LANGFUSE_SESSION_NAME", "GraphAide-Development"),
        "langfuseEnvironment": os.getenv("LANGFUSE_ENVIRONMENT", "development"),
    }


@app.get("/get-observability-config")
async def get_observability_config():
    """Get Langfuse observability config from environment variables.

    Deprecated: Use /get-config instead.
    Kept for backward compatibility.
    """
    config = await get_config()
    return {
        "langfuse_enabled": config["langfuseEnabled"],
        "langfuse_public_key": config["langfusePublicKey"],
        "langfuse_secret_key": config["langfuseSecretKey"],
        "langfuse_base_url": config["langfuseBaseUrl"],
        "langfuse_debug": config["langfuseDebug"],
        "langfuse_service_name": config["langfuseServiceName"],
        "langfuse_session_name": config["langfuseSessionName"],
        "langfuse_environment": config["langfuseEnvironment"],
    }


@app.post("/extract", response_model=ExtractResponse)
async def extract_from_text(request: ExtractRequest):
    """Extract knowledge graph from raw text.

    Returns nodes and edges as JSON without storing to Neo4j.
    """
    text_path = None
    ontology_path = None
    try:
        # Write text to temp file (workflow expects file path)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(request.text)
            text_path = f.name

        if request.ontology_text:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".owl", delete=False) as f:
                f.write(request.ontology_text)
                ontology_path = f.name

        result = extract_graph(
            file_path=text_path,
            ontology_path=ontology_path,
        )

        return ExtractResponse(
            success=True,
            nodes=result.get("nodes", []),
            edges=result.get("edges", []),
            metadata={"segments_processed": result.get("segments_processed", 0)},
            errors=[],
        )
    except Exception as e:
        error_msg = str(e)
        print(f"[API] Extract error: {error_msg}")
        return ExtractResponse(
            success=False,
            nodes=[],
            edges=[],
            metadata={},
            errors=[error_msg],
        )
    finally:
        # Cleanup temp files
        if text_path and os.path.exists(text_path):
            os.unlink(text_path)
        if ontology_path and os.path.exists(ontology_path):
            os.unlink(ontology_path)


@app.post("/extract/file", response_model=ExtractResponse)
async def extract_from_file(
    file: UploadFile = File(..., description="Text or PDF file"),
    ontology: UploadFile | None = File(None, description="Ontology file"),
):
    """Extract knowledge graph from uploaded file.

    Supports .txt and .pdf files.
    """
    file_path = None
    ontology_path = None
    try:
        # Save uploaded file
        suffix = os.path.splitext(file.filename)[1] or ".txt"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            content = await file.read()
            f.write(content)
            file_path = f.name

        if ontology:
            onto_suffix = os.path.splitext(ontology.filename)[1] or ".owl"
            with tempfile.NamedTemporaryFile(suffix=onto_suffix, delete=False) as f:
                onto_content = await ontology.read()
                f.write(onto_content)
                ontology_path = f.name

        result = extract_graph(
            file_path=file_path,
            ontology_path=ontology_path,
        )

        return ExtractResponse(
            success=True,
            nodes=result.get("nodes", []),
            edges=result.get("edges", []),
            metadata={"segments_processed": result.get("segments_processed", 0)},
            errors=[],
        )
    except Exception as e:
        error_msg = str(e)
        print(f"[API] Extract error: {error_msg}")
        return ExtractResponse(
            success=False,
            nodes=[],
            edges=[],
            metadata={},
            errors=[error_msg],
        )
    finally:
        # Cleanup
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
        if ontology_path and os.path.exists(ontology_path):
            os.unlink(ontology_path)


@app.post("/extract-merge", response_model=ExtractResponse)
async def extract_merge_from_text(request: ExtractRequest):
    """Extract knowledge graph and merge duplicate nodes by node_id.

    Returns merged nodes and edges as JSON without storing to Neo4j.
    """
    text_path = None
    ontology_path = None
    try:
        # Write text to temp file (workflow expects file path)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(request.text)
            text_path = f.name

        if request.ontology_text:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".owl", delete=False) as f:
                f.write(request.ontology_text)
                ontology_path = f.name

        result = extract_graph_merge(
            file_path=text_path,
            ontology_path=ontology_path,
        )

        return ExtractResponse(
            success=True,
            nodes=result.get("merged_nodes", []),
            edges=result.get("merged_edges", []),
            metadata={"segments_processed": result.get("segments_processed", 0)},
            errors=[],
        )
    except Exception as e:
        error_msg = str(e)
        print(f"[API] Extract-merge error: {error_msg}")
        return ExtractResponse(
            success=False,
            nodes=[],
            edges=[],
            metadata={},
            errors=[error_msg],
        )
    finally:
        # Cleanup temp files
        if text_path and os.path.exists(text_path):
            os.unlink(text_path)
        if ontology_path and os.path.exists(ontology_path):
            os.unlink(ontology_path)


@app.post("/extract-merge/file", response_model=ExtractResponse)
async def extract_merge_from_file(
    file: UploadFile = File(..., description="Text or PDF file"),
    ontology: UploadFile | None = File(None, description="Ontology file"),
):
    """Extract knowledge graph and merge duplicate nodes by node_id from uploaded file."""
    file_path = None
    ontology_path = None
    try:
        # Save uploaded file
        suffix = os.path.splitext(file.filename)[1] or ".txt"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            content = await file.read()
            f.write(content)
            file_path = f.name

        if ontology:
            onto_suffix = os.path.splitext(ontology.filename)[1] or ".owl"
            with tempfile.NamedTemporaryFile(suffix=onto_suffix, delete=False) as f:
                onto_content = await ontology.read()
                f.write(onto_content)
                ontology_path = f.name

        result = extract_graph_merge(
            file_path=file_path,
            ontology_path=ontology_path,
        )

        return ExtractResponse(
            success=True,
            nodes=result.get("merged_nodes", []),
            edges=result.get("merged_edges", []),
            metadata={"segments_processed": result.get("segments_processed", 0)},
            errors=[],
        )
    except Exception as e:
        error_msg = str(e)
        print(f"[API] Extract-merge error: {error_msg}")
        return ExtractResponse(
            success=False,
            nodes=[],
            edges=[],
            metadata={},
            errors=[error_msg],
        )
    finally:
        # Cleanup
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
        if ontology_path and os.path.exists(ontology_path):
            os.unlink(ontology_path)


@app.post("/ingest", response_model=IngestResponse)
async def ingest_text(request: ExtractRequest):
    """Extract and ingest knowledge graph into Neo4j from raw text."""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(request.text)
            text_path = f.name

        ontology_path = None
        if request.ontology_text:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".owl", delete=False) as f:
                f.write(request.ontology_text)
                ontology_path = f.name

        result = ingest_to_neo4j(
            file_path=text_path,
            ontology_path=ontology_path,
        )

        os.unlink(text_path)
        if ontology_path:
            os.unlink(ontology_path)

        return IngestResponse(
            success=True,
            nodes_created=result.get("nodes_created", 0),
            edges_created=result.get("edges_created", 0),
            message="Successfully ingested into Neo4j",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(..., description="Text or PDF file"),
    ontology: UploadFile | None = File(None, description="Ontology file"),
    clear: bool = Form(False, description="Clear existing graph before ingesting"),
):
    """Extract and ingest knowledge graph into Neo4j from uploaded file."""
    try:
        suffix = os.path.splitext(file.filename)[1] or ".txt"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            content = await file.read()
            f.write(content)
            file_path = f.name

        ontology_path = None
        if ontology:
            onto_suffix = os.path.splitext(ontology.filename)[1] or ".owl"
            with tempfile.NamedTemporaryFile(suffix=onto_suffix, delete=False) as f:
                onto_content = await ontology.read()
                f.write(onto_content)
                ontology_path = f.name

        result = ingest_to_neo4j(
            file_path=file_path,
            ontology_path=ontology_path,
            clear_existing=clear,
        )

        os.unlink(file_path)
        if ontology_path:
            os.unlink(ontology_path)

        return IngestResponse(
            success=True,
            nodes_created=result.get("nodes_created", 0),
            edges_created=result.get("edges_created", 0),
            message="Successfully ingested into Neo4j",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class VectorDBIngestResponse(BaseModel):
    """Response model for vector DB ingestion."""

    success: bool
    documents_loaded: int = 0
    chunks_created: int = 0
    vector_store_name: str = "GA_VDB"
    vector_store_path: str = "./chroma"
    message: str = ""


class VectorDBVisualizeResponse(BaseModel):
    """Response model for vector DB visualization."""

    success: bool
    projection_file_path: str = ""
    visualization_image_path: str = ""
    projection_metadata_path: str = ""
    num_embeddings_projected: int = 0
    message: str = ""


@app.post("/vectordb-ingest", response_model=VectorDBIngestResponse)
async def vectordb_ingest(
    file_paths: str = Form(..., description="Comma-separated file paths"),
    split: bool = Form(True, description="Split documents into chunks"),
    append: bool = Form(True, description="Append to existing vector store"),
):
    """Load documents into vector store for semantic search.

    Supports PDF, TXT, JSON, JSONL, CSV, TSV, and YAML files.
    """
    try:
        # Parse comma-separated file paths
        file_list = [f.strip() for f in file_paths.split(",")]

        result = ingest_to_vectordb(
            file_paths=file_list,
            split_docs=split,
            append=append,
        )

        return VectorDBIngestResponse(
            success=result.get("success", False),
            documents_loaded=result.get("documents_loaded", 0),
            chunks_created=result.get("chunks_created", 0),
            vector_store_name=result.get("vector_store_name", "GA_VDB"),
            vector_store_path=result.get("vector_store_path", "./chroma"),
            message="Successfully ingested documents into vector store",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vectordb-visualize", response_model=VectorDBVisualizeResponse)
async def vectordb_visualize(
    reuse_embedding: bool = Form(False, description="Reuse existing UMAP projection"),
    output_dir: str = Form("./data", description="Output directory for visualization"),
):
    """Create 2D UMAP visualization of vector embeddings."""
    try:
        result = visualize_vector_store(
            reuse_embedding=reuse_embedding,
            output_dir=output_dir,
        )

        return VectorDBVisualizeResponse(
            success=result.get("success", False),
            projection_file_path=result.get("projection_file_path", ""),
            visualization_image_path=result.get("visualization_image_path", ""),
            projection_metadata_path=result.get("projection_metadata_path", ""),
            num_embeddings_projected=result.get("num_embeddings_projected", 0),
            message="Successfully created visualization",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Query the knowledge graph with a natural language question."""
    try:
        result = query_graph(question=request.question)

        return QueryResponse(
            question=request.question,
            answer=result.get("answer"),
            graph_answer=result.get("graph_answer"),
            related_nodes=result.get("related_nodes", []),
            related_edges=result.get("related_edges", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/load-json", response_model=IngestResponse)
async def load_json_to_neo4j(
    file: UploadFile = File(..., description="JSON file from extract endpoint"),
    clear: bool = Form(False, description="Clear existing graph before loading"),
):
    """Load pre-extracted JSON file directly into Neo4j.

    The JSON file should be in the format produced by the /extract endpoint,
    containing 'nodes' and 'edges' arrays.
    """
    try:
        from graphgen.core import load_json_to_neo4j as load_json_core

        # Read JSON file
        content = await file.read()
        json_path = None
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(content)
            json_path = f.name

        result = load_json_core(
            json_path=json_path,
            clear_existing=clear,
        )

        # Cleanup
        os.unlink(json_path)

        return IngestResponse(
            success=True,
            nodes_created=result.get("nodes_created", 0),
            edges_created=result.get("edges_created", 0),
            message="Successfully loaded JSON into Neo4j",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
