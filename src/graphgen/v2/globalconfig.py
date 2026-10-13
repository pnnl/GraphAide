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

VECTOR_STORE_BASEDIR = Path(os.getenv("VECTOR_STORE_PATH", PROJECT_ROOT / ".local_vectorstores/"))

DEFAULT_K = 30

DEFAULT_MAX_OUTPUT_TOKENS_LIMIT_LLM = (
    128000  # LLM output token limit. For input chunk size, see max_tokens_per_segment in CLI/workflows
)

# Context window presets for flexible scaling across different LLM capabilities
CONTEXT_WINDOW_PRESETS = {
    "small": 4096,      # Conservative, for resource-limited deployments
    "medium": 8192,     # Balanced (new default) - supports richer context with multi-retriever RAG
    "large": 16384,     # For models supporting larger windows (GPT-4, Claude 3)
    "xlarge": 32768,    # For cutting-edge models with massive context windows
}
DEFAULT_CONTEXT_WINDOW_MODE = "medium"  # New default: increased from 4096

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
