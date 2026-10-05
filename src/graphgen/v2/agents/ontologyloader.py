import logging
from pathlib import Path

from pydantic import BaseModel, Field

from ..ontology_utils import parse_rdf_ontology
from ..state import KGGenerationState, RAGContext
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.ontologyloader")

LOCAL_ONTO = None


class OntologyLoaderToolSchema(BaseModel):
    """Input schema for OntologyLoaderAgent tool."""

    ontology_file_path: str = Field(description="Path to the OWL ontology file to load")


class OntologyLoaderAgent(GraphAideAgent):
    """Load an OWL ontology file and extract node/edge type constraints.

    Parses an ontology file to extract class names (for node types) and
    property names (for edge types) that can guide knowledge graph extraction.
    Uses owlready2 for ontology parsing.

    Input state keys:
        ontology_file_path (str): Path to the OWL ontology file to load.

    Output state keys:
        rag_context (RAGContext): Contains ontology node/edge types and metadata.
        messages (List[str]): Status messages about loaded ontology.

    Requires settings:
        vector_store: Vector store instance (required but not used directly).
    """

    tool_schema = OntologyLoaderToolSchema
    tool_description = "Load an OWL ontology file and extract node/edge type constraints for knowledge graph extraction"
    tool_output_keys = ["rag_context", "messages"]

    def __call__(self, state: KGGenerationState) -> dict:
        import os

        # 1. Access the Vector Store from the factory-injected settings
        vector_store = self.settings.get("vector_store", None)

        if not vector_store:
            raise ValueError(
                f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
            )

        # 2. Check if ontology path is provided
        ontology_path_str = state.get("ontology_file_path") or ""
        if not ontology_path_str:
            logger.info("No ontology file provided, skipping")
            return {
                "messages": ["No ontology file provided - extraction will use open schema."],
                "rag_context": RAGContext(),
            }

        # 3. Load and parse the ontology file using shared parser
        ontology_file_path = Path(ontology_path_str)

        # DEBUG: Log path resolution
        logger.debug(f"Input path: {ontology_path_str}, working dir: {os.getcwd()}, resolved: {ontology_file_path}, exists: {ontology_file_path.exists()}")

        if not ontology_file_path.exists():
            logger.error(f"File does not exist at {ontology_file_path}")
            raise FileNotFoundError(f"Ontology file not found: {ontology_file_path}")

        try:
            # Use shared ontology parser (also used by VectorDBLoader)
            ontology_data = parse_rdf_ontology(str(ontology_file_path))
            logger.debug("Successfully parsed ontology using shared parser")
        except Exception as e:
            logger.error(f"Failed to load ontology: {type(e).__name__}: {e}")
            raise

        # Populate RAGContext with all ontology metadata
        rag_context = RAGContext(
            ontology_node_types=ontology_data["node_types"],
            ontology_edge_types=ontology_data["edge_types"],
            ontology_node_definitions=ontology_data["node_definitions"],
            ontology_node_examples=ontology_data["node_examples"],
            ontology_edge_definitions=ontology_data["edge_definitions"],
            ontology_edge_examples=ontology_data["edge_examples"],
        )

        # Log summary
        logger.info(
            f"Ontology: {len(ontology_data['node_types'])} classes, "
            f"{len(ontology_data['edge_types'])} properties, "
            f"{len(ontology_data['node_definitions'])} definitions, "
            f"{sum(len(v) for v in ontology_data['node_examples'].values())} examples"
        )

        return {
            "messages": [
                f"Ontology loaded with {len(ontology_data['node_types'])} classes, "
                f"{len(ontology_data['edge_types'])} properties.\n"
                f"Enriched with {len(ontology_data['node_definitions'])} class definitions "
                f"and {sum(len(v) for v in ontology_data['node_examples'].values())} examples.\n"
                f"RAG context updated with complete ontology metadata."
            ],
            "rag_context": rag_context,
        }
