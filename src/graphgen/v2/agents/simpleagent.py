import logging
import os
import traceback

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from graphgen.v2.agents.base import GraphAideAgent
from graphgen.v2.state import SimpleAgentState

logger = logging.getLogger("graphgen.agents.simpleagent")


class SimpleAgentToolSchema(BaseModel):
    """Input schema for SimpleAgent tool."""

    file_path: str = Field(description="Path to the text file to process")
    instruction: str = Field(description="What to do with the document")


class SimpleAgent(GraphAideAgent):
    """Run an instruction over a text document with an LLM.

    Reads the document at file_path, fills the prompt template with the
    instruction and document text, and returns the model response. The
    template is simpleagent.template unless template_path overrides it.

    Input state keys:
        file_path (str): Path to the text file.
        instruction (str): What the agent should do with the document.
        template_path (str, optional): Custom prompt template file.

    Output state keys:
        response (str): The model's response text.
        messages (List): Raw model response.
    """

    tool_schema = SimpleAgentToolSchema
    tool_description = "Apply an instruction to a text document using an LLM"
    tool_output_keys = ["response", "messages"]

    def __call__(self, state: SimpleAgentState) -> dict:
        file_path = state.get("file_path", "")
        try:
            if not file_path or not os.path.isfile(file_path):
                raise FileNotFoundError(f"Document not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                document = f.read()

            prompt = self.prompt
            template_path = state.get("template_path")
            if template_path:
                with open(template_path, "r", encoding="utf-8") as f:
                    prompt = ChatPromptTemplate.from_template(f.read())

            chain = prompt | self.model
            response = self._invoke_chain(
                chain,
                {
                    "instruction": state.get("instruction", ""),
                    "file_content": document,
                    "file_name": os.path.basename(file_path),
                },
            )
            logger.debug(f"SimpleAgent: processed {file_path}")
            return {
                "messages": [response],
                "response": response.content
                if hasattr(response, "content")
                else str(response),
            }
        except Exception as e:
            logger.error(f"Error in SimpleAgent: {e}")
            return {
                "messages": [
                    "SimpleAgent failed to process the input with error: "
                    + str(traceback.format_exc())
                ],
                "response": "",
            }
