"""GraphAide utilities module."""

import logging
from datetime import datetime
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from graphgen.v2.agents.base import GraphAideAgent
from graphgen.v2.state import KGGenerationState


class PrettyFormatter(logging.Formatter):
    """Custom formatter for pretty logging with emoji and formatting."""

    EMOJI = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
    }

    def format(self, record):
        """Format log record with emoji and pretty formatting."""
        level = record.levelname
        emoji = self.EMOJI.get(level, "")

        if level == "DEBUG":
            # DEBUG: 🔍 [DEBUG] message
            return f"{emoji} [{level}] {record.getMessage()}"
        elif level == "INFO":
            # INFO: #### [INFO] message ####
            msg = record.getMessage()
            return f"#### [{level}] {msg} ####"
        elif level in ["ERROR", "CRITICAL"]:
            # ERROR/CRITICAL: ❌ [ERROR] message
            return f"{emoji} [{level}] {record.getMessage()}"
        elif level == "WARNING":
            # WARNING: ⚠️ [WARNING] message
            return f"{emoji} [{level}] {record.getMessage()}"
        else:
            return f"{emoji} [{level}] {record.getMessage()}" if emoji else record.getMessage()


def strip_thinking_tokens(text: str) -> str:
    """Strip Claude thinking syntax tokens from text.

    Removes <|channel>thought markers and other thinking-related syntax
    that may leak into LLM outputs when extended thinking is enabled.

    Args:
        text: Text potentially containing thinking tokens

    Returns:
        Text with thinking tokens removed
    """
    import re
    # Remove all <|channel>thought....*?<|end_thinking|> blocks
    text = re.sub(r'<\|channel>thought.*?<\|end[_-]?thinking\|>', '', text, flags=re.DOTALL)
    # Remove orphaned <|channel>thought markers
    text = re.sub(r'<\|channel>thought[^>]*>', '', text)
    # Remove any other thinking markers
    text = re.sub(r'<\|[a-z_]*thinking[a-z_]*\|>', '', text, flags=re.IGNORECASE)
    return text.strip()


def mask_sensitive_value(value: str, show_chars: int = 4) -> str:
    """Mask sensitive value, showing only last N characters.

    Args:
        value: Value to mask (e.g., API key)
        show_chars: Number of characters to show at the end (default 4)

    Returns:
        Masked string in format: ***...abcd (where abcd are last 4 chars)
    """
    if not value or len(value) <= show_chars:
        return "***"
    return "*" * (len(value) - show_chars) + value[-show_chars:]


def get_linear_app(
    agents: list[GraphAideAgent],
    initial_state: KGGenerationState,
    agent_names: list[str] = None
) -> KGGenerationState:
    """Executes a linear workflow of agents, where the output of one agent is passed as input to the next.

    Args:
        agents (list[GraphAideAgent]): A list of GraphAideAgent instances to execute in order.
        initial_state (KGGenerationState): The initial state to pass to the first agent.
        agent_names (list[str], optional): Custom names for each agent node.
                                          If None, uses agent class names (default).

    """
    workflow = StateGraph(KGGenerationState)

    # Use provided names or default to class names
    if agent_names is None:
        agent_names = [agent.__class__.__name__ for agent in agents]
    elif len(agent_names) != len(agents):
        logger = logging.getLogger("graphgen.utils")
        logger.error(f"agent_names length {len(agent_names)} doesn't match agents {len(agents)}")
        agent_names = [agent.__class__.__name__ for agent in agents]

    logger = logging.getLogger("graphgen.utils")
    for name, agent in zip(agent_names, agents):
        try:
            workflow.add_node(name, agent)
        except Exception as e:
            logger.error(f"Workflow: failed to add {name}: {e}")

    nodelist = [START] + agent_names + [END]
    for index, n in enumerate(nodelist[:-1]):
        workflow.add_edge(n, nodelist[index + 1])

    # Compile the graph
    app = workflow.compile()
    return app


