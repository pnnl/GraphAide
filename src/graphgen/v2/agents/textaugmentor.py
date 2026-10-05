import logging
from typing import List

from pydantic import BaseModel, Field

from ..state import KGQuestionAnswerState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.textaugmentor")


class TextAugmentorSchema(BaseModel):
    augmented_texts: List[str] = Field(
        ..., description="List of augmented versions of the input text"
    )


class TextAugmentorToolSchema(BaseModel):
    """Input schema for TextAugmentorAgent tool."""

    raw_text: str = Field(description="The original text to augment with variations")


class TextAugmentorAgent(GraphAideAgent):
    """Generate augmented variations of input text for query expansion.

    Takes input text and uses an LLM to generate multiple paraphrased or
    semantically similar versions. Useful for expanding queries to improve
    retrieval coverage in RAG pipelines.

    Input state keys:
        raw_text (str): The original text to augment with variations.

    Output state keys:
        extended_QA_pairs (List[Tuple[str, str]]): Original plus augmented texts
            as (question, answer) tuples with empty answers.
    """

    tool_schema = TextAugmentorToolSchema
    tool_description = "Generate augmented variations of input text for query expansion"
    tool_output_keys = ["extended_QA_pairs"]

    def __call__(self, state: KGQuestionAnswerState) -> KGQuestionAnswerState:
        # Logic: combine Prompt + Model
        structured_llm = self.model.with_structured_output(TextAugmentorSchema)
        chain = self.prompt | structured_llm
        input_text = state.get("raw_text", "")
        # Map State 'raw_text' to Template 'question'
        inputs = {"raw_text": input_text, "k-new": 3}

        # Run
        try:
            result = self._invoke_chain(chain, inputs)
            logger.info(f"TextAugmentor: generated {len(result.augmented_texts)} variations")

            extended_QA_pairs = [(q, "") for q in result.augmented_texts]
            return {"extended_QA_pairs": [(input_text, "")] + extended_QA_pairs}
        except Exception as e:
            logger.error(f"TextAugmentor failed: {e}")
            return {"intent_scores": None}
