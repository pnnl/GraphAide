import json
import logging
from typing import List

from pydantic import BaseModel, Field

from ..state import Edge, KGGenerationState, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.nodesedgefixer")

UNKNOWN_TYPE = "Unknown"
UNRESOLVED_TYPES = {"", UNKNOWN_TYPE, "default_type"}


class NodeTypeAssignment(BaseModel):
    node_id: str = Field(description="node_id of the node being typed")
    node_type: str = Field(description="Chosen type from the allowed list, or 'Unknown'")


class NodeTypeAssignments(BaseModel):
    assignments: List[NodeTypeAssignment]


def is_unresolved(node: Node) -> bool:
    return (node.node_type or "") in UNRESOLVED_TYPES


def fix_unresolved_node_types(nodes: List[Node], allowed: List[str], prompt, model) -> int:
    """Assign types to unresolved nodes in place. Makes at most one LLM call.

    Nodes whose LLM-chosen type is outside `allowed` become 'Unknown'.
    Returns the number of nodes that received an allowed type.
    """
    unresolved = [n for n in nodes if is_unresolved(n)]
    if not unresolved:
        return 0

    allowed_set = set(allowed)
    if not allowed_set:
        for node in unresolved:
            node.node_type = UNKNOWN_TYPE
        return 0

    payload = [
        {
            "node_id": n.node_id,
            "node_name": n.node_name,
            "english_name": n.english_name,
            "context": n.raw_source_line,
        }
        for n in unresolved
    ]
    chain = prompt | model.with_structured_output(NodeTypeAssignments)
    try:
        result = chain.invoke(
            {
                "allowed_types": ", ".join(sorted(allowed_set)),
                "nodes": json.dumps(payload, ensure_ascii=False),
            }
        )
        chosen = {a.node_id: a.node_type for a in result.assignments}
    except Exception as e:
        logger.warning(f"Node type fix failed, leaving nodes as 'Unknown': {e}")
        chosen = {}

    fixed = 0
    for node in unresolved:
        new_type = chosen.get(node.node_id, UNKNOWN_TYPE)
        if new_type not in allowed_set:
            new_type = UNKNOWN_TYPE
        node.node_type = new_type
        if new_type != UNKNOWN_TYPE:
            fixed += 1
    return fixed


class NodesEdgeFixerToolSchema(BaseModel):
    """Input schema for NodesEdgeFixerAgent tool."""

    nodes: List[Node]
    edges: List[Edge]


class NodesEdgeFixerAgent(GraphAideAgent):
    """Add stub nodes for edge endpoints and retype unresolved nodes.

    Input state keys:
        nodes (List[Node]): Extracted nodes.
        edges (List[Edge]): Extracted edges.
        rag_context_summary (RAGContextSummary, optional): Source of ontology node types.

    Output state keys:
        nodes (List[Node]): Only the newly created stub nodes (operator.add reducer).
        messages, current_agent, agent_status.
    """

    tool_schema = NodesEdgeFixerToolSchema
    tool_description = "Add stub nodes for edge endpoints missing from the node list and assign types to nodes whose type is empty, Unknown, or default_type. Call BEFORE parallel NodesLoader and EdgesLoader."
    tool_output_keys = ["nodes", "messages", "agent_status"]

    def __call__(self, state: KGGenerationState) -> dict:
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])

        stubs = self._build_stubs(nodes, edges)
        all_nodes = nodes + stubs

        allowed = self._allowed_types(state, all_nodes)
        unresolved_count = sum(1 for n in all_nodes if is_unresolved(n))
        fixed = fix_unresolved_node_types(all_nodes, allowed, self.prompt, self.model)

        message = (
            f"Added {len(stubs)} stub nodes; {unresolved_count} nodes needed a type, "
            f"{fixed} assigned from allowed types."
        )
        logger.info(f"NodesEdgeFixer: {message}")

        return {
            "nodes": stubs,
            "messages": [message],
            "current_agent": [self.__class__.__name__],
            "agent_status": {self.__class__.__name__: True},
        }

    def _build_stubs(self, nodes: List[Node], edges: List[Edge]) -> List[Node]:
        existing_ids = {n.node_id for n in nodes if n.node_id}
        referenced_ids = set()
        for edge in edges:
            if edge.source_id:
                referenced_ids.add(edge.source_id)
            if edge.target_id:
                referenced_ids.add(edge.target_id)

        return [
            Node(
                node_id=node_id,
                node_name=node_id,
                english_name=node_id,
                node_type=UNKNOWN_TYPE,
                wikidata_id=None,
                raw_source=None,
                character_span=None,
                token_span=None,
            )
            for node_id in sorted(referenced_ids - existing_ids)
        ]

    def _allowed_types(self, state: KGGenerationState, nodes: List[Node]) -> List[str]:
        summary = state.get("rag_context_summary")
        ontology_types = list(getattr(summary, "ontology_node_types", None) or [])
        if ontology_types:
            return ontology_types
        return sorted({n.node_type for n in nodes if n.node_type and not is_unresolved(n)})
