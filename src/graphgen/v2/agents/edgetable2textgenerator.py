import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..state import KGQuestionAnswerState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.edgetable2textgenerator")


class EdgeTable2TextGeneratorToolSchema(BaseModel):
    """Input schema for EdgeTable2TextGeneratorAgent tool."""

    graph_answer: Any = Field(
        description="Raw results from a Neo4j query to convert to text"
    )
    question: Optional[str] = Field(
        default=None, description="Original question for context"
    )


class EdgeTable2TextGeneratorAgent(GraphAideAgent):
    """Convert raw graph query results into human-readable natural language.

    Takes structured graph database results (typically edge/relationship data)
    and uses an LLM to generate a natural language summary or explanation.

    Input state keys:
        graph_answer (Any): Raw results from a Neo4j query to convert to text.
        question (str, optional): Original question for context.

    Output state keys:
        graph_answer_text (str): Natural language description of the graph results.
        messages (List[str]): Status messages including the generated response.
    """

    tool_schema = EdgeTable2TextGeneratorToolSchema
    tool_description = (
        "Convert raw graph query results into human-readable natural language"
    )
    tool_output_keys = ["graph_answer_text", "messages"]

    def __call__(self, state: KGQuestionAnswerState) -> KGQuestionAnswerState:
        try:
            chain = self.prompt | self.model
            question = state.get("question", "")
            edgetable = state.get("graph_answer", "No input data found")

            response = self._invoke_chain(chain, {"edge_table": edgetable})
            logger.info("EdgeTable2Text: response generated")
            return {
                "messages": [
                    "Edge Table 2 Text Generator response: " + response.content
                ],
                "graph_answer_text": response.content,
            }
        except Exception as e:
            logger.error(f"EdgeTable2Text failed: {e}")
            return {
                "messages": [
                    "Edge Table 2 Text Generator failed to process the input with error: "
                    + str(e)
                ]
            }
