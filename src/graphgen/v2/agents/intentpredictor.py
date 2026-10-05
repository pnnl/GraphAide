import logging

from pydantic import BaseModel, Field

from ..state import IntentSchema, KGQuestionAnswerState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.intentpredictor")


class IntentPredictorToolSchema(BaseModel):
    """Input schema for IntentPredictorAgent tool."""

    raw_text: str = Field(description="The question or text to analyze for intent")


class IntentPredictorAgent(GraphAideAgent):
    """Analyze a question to predict its intent dimensions for routing.

    Evaluates the input question across multiple intent dimensions including
    subjectivity, locality, navigationality, procedurality, and causality.
    Used to determine optimal query strategies.

    Input state keys:
        raw_text (str): The question or text to analyze for intent.

    Output state keys:
        intent_scores (IntentSchema): Structured scores for each intent dimension.
    """

    tool_schema = IntentPredictorToolSchema
    tool_description = "Analyze a question to predict intent dimensions (subjectivity, locality, navigationality, procedurality, causality)"
    tool_output_keys = ["intent_scores"]

    def __call__(self, state: KGQuestionAnswerState) -> KGQuestionAnswerState:
        # Logic: combine Prompt + Model
        structured_llm = self.model.with_structured_output(IntentSchema)
        chain = self.prompt | structured_llm

        # Map State 'raw_text' to Template 'question'
        logger.info("IntentPredictor: analyzing input")
        inputs = {"question": state.get("raw_text", "")}

        # Run
        try:
            result = self._invoke_chain(chain, inputs)
            opdata = IntentSchema(**result.dict())
            return {"intent_scores": opdata}
        except Exception as e:
            logger.error(f"IntentPredictor failed: {e}")
            return {"intent_scores": None}
