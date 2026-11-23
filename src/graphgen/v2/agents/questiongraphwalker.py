import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

from ..state import KGQuestionAnswerState
from .base import GraphAideAgent
from .neo4jqueryrunner import find_write_operation

logger = logging.getLogger("graphgen.agents.questiongraphwalker")

MAX_ATTEMPTS = 3
MAX_LIMIT = 10
_TRAILING_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\s*$", re.I)
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class QuestionGraphWalkerToolSchema(BaseModel):
    """Input schema for QuestionGraphWalkerAgent tool."""

    question: str = Field(
        description="Natural language question about the knowledge graph"
    )


class QuestionGraphWalkerAgent(GraphAideAgent):
    """Generate a free-form read-only Cypher query and validate it against Neo4j.

    The LLM proposes a query. Deterministic checks run before it is accepted:
    read-only keyword check, a trailing LIMIT of 10 or less, and EXPLAIN, which
    compiles the query without executing it. A rejected attempt is sent back to
    the LLM with the reason, up to MAX_ATTEMPTS times.

    Input state keys:
        question (str): Natural language question about the knowledge graph.

    Output state keys:
        graph_question (str): Validated Cypher query (not executed).
        messages (List[str]): Status messages.

    Requires settings:
        graph_store: Neo4j connection used for EXPLAIN validation.
    """

    tool_schema = QuestionGraphWalkerToolSchema
    tool_description = (
        "Generate a free-form read-only Cypher query for a natural language question"
    )
    tool_output_keys = ["graph_question", "messages"]

    def __call__(self, state: KGQuestionAnswerState) -> KGQuestionAnswerState:
        question = state.get("question", "")
        graph_store = self.settings.get("graph_store")
        feedback = ""
        problem = "no attempt made"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._invoke_chain(
                    self.prompt | self.model,
                    {"raw_text": question, "feedback": feedback},
                )
            except Exception as e:
                logger.error(f"QueryGraphWalk failed: {e}")
                return {
                    "messages": [
                        "Query Graph Walker failed to process the input with error: "
                        + str(e)
                    ]
                }

            cypher = _FENCE.sub("", response.content.strip()).strip()
            problem = self._check(cypher, graph_store)
            if problem is None:
                logger.debug(f"QueryGraphWalk: query validated on attempt {attempt}")
                return {"messages": [response], "graph_question": cypher}

            logger.warning(f"QueryGraphWalk attempt {attempt} rejected: {problem}")
            feedback = (
                f"Your previous query was rejected: {problem}\n"
                f"Previous query:\n{cypher}\n"
                "Write a corrected query."
            )

        return {
            "messages": [
                f"Query Graph Walker could not produce a valid query after {MAX_ATTEMPTS} attempts: {problem}"
            ]
        }

    def _check(self, cypher: str, graph_store) -> Optional[str]:
        """Return the reason a query is rejected, or None if it is accepted."""
        if not cypher:
            return "the query is empty"

        blocked = find_write_operation(cypher)
        if blocked:
            return f"it is not read-only ({blocked})"

        limit = _TRAILING_LIMIT.search(cypher.rstrip(";").rstrip())
        if not limit or int(limit.group(1)) > MAX_LIMIT:
            return f"it must end with LIMIT {MAX_LIMIT} or less"

        if graph_store is None:
            return "no graph connection is available for validation"

        try:
            graph_store.query(f"EXPLAIN {cypher}")
        except Exception as e:
            return f"Neo4j rejected the query: {e}"

        return None
