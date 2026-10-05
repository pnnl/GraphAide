# --- GLOBAL CONFIGURATION FOR GRAPHGEN V2 ---
# This file contains global settings and configurations for GraphGen V2.
import os
import sys
from pathlib import Path

CONTENT_LABEL_LIMIT = -1  # Limit for content preview in metadata
PLOT_TITLE = "Dynamic Embeddings Visualization"

global_config_path = Path(__file__).resolve()
PROJECT_ROOT = global_config_path.parent.parent.parent.parent

# Templates: check mounted path (Docker) → package path → environment root → project root
_mounted_templates = Path("/app/templates")
_package_templates = global_config_path.parent / "templates"
_env_templates = Path(sys.prefix) / "templates"
_root_templates = PROJECT_ROOT / "templates"

if _mounted_templates.exists():
    AGENT_TEMPLATE_DIR = _mounted_templates
elif _package_templates.exists():
    AGENT_TEMPLATE_DIR = _package_templates
elif _env_templates.exists():
    AGENT_TEMPLATE_DIR = _env_templates
else:
    AGENT_TEMPLATE_DIR = _root_templates

AGENT_CONFIG_PATH = PROJECT_ROOT / "agent_config.json"

ENV_PATH = PROJECT_ROOT / ".env"

VECTOR_STORE_BASEDIR = Path(
    os.getenv("VECTOR_STORE_PATH", PROJECT_ROOT / ".local_vectorstores/")
)

DEFAULT_K = 10

DEFAULT_MAX_OUTPUT_TOKENS_LIMIT_LLM = 128000  # LLM output token limit. For input chunk size, see max_tokens_per_segment in CLI/workflows

DEFAULT_EXTERNAL_METADATA = None

# Batch sizes for kg_load_json workflow (for loading large pre-extracted JSON files)
NODE_BATCH_SIZE = 30  # Number of nodes to load per batch
EDGE_BATCH_SIZE = 50  # Number of edges to load per batch

# YML_METADATA_FILTER = ""

# CSV_METADATA_FILTER = ""

# Load project-specific config overrides
PROJECT_CONFIG_PATH = PROJECT_ROOT / "config.local.py"
if PROJECT_CONFIG_PATH.exists():
    import importlib.util

    spec = importlib.util.spec_from_file_location("project_config", PROJECT_CONFIG_PATH)
    project_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(project_config)

    for key in dir(project_config):
        if not key.startswith("_"):
            globals()[key] = getattr(project_config, key)