def get_chain_verbose() -> bool:
    """Determine if LangChain chains should be verbose based on current log level.

    Returns:
        bool: True if log level is DEBUG, False otherwise (including INFO, WARNING, ERROR)

    Used by GraphCypherQAChain, ExtractorAgent, and other chains to control verbosity.
    Rules:
        - DEBUG mode: verbose=True (shows Cypher queries, intermediate steps)
        - INFO mode: verbose=False (only GraphAide logs, no chain traces)
    """
    graphaide_logger = logging.getLogger("graphgen")
    return graphaide_logger.level == logging.DEBUG


def setup_logging(log_level="INFO", log_file=None):
    """Configure logging for entire workflow.

    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR) for GraphAide modules. Defaults to INFO.
        log_file (str, optional): Path to log file. If None, uses default: graphaide_run_<date>.log
    """
    if log_file is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = f"graphaide_run_{date_str}.log"

    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create formatter
    formatter = PrettyFormatter()

    # Configure handlers - CRITICAL: set to DEBUG so they don't filter messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    handlers = [console_handler, file_handler]

    # Configure root logger to WARNING (suppresses all third-party noise)
    logging.basicConfig(
        level=logging.WARNING,
        handlers=handlers,
        force=True
    )

    # Set specified level for GraphAide modules only
    graphaide_level = getattr(logging, log_level.upper())
    logging.getLogger("graphgen").setLevel(graphaide_level)

    # Log setup message
    logger = logging.getLogger("graphgen")
    abs_path = Path(log_file).resolve()
    logger.info(f"Logging to: {abs_path}")

    return log_file


def get_logger(name):
    """Get a logger instance for the given module name."""
    return logging.getLogger(name)


def get_current_log_level():
    """Get the current log level for GraphAide.

    Returns:
        str: Current log level name (e.g., 'DEBUG', 'INFO', 'WARNING'). Defaults to 'INFO' if not set.
    """
    graphgen_logger = logging.getLogger("graphgen")
    level = graphgen_logger.level
    # Return "INFO" as default if NOTSET (logging not initialized yet)
    if level == logging.NOTSET:
        return "INFO"
    return logging.getLevelName(level)


def log_workflow_start(workflow_name: str):
    """Log workflow start with pretty centered formatting.

    Args:
        workflow_name: Name of the workflow being started
    """
    logger = logging.getLogger("graphgen")
    width = 60
    border = "=" * width
    name_str = f" {workflow_name.upper()} "
    centered_name = name_str.center(width, "=")
    logger.info(f"\n{border}\n{centered_name}\n{border}")


def get_vector_store_metadata(vector_store):
    """Extract all unique metadata values from a ChromaDB vector store.

    Args:
        vector_store: ChromaDB vector store instance

    Returns:
        dict: Mapping of metadata keys to their unique values
    """
    collection = vector_store._collection
    all_data = collection.get(include=["metadatas"])
    metadatas = all_data.get("metadatas", [])

    # Collect all unique metadata keys and values
    metadata_map = {}
    for metadata in metadatas:
        if metadata:
            for key, value in metadata.items():
                if key not in metadata_map:
                    metadata_map[key] = set()
                if value is not None:
                    metadata_map[key].add(str(value))

    # Convert sets to sorted lists
    return {key: sorted(list(values)) for key, values in metadata_map.items()}


def print_vector_store_summary(vector_store):
    """Print a formatted summary of vector store contents.

    Args:
        vector_store: ChromaDB vector store instance
    """
    collection = vector_store._collection
    total_docs = collection.count()

    print(f"\n{'='*60}")
    print(f"Vector Store Summary")
    print(f"{'='*60}")
    print(f"Total documents: {total_docs}")

    if total_docs == 0:
        print("(Empty store)")
        print(f"{'='*60}\n")
        return

    metadata = get_vector_store_metadata(vector_store)

    print(f"\nMetadata Categories:")
    print(f"{'-'*60}")
    for key, values in metadata.items():
        print(f"\n{key}:")
        for value in values:
            count = collection.count(
                where={key: {"$eq": value}}
            ) if key in ["source", "metadata_filter"] else "N/A"
            print(f"  - {value} ({count} docs)")

    print(f"\n{'='*60}\n")
