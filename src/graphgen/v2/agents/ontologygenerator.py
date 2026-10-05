import logging
import os
from typing import List, Optional
from pydantic import BaseModel, Field

from ..state import KGGenerationState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.ontologygenerator")


class OntologyGeneratorToolSchema(BaseModel):
    """Input schema for OntologyGeneratorAgent tool."""

    node_types: Optional[List[str]] = Field(
        default=None,
        description="List of node types (e.g., ['Organization', 'Person', 'Topic'])",
    )
    edge_types: Optional[List[str]] = Field(
        default=None,
        description="List of edge/relationship types (e.g., ['worksWith', 'relatedTo'])",
    )
    output_path: Optional[str] = Field(
        default="ontology.nt",
        description="Path to save the generated N-Triple ontology file",
    )


class OntologyGeneratorAgent(GraphAideAgent):
    """Generate a valid N-Triple format ontology from node and edge type lists.

    Creates an OWL/RDF ontology in N-Triple serialization format.
    Each node_type becomes an owl:Class, each edge_type becomes an owl:ObjectProperty.

    Input state keys:
        node_types (List[str]): List of node type names
        edge_types (List[str]): List of edge/relationship type names
        output_path (str, optional): Path to save .nt file (default: ontology.nt)

    Output state keys:
        ontology_file_path (str): Path to generated .nt file
        messages (List[str]): Generation logs
    """

    tool_schema = OntologyGeneratorToolSchema
    tool_description = "Generate a valid N-Triple RDF ontology from node and edge types"
    tool_output_keys = ["ontology_file_path", "messages"]

    def __call__(self, state: KGGenerationState) -> dict:
        try:
            # Get inputs from state
            node_types = state.get("node_types", [])
            edge_types = state.get("edge_types", [])
            output_path = state.get("output_path", "ontology.nt")

            # Debug logging
            logger.debug(f"OntologyGenerator: Received node_types={node_types}, edge_types={edge_types}, output_path={output_path}")

            # Normalize inputs - handle both string (comma-separated) and list
            if isinstance(node_types, str):
                node_types = [t.strip() for t in node_types.split(",") if t.strip()]
            elif isinstance(node_types, list):
                node_types = [t.strip() if isinstance(t, str) else t for t in node_types]

            if isinstance(edge_types, str):
                edge_types = [t.strip() for t in edge_types.split(",") if t.strip()]
            elif isinstance(edge_types, list):
                edge_types = [t.strip() if isinstance(t, str) else t for t in edge_types]

            if not node_types and not edge_types:
                err_msg = "Error: No node_types or edge_types provided"
                logger.error(f"OntologyGenerator: {err_msg}")
                return {
                    "messages": [err_msg],
                    "ontology_file_path": None,
                }

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            # Generate and validate ontology with retries
            max_retries = 3
            last_error = None

            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"OntologyGenerator: Attempt {attempt}/{max_retries} to generate and validate ontology")

                    # Generate N-Triple ontology
                    triples = self._generate_ntriples(node_types, edge_types)

                    # Validate before writing (fail fast)
                    if not triples or not triples.strip():
                        raise ValueError("Generated ontology is empty")

                    # Write to file
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(triples)

                    # Validate using owlready2
                    self._validate_ntriples(output_path)

                    msg = f"Generated and validated N-Triple ontology with {len(node_types)} classes and {len(edge_types)} properties"
                    logger.info(f"OntologyGenerator: [OK] {msg}")

                    return {
                        "messages": [msg],
                        "ontology_file_path": output_path,
                    }

                except Exception as e:
                    last_error = e
                    logger.error(f"OntologyGenerator: Attempt {attempt}/{max_retries} failed: {e}")
                    if attempt < max_retries:
                        logger.warning(f"OntologyGenerator: Retrying ({max_retries - attempt} attempts remaining)...")
                    continue

            # All retries failed
            err_msg = f"Error generating ontology after {max_retries} attempts: {str(last_error)}"
            logger.error(f"OntologyGenerator: {err_msg}")
            return {
                "messages": [err_msg],
                "ontology_file_path": None,
            }

        except Exception as e:
            import traceback
            logger.error(f"OntologyGenerator failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "messages": [f"Error generating ontology: {str(e)}"],
                "ontology_file_path": None,
            }

    def _validate_ntriples(self, output_path: str) -> None:
        """Validate ontology file using owlready2 (same as OntologyLoaderAgent).

        Args:
            output_path: Path to the ontology file to validate

        Raises:
            Exception: If validation fails
        """
        try:
            from owlready2 import get_ontology, onto_path
            from pathlib import Path

            ontology_file = Path(output_path)
            onto_path.append(str(ontology_file.parent))

            # Detect format from file extension
            file_ext = ontology_file.suffix.lower()
            format_map = {
                ".owl": "rdfxml",
                ".ttl": "turtle",
                ".nt": "ntriples",
                ".rdf": "rdfxml",
            }
            file_format = format_map.get(file_ext, "rdfxml")

            # Load and parse the file with owlready2 (same method as OntologyLoaderAgent)
            onto = get_ontology(str(ontology_file.absolute())).load(format=file_format)

            # For N-Triple files, owlready2 doesn't extract classes/properties well,
            # so just verify it loads without errors
            if file_format == "ntriples":
                logger.info("OntologyGenerator: Validated N-Triple ontology (parsed successfully)")
            else:
                classes = list(onto.classes())
                properties = list(onto.properties())
                logger.info(f"OntologyGenerator: Validated ontology - {len(classes)} classes, {len(properties)} properties")

        except Exception as e:
            raise ValueError(f"Ontology validation (owlready2) failed: {e}")

    def _generate_ntriples(self, node_types: list, edge_types: list) -> str:
        """Generate N-Triple format RDF ontology with proper OWL declarations.

        Args:
            node_types: List of node type names
            edge_types: List of edge type names

        Returns:
            N-Triple format string with valid OWL/RDF structure
        """
        base_ns = "http://graphaide.org/ontology/"
        owl_ns = "http://www.w3.org/2002/07/owl#"
        rdf_ns = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        rdfs_ns = "http://www.w3.org/2000/01/rdf-schema#"

        triples = []

        # Ontology header - declare the ontology itself
        ontology_uri = f"{base_ns}ontology"
        triples.append(
            f"<{ontology_uri}> <{rdf_ns}type> <{owl_ns}Ontology> ."
        )

        # Generate Class definitions for node types
        for node_type in node_types:
            node_uri = f"{base_ns}{node_type}"

            # Class declaration
            triples.append(
                f"<{node_uri}> <{rdf_ns}type> <{owl_ns}Class> ."
            )

            # Subclass of Thing
            triples.append(
                f"<{node_uri}> <{rdfs_ns}subClassOf> <{owl_ns}Thing> ."
            )

            # Label
            triples.append(
                f'<{node_uri}> <{rdfs_ns}label> "{node_type}"@en .'
            )

            # Comment
            triples.append(
                f'<{node_uri}> <{rdfs_ns}comment> "Entity type: {node_type}"@en .'
            )

        # Generate ObjectProperty definitions for edge types
        for edge_type in edge_types:
            prop_uri = f"{base_ns}{edge_type}"

            # ObjectProperty declaration
            triples.append(
                f"<{prop_uri}> <{rdf_ns}type> <{owl_ns}ObjectProperty> ."
            )

            # Label
            triples.append(
                f'<{prop_uri}> <{rdfs_ns}label> "{edge_type}"@en .'
            )

            # Comment
            triples.append(
                f'<{prop_uri}> <{rdfs_ns}comment> "Relationship type: {edge_type}"@en .'
            )

            # Domain and range - can connect any Thing to any Thing
            thing_uri = f"{owl_ns}Thing"
            triples.append(
                f"<{prop_uri}> <{rdfs_ns}domain> <{thing_uri}> ."
            )
            triples.append(
                f"<{prop_uri}> <{rdfs_ns}range> <{thing_uri}> ."
            )

        return "\n".join(triples) + "\n"
