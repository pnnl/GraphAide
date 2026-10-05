import logging
import traceback

from pydantic import BaseModel, Field

from graphgen.v2.agents.base import GraphAideAgent
from graphgen.v2.state import KGGenerationState

logger = logging.getLogger("graphgen.agents.simpleagent")


class SimpleAgentToolSchema(BaseModel):
    """Input schema for SimpleAgent tool."""

    raw_text: str = Field(description="Input text to process with the LLM")


class SimpleAgent(GraphAideAgent):
    """Basic LLM agent that processes raw text with a prompt template.

    A minimal agent that passes raw_text through a prompt template and LLM,
    returning the response. Useful for simple text transformations or as
    a template for custom agents.

    Input state keys:
        raw_text (str): Input text to process with the LLM.

    Output state keys:
        raw_text (str): The LLM's response text.
        messages (List[str]): The full LLM response object.
    """

    tool_schema = SimpleAgentToolSchema
    tool_description = "Process raw text through an LLM with a prompt template"
    tool_output_keys = ["raw_text", "messages"]

    def __call__(self, state: KGGenerationState) -> KGGenerationState:
        try:
            logger.info("SimpleAgent: processing input")
            chain = self.prompt | self.model
            response = self._invoke_chain(chain, {"raw_text": state.get("raw_text", "")})
            return {
                "messages": [response],
                "raw_text": response.content
                if hasattr(response, "content")
                else str(response),
            }
        except Exception as e:
            logger.error(f"Error in SimpleAgent: {e}")
            return {
                "messages": [
                    "SimpleAgent failed to process the input with error: "
                    + str(traceback.format_exc())
                ]
            }
