import logging
from typing import List

import openai
from pydantic import BaseModel, Field

from ..state import Edge, KGQuestionAnswerState, Node
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.neo4jqueryrunner")


class Neo4jPostProcessorSchema(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


class Neo4jQueryRunnerToolSchema(BaseModel):
    """Input schema for Neo4jQueryRunnerAgent tool."""

    graph_question: str = Field(description="A valid Cypher query to execute against Neo4j")


class Neo4jQueryRunnerAgent(GraphAideAgent):
    """Execute a Cypher query against the Neo4j graph database and return results.

    Takes a pre-generated Cypher query from the state and runs it against
    the configured Neo4j database, returning the query results.

    Input state keys:
        graph_question (str): A valid Cypher query to execute against Neo4j.

    Output state keys:
        graph_answer (Any): Raw results returned from the Neo4j query.
        messages (List[str]): Status messages including query results.
        is_valid (bool): Whether the query executed successfully.

    Requires settings:
        vector_store: Vector store instance (required but not used directly).
        graph_store: Neo4j graph database connection for query execution.
    """

    tool_schema = Neo4jQueryRunnerToolSchema
    tool_description = "Execute a Cypher query against Neo4j and return the results"
    tool_output_keys = ["graph_answer", "messages", "agent_status"]

    def __call__(self, state: KGQuestionAnswerState) -> KGQuestionAnswerState:

        # 1. Access the Vector Store from the factory-injected settings
        vector_store = self.settings.get("vector_store")
        graph_store = self.settings.get("graph_store")
        if not vector_store:
            raise ValueError(
                f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
            )

        try:
            query = state.get("graph_question", "")
            if not query:
                return {
                    "messages": [
                        "No graph question found in state to run against Neo4j."
                    ]
                }
            logger.info("Neo4jQuery: executing query")
            result = graph_store.query(query)

            # 4. Return updated state
            return {
                "messages": [
                    f"Successfully executed query. and received results: {result}"
                ],
                "current_agent": [self.__class__.__name__],
                "graph_answer": result,
                "agent_status": {self.__class__.__name__: True},
            }
        except openai.PermissionDeniedError as e:
            logger.error(f"Neo4jQuery permission denied [{e.status_code}]: {e.body}")
            return {"messages": [f"Permission denied: {e.body}"]}
        except Exception as e:
            logger.error(f"Neo4jQuery failed: {e}")
            return {"messages": [f"Error during extraction: {str(e)}"]}
