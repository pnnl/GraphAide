"""
Pytest configuration and fixtures for GraphAide integration tests.
"""
import os
import shutil
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Load .env file before importing anything that uses env vars
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

from graphaide import (
    GraphAide,
    ModelConfig,
    GraphDBConfig,
    VectorDBConfig,
    IngestType,
    RetrieveType,
    get_sample_data_path,
)
from graphgen.v2.GraphDBManager import GraphDBFactory
from graphgen.v2.VectorStoreManager import VectorFactory


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def model_config():
    """
    OpenAI GPT-4o model config for integration tests.
    Reads from environment variables (set in .env or notebook).
    """
    return ModelConfig(
        provider="openai",
        model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-project"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://ai-incubator-api.pnnl.gov"),
        api_key=os.getenv("OPENAI_API_KEY", ""),
        embedding_model_name=os.getenv(
            "OPENAI_EMBEDDING_MODEL_NAME", "text-embedding-3-small-project"
        ),
        max_output_tokens_limit_llm=int(
            os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "16000")
        ),
    )


@pytest.fixture(scope="session")
def graphdb_config():
    """
    Neo4j graph database config for integration tests.
    Uses 'integrationtest' database.
    """
    return GraphDBConfig(
        uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "neo4jpwd"),
        database=os.getenv("NEO4J_DATABASE", "integrationtest"),
        provider="neo4j",
    )


@pytest.fixture(scope="session")
def vector_config():
    """
    ChromaDB vector database config for integration tests.
    Uses 'integrationtest' store name.
    """
    return VectorDBConfig(
        provider="chromadb",
        store_name="integrationtest",
        store_path=os.getenv(
            "VECTORSTORE_PATH", str(Path.home() / ".vectorstores_graphaide")
        ),
        ingest_type=IngestType.ENTITIES,
        retrieve_type=RetrieveType.ENTITIES,
        description="Integration test vector store. Entities only.",
    )


@pytest.fixture(scope="session")
def graphaide_instance(model_config, graphdb_config, vector_config):
    """
    Initialized GraphAide instance for integration tests.
    Single instance reused across all tests in session.
    """
    return GraphAide(
        model_config=model_config,
        graphdb_config=graphdb_config,
        vector_configs=[vector_config],
    )


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def sample_data():
    """
    Return paths to sample data files used in tests.
    All paths point to GraphAide's built-in sample data.
    """
    return {
        "pdf": str(get_sample_data_path("experiments.pdf")),
        "ontology_biology": str(get_sample_data_path("ontology_biology.nt")),
        "ontology_cyber": str(get_sample_data_path("ontology_cyber.nt")),
        "pnnl_pdf": str(get_sample_data_path("PNNL_About.pdf")),
        "jsonl": str(get_sample_data_path("test_data.jsonl")),
    }


# ============================================================================
# Database Cleanup Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def clean_neo4j_per_test(graphdb_config):
    """
    Clear Neo4j 'integrationtest' database before each test.
    Cleanup happens automatically (no yield return needed).
    """
    driver = GraphDBFactory(graphdb_config=graphdb_config).get_driver()

    if driver:
        # Delete all nodes and relationships
        try:
            driver.query("MATCH (n) DETACH DELETE n")
        except Exception as e:
            pytest.skip(f"Neo4j not available: {e}")

    yield


@pytest.fixture(autouse=True)
def clean_vectordb_per_test(vector_config):
    """
    Delete ChromaDB 'integrationtest' store before each test.
    Cleanup happens automatically (no yield return needed).
    """
    # Expand home directory if needed
    store_base = Path(vector_config.store_path).expanduser()
    store_path = store_base / vector_config.store_name

    # Delete before test
    try:
        if store_path.exists():
            shutil.rmtree(store_path)
            print(f"Cleaned vector store: {store_path}")
    except Exception as e:
        print(f"Warning: Could not clean vector store before test: {e}")

    yield

    # Delete after test
    try:
        if store_path.exists():
            shutil.rmtree(store_path)
            print(f"Cleaned vector store after test: {store_path}")
    except Exception as e:
        print(f"Warning: Could not clean vector store after test: {e}")


# ============================================================================
# Pytest Hooks
# ============================================================================


def pytest_configure(config):
    """
    Register custom markers.
    """
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (slow, uses LLM/DB)"
    )
    config.addinivalue_line("markers", "slow: mark test as slow running")
