import base64
import logging
import mimetypes
import os
import traceback

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from graphgen.v2.agents.base import GraphAideAgent
from graphgen.v2.state import ImageExplainerState

logger = logging.getLogger("graphgen.agents.imageexplainer")


class ImageExplainerToolSchema(BaseModel):
    """Input schema for ImageExplainerAgent tool."""

    file_path: str = Field(description="Path to the image file to explain")


class ImageExplainerAgent(GraphAideAgent):
    """Describe the key findings of an image using a vision-capable LLM.

    Reads an image from disk, sends it with the prompt from imageexplainer.template
    to a multimodal model, and returns the generated description.

    Input state keys:
        file_path (str): Path to the image file (PNG, JPG, JPEG, GIF, BMP, WEBP).

    Output state keys:
        explanation (str): Text description of the key findings in the image.
        messages (List): Raw model response.
    """

    tool_schema = ImageExplainerToolSchema
    tool_description = "Describe the key findings of an image file using a vision LLM"
    tool_output_keys = ["explanation", "messages"]

    def __call__(self, state: ImageExplainerState) -> dict:
        file_path = state.get("file_path", "")
        try:
            if not file_path or not os.path.isfile(file_path):
                raise FileNotFoundError(f"Image file not found: {file_path}")

            with open(file_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            mime_type = mimetypes.guess_type(file_path)[0] or "image/png"

            prompt = self.prompt
            template_path = state.get("template_path")
            if template_path:
                with open(template_path, "r", encoding="utf-8") as f:
                    prompt = ChatPromptTemplate.from_template(f.read())

            prompt_text = prompt.format_messages(
                file_name=os.path.basename(file_path)
            )[0].content

            message = HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                    {"type": "text", "text": prompt_text},
                ]
            )
            response = self._invoke_chain(self.model, [message])
            logger.debug(f"ImageExplainer: described {file_path}")
            return {
                "messages": [response],
                "explanation": response.content
                if hasattr(response, "content")
                else str(response),
            }
        except Exception as e:
            logger.error(f"Error in ImageExplainerAgent: {e}")
            return {
                "messages": [
                    "ImageExplainerAgent failed to process the input with error: "
                    + str(traceback.format_exc())
                ],
                "explanation": "",
            }
