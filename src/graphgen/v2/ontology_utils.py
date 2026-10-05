"""Shared ontology parsing utilities for OntologyLoader and VectorDBLoader.

Provides reusable RDF parsing functions and context building with safety escaping.
"""

import logging
from pathlib import Path

import rdflib

logger = logging.getLogger("graphgen.v2.ontology_utils")


def parse_rdf_ontology(ontology_file_path: str) -> dict:
    """Parse RDF ontology and extract classes/properties with metadata.

    Extracts:
    - Node types (owl:Class URIs)
    - Edge types (owl:ObjectProperty, owl:DatatypeProperty URIs)
    - Definitions (skos:definition)
    - Examples (skos:example)
    - Subclass relationships (rdfs:subClassOf)

    Args:
        ontology_file_path: Path to ontology file (.owl, .ttl, .nt, .rdf)

    Returns:
        Dictionary with keys:
        - node_types: List[str] - class names
        - edge_types: List[str] - property names
        - node_definitions: Dict[str, str] - class_name → definition
        - node_examples: Dict[str, List[str]] - class_name → [examples]
        - edge_definitions: Dict[str, str] - property_name → definition
        - edge_examples: Dict[str, List[str]] - property_name → [examples]
    """
    ontology_path = Path(ontology_file_path)
    if not ontology_path.exists():
        raise FileNotFoundError(f"Ontology file not found: {ontology_path}")

    # Detect format from file extension
    file_ext = ontology_path.suffix.lower()
    format_map = {
        ".owl": "xml",
        ".ttl": "turtle",
        ".nt": "ntriples",
        ".rdf": "xml",
    }
    file_format = format_map.get(file_ext, "xml")

    logger.debug(f"Parsing ontology: {ontology_file_path} (format: {file_format})")

    # Parse ontology
    graph = rdflib.Graph()
    graph.parse(str(ontology_path), format=file_format)

    # Define namespaces
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

    # Initialize result dictionaries
    node_types = []
    edge_types = []
    node_definitions = {}
    node_examples = {}
    edge_definitions = {}
    edge_examples = {}

    # Process classes (node types)
    for subject in graph.subjects(RDF.type, OWL.Class):
        # Extract local name from URI
        type_name = (
            str(subject).split("#")[-1]
            if "#" in str(subject)
            else str(subject).split("/")[-1]
        )
        node_types.append(type_name)

        # Get skos:definition
        definitions = []
        for definition in graph.objects(subject, SKOS.definition):
            definitions.append(str(definition))
        if definitions:
            node_definitions[type_name] = definitions[0]  # Take first definition

        # Get skos:example
        examples = []
        for example in graph.objects(subject, SKOS.example):
            examples.append(str(example))
        if examples:
            node_examples[type_name] = examples

    # Process ObjectProperties (edge types)
    for subject in graph.subjects(RDF.type, OWL.ObjectProperty):
        type_name = (
            str(subject).split("#")[-1]
            if "#" in str(subject)
            else str(subject).split("/")[-1]
        )
        edge_types.append(type_name)

        # Get skos:definition
        definitions = []
        for definition in graph.objects(subject, SKOS.definition):
            definitions.append(str(definition))
        if definitions:
            edge_definitions[type_name] = definitions[0]

        # Get skos:example
        examples = []
        for example in graph.objects(subject, SKOS.example):
            examples.append(str(example))
        if examples:
            edge_examples[type_name] = examples

    # Process DatatypeProperties (also edge types)
    for subject in graph.subjects(RDF.type, OWL.DatatypeProperty):
        type_name = (
            str(subject).split("#")[-1]
            if "#" in str(subject)
            else str(subject).split("/")[-1]
        )
        edge_types.append(type_name)

        # Get skos:definition
        definitions = []
        for definition in graph.objects(subject, SKOS.definition):
            definitions.append(str(definition))
        if definitions:
            edge_definitions[type_name] = definitions[0]

        # Get skos:example
        examples = []
        for example in graph.objects(subject, SKOS.example):
            examples.append(str(example))
        if examples:
            edge_examples[type_name] = examples

    logger.info(f"Ontology: {len(node_types)} classes, {len(edge_types)} properties")
    logger.debug(
        f"  Node definitions: {len(node_definitions)}, Node examples: {len(node_examples)}"
    )
    logger.debug(
        f"  Edge definitions: {len(edge_definitions)}, Edge examples: {len(edge_examples)}"
    )

    return {
        "node_types": node_types,
        "edge_types": edge_types,
        "node_definitions": node_definitions,
        "node_examples": node_examples,
        "edge_definitions": edge_definitions,
        "edge_examples": edge_examples,
    }


def build_enriched_ontology_context(rag_context) -> str:
    """Build a safe, LLM-friendly context string with ontology metadata.

    Uses clear delimiters instead of brackets to avoid prompt injection/parsing issues.
    Escapes quotes and braces to prevent breaking LLM prompts or serialization.

    Args:
        rag_context: RAGContext with node/edge types and their metadata

    Returns:
        Formatted context string safe for LLM prompts
    """
    context = "\n"

    # SECTION 1: Node Types with Definitions and Examples
    if rag_context.ontology_node_types:
        context += "=== VALID NODE TYPES ===\n"

        for node_type in rag_context.ontology_node_types:
            # Line 1: Type name
            context += f"- {node_type}"

            # Line 2: Definition (if available)
            definition = rag_context.ontology_node_definitions.get(node_type, "")
            if definition:
                # Escape dangerous characters: quotes and braces
                safe_definition = (
                    definition.replace('"', "'")
                    .replace("{", "[")
                    .replace("}", "]")
                    .strip()
                )
                context += f"\n  Definition: {safe_definition}"

            # Line 3: Examples (if available, limit to 5)
            examples = rag_context.ontology_node_examples.get(node_type, [])
            if examples:
                # Escape and limit examples
                safe_examples = ", ".join(
                    [
                        ex.replace('"', "'").replace("{", "[").replace("}", "]")
                        for ex in examples[:5]
                    ]
                )
                context += f"\n  Examples: {safe_examples}"

            context += "\n"

        context += "\n"

    # SECTION 2: Edge Types with Definitions and Examples
    if rag_context.ontology_edge_types:
        context += "=== VALID RELATIONSHIP TYPES ===\n"

        for edge_type in rag_context.ontology_edge_types:
            # Line 1: Type name
            context += f"- {edge_type}"

            # Line 2: Definition (if available)
            definition = rag_context.ontology_edge_definitions.get(edge_type, "")
            if definition:
                safe_definition = (
                    definition.replace('"', "'")
                    .replace("{", "[")
                    .replace("}", "]")
                    .strip()
                )
                context += f"\n  Definition: {safe_definition}"

            # Line 3: Examples (if available, limit to 5)
            examples = rag_context.ontology_edge_examples.get(edge_type, [])
            if examples:
                safe_examples = ", ".join(
                    [
                        ex.replace('"', "'").replace("{", "[").replace("}", "]")
                        for ex in examples[:5]
                    ]
                )
                context += f"\n  Examples: {safe_examples}"

            context += "\n"

        context += "\nEnsure all node types and edge types match the lists above.\n"

    return context
