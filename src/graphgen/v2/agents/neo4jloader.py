import logging
from typing import List

import openai
from pydantic import BaseModel, Field

from ..state import Edge, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.neo4jloader")


class ExtractorSchema(BaseModel):
    nodes: List[Node] = Field(
        default_factory=list, description="Extracted entity nodes"
    )
    edges: List[Edge] = Field(
        default_factory=list, description="Extracted relationships"
    )


class Neo4jLoaderToolSchema(BaseModel):
    """Input schema for Neo4jLoaderAgent tool."""

    raw_text: str = Field(description="Text to extract entities and relationships from")


class Neo4jLoaderAgent(GraphAideAgent):
    """Extract and load entities from text directly into Neo4j.

    Combines extraction and loading in one step: takes raw text, extracts
    nodes and edges using structured LLM output with vector store context,
    and returns them for subsequent loading operations.

    Input state keys:
        raw_text (str): Text to extract entities and relationships from.

    Output state keys:
        nodes (List[Node]): Extracted entity nodes.
        edges (List[Edge]): Extracted relationships between nodes.
        messages (List[str]): Status messages about extraction results.
        is_valid (bool): Whether extraction completed successfully.

    Requires settings:
        vector_store: Vector store for context retrieval during extraction.
    """

    tool_schema = Neo4jLoaderToolSchema
    tool_description = "Extract entities and relationships from text and prepare them for Neo4j loading"
    tool_output_keys = ["nodes", "edges", "messages", "agent_status"]

    def __call__(self, state: dict) -> dict:

        # 1. Access the Vector Store from the factory-injected settings
        vector_store = self.settings.get("vector_store")

        if not vector_store:
            raise ValueError(
                f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
            )

        # 2. Perform Retrieval
        # We use the raw_text (or 'question') to find relevant LONGROOM context
        query = state.get("raw_text", "")
        docs = vector_store.similarity_search(query, k=3)
        context = "\n "
        for doc in docs:
            # Safe parsing
            meta_val = doc.metadata.get(
                "source", doc.metadata.get("id", doc.metadata.get("title", ""))
            )
            if "|" in meta_val:
                qid_label = meta_val.split("|")
                if len(qid_label) >= 2:
                    context = (
                        context + f"QID={qid_label[0]} Label={qid_label[1]}" + "\n"
                    )

        logger.info(f"{len(docs)} docs retrieved")

        # Logic: combine Prompt + Model
        # Use structured output
        structured_llm = self.model.with_structured_output(ExtractorSchema)
        chain = self.prompt | structured_llm

        # 2. Map State 'raw_text' to Template 'question'
        # Also unpack any partials (like ontology) from self.settings
        inputs = {
            "question": state.get("raw_text", ""),  # <--- KEY MATCHES TEMPLATE
            "context": context,
            **self.settings.get("partials", {}),
        }

        # 3. Run
        try:
            result = self._invoke_chain(chain, inputs)

            # 5. Convert dictionaries to your strict Node/Edge objects
            extracted_nodes = [
                n if isinstance(n, Node) else Node(**n) for n in result.nodes
            ]
            extracted_edges = [
                e if isinstance(e, Edge) else Edge(**e) for e in result.edges
            ]

            # 4. Return updated state
            return {
                "nodes": extracted_nodes,
                "edges": extracted_edges,
                "messages": [
                    f"Extracted {len(extracted_nodes)} nodes, {len(extracted_edges)} edges"
                ],
                "agent_status": {self.__class__.__name__: True},
            }
        except openai.PermissionDeniedError as e:
            logger.error(f"Permission denied [{e.status_code}]: {e.body}")
        except Exception as e:
            logger.error(f"Failed: {e}")
            return {"messages": [f"Error during extraction: {str(e)}"]}
