import logging
from typing import Optional

from pydantic import BaseModel, Field

from graphgen.v2.agents.base import GraphAideAgent
from graphgen.v2.state import KGQuestionAnswerState

logger = logging.getLogger("graphgen.agents.simplerag")


class SimpleRAGToolSchema(BaseModel):
    """Input schema for SimpleRAGAgent tool."""

    question: str = Field(description="The user's question to answer")
    graph_answer_text: Optional[str] = Field(
        default=None, description="Text from graph query results to incorporate"
    )


class SimpleRAGAgent(GraphAideAgent):
    """Answer questions using RAG with vector store and graph context.

    Combines vector store retrieval with graph answer context to generate
    comprehensive answers. Retrieves relevant documents from the vector store
    and incorporates any graph_answer_text from previous pipeline steps.

    Input state keys:
        question (str): The user's question to answer.
        graph_answer_text (str, optional): Text from graph query results.

    Output state keys:
        answer (str): The generated answer combining all context sources.
        messages (List[str]): The full LLM response object.

    Requires settings:
        vector_store: Vector store for similarity search and context retrieval.
    """

    tool_schema = SimpleRAGToolSchema
    tool_description = "Answer questions using RAG with vector store and optional graph context"
    tool_output_keys = ["answer", "messages"]

    def __call__(self, state: KGQuestionAnswerState) -> KGQuestionAnswerState:
        try:
            vector_store = self.settings.get("vector_store")

            if not vector_store:
                raise ValueError(
                    f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
                )
            chain = self.prompt | self.model
            question = state.get("question", "")
            graph_answer_text = state.get("graph_answer_text", "")
            context = ""
            try:
                docs = vector_store.similarity_search(question, k=3)
            except Exception as e:
                logger.error(f"SimpleRAG similarity search failed: {e}")
                docs = []
            for doc in docs:
                # Safe parsing - extract metadata and content
                meta_val = doc.metadata.get(
                    "source", doc.metadata.get("id", doc.metadata.get("title", ""))
                )
                doc_content = doc.page_content if hasattr(doc, "page_content") else ""

                if meta_val:
                    # If metadata has QID|Label format, parse it
                    if "|" in meta_val:
                        qid_label = meta_val.split("|")
                        if len(qid_label) >= 2:
                            context = context + f"QID={qid_label[0]} Label={qid_label[1]}" + "\n"
                    else:
                        # Metadata doesn't have QID format - use metadata:content
                        context = context + f"{meta_val}: {doc_content}" + "\n"
                elif doc_content:
                    # No metadata but has content - use content directly
                    context = context + doc_content + "\n"
            input_text = f"Question: {question}\nGraph Answer Text: {graph_answer_text}\nContext from Vector Store:\n{context}"
            response = self._invoke_chain(chain, {"question": input_text})
            logger.info("SimpleRAG: response generated")
            return {"messages": [response], "answer": response.content}
        except Exception as e:
            logger.error(f"SimpleRAG failed: {e}")
            return {
                "messages": [
                    "SimpleRAGAgent failed to process the input with error: " + str(e)
                ]
            }
