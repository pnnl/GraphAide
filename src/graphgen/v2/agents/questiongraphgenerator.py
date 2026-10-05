import logging

from pydantic import BaseModel, Field

from ..state import KGQuestionAnswerState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.questiongraphgenerator")


class QuestionGraphGeneratorToolSchema(BaseModel):
    """Input schema for QuestionGraphGeneratorAgent tool."""

    question: str = Field(
        description="Natural language question about the knowledge graph"
    )


class QuestionGraphGeneratorAgent(GraphAideAgent):
    """Convert a natural language question into a Cypher query for Neo4j.

    Takes a user question and uses an LLM to generate an appropriate
    Cypher query that can retrieve relevant information from the knowledge graph.

    Input state keys:
        question (str): Natural language question about the knowledge graph.

    Output state keys:
        graph_question (str): Generated Cypher query to execute against Neo4j.
        messages (List[str]): Status messages including the LLM response.
    """

    tool_schema = QuestionGraphGeneratorToolSchema
    tool_description = (
        "Convert a natural language question into a Cypher query for Neo4j"
    )
    tool_output_keys = ["graph_question", "messages"]

    def __call__(self, state: KGQuestionAnswerState) -> KGQuestionAnswerState:
        try:
            chain = self.prompt | self.model
            response = self._invoke_chain(chain, {"raw_text": state.get("question", "")})
            logger.info("QueryGraphGen: query generated")
            return {"messages": [response], "graph_question": response.content}
        except Exception as e:
            logger.error(f"QueryGraphGen failed: {e}")
            return {
                "messages": [
                    "Query Graph Generator failed to process the input with error: "
                    + str(e)
                ]
            }
