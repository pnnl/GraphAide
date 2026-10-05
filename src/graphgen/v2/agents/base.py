import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from langchain.tools import BaseTool, ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command
from pydantic import BaseModel

from graphgen.v2.LangFuseManager import get_langfuse_callback, get_debug_callback

logger = logging.getLogger("graphgen.agents.base")


class GraphAideAgent(ABC):
    """Abstract base class for all GraphAide agents.

    All agents inherit from this class and implement the __call__ method
    to process state dictionaries in LangGraph workflows.

    Attributes:
        model: The LLM model instance for generating responses.
        prompt: Compiled ChatPromptTemplate from the template string.
        settings: Configuration dict including vector_store, graph_store, etc.
        tool_schema: Pydantic model defining tool input schema (set by subclasses).
        tool_description: Description of the tool for LLM (set by subclasses).
        tool_output_keys: Keys from agent output to return as tool result and update state.

    Note:
        When used as a tool via as_tool(), the tool:
        1. Receives shared state via InjectedState (reads rag_context, nodes, etc.)
        2. Returns a Command that updates shared state with tool outputs (excluding 'messages')
        3. Adds a ToolMessage so the LLM sees the result

        This enables automatic state sharing between tools without LLM passing values.
    """

    # Tool-related class attributes - subclasses should override these
    tool_schema: Optional[Type[BaseModel]] = None
    tool_description: str = ""
    tool_output_keys: List[str] = ["messages"]

    def __init__(
        self, model: BaseChatModel, template_str: str, settings: Dict[str, Any] = None
    ):
        self.model = model
        self.settings = settings or {}
        # Pre-compile the template from the file content
        self.prompt = ChatPromptTemplate.from_template(template_str)
        # LangFuse client reference (for future use in Phase 3 for workflow-level tracing)
        self._langfuse_client = get_langfuse_callback()
        self._debug_callback = get_debug_callback()
        if self._langfuse_client:
            logger.debug(f"🔍 [{self.__class__.__name__}] LangFuse callback available for tracing")

    def _invoke_chain(self, chain, inputs: Dict[str, Any]) -> Any:
        """Invoke a chain with LangFuse and debug callbacks attached.

        Use this instead of chain.invoke() directly to ensure traces are captured.

        Args:
            chain: LangChain chain/runnable to invoke
            inputs: Input dict for the chain

        Returns:
            Chain output
        """
        callbacks = [self._debug_callback]
        if self._langfuse_client:
            callbacks.insert(0, self._langfuse_client)
        config = {"callbacks": callbacks}
        return chain.invoke(inputs, config=config)

    @abstractmethod
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Main node logic for LangGraph."""
        pass

    def as_tool(self, name: Optional[str] = None) -> BaseTool:
        """Convert this agent to a LangChain tool with state injection via ToolRuntime.

        The tool receives shared state via ToolRuntime.state, allowing it to read
        values like rag_context, nodes, edges without requiring the LLM
        to pass them explicitly. Tool inputs are merged with state, with explicit
        inputs taking precedence.

        The tool returns a Command that:
        1. Updates shared state with outputs (excluding 'messages')
        2. Adds a ToolMessage so the LLM sees the result

        Args:
            name: Optional tool name. Defaults to the class name.

        Returns:
            BaseTool that wraps this agent for use with LLM tool calling.

        Raises:
            ValueError: If tool_schema is not defined on the agent class.
        """
        if self.tool_schema is None:
            raise ValueError(
                f"Agent '{self.__class__.__name__}' has no tool_schema defined. "
                "Set the tool_schema class attribute to use as_tool()."
            )

        # Capture self for closure
        agent = self
        tool_name = name or self.__class__.__name__
        tool_desc = self.tool_description or f"Run the {self.__class__.__name__}"

        # Use @tool decorator with ToolRuntime for state access
        # args_schema tells the LLM the exact parameters to pass
        @tool(tool_name, description=tool_desc, args_schema=agent.tool_schema)
        def _run(runtime: ToolRuntime, **kwargs) -> Command:
            # ToolRuntime provides access to shared state and tool_call_id
            state = runtime.state or {}
            tool_call_id = runtime.tool_call_id

            # Merge state with explicit tool inputs (tool inputs take precedence)
            merged = dict(state)
            merged.update(kwargs)

            # Call the agent's __call__ method with merged state
            result = agent(merged)

            # Extract all output keys for the tool message (LLM sees this)
            output = {k: result.get(k) for k in agent.tool_output_keys if k in result}
            if not output:
                output = {"messages": result.get("messages", ["No output"])}

            # Extract state update keys (everything except 'messages')
            state_update = {
                k: result.get(k)
                for k in agent.tool_output_keys
                if k in result and k != "messages"
            }

            # Add ToolMessage to state update
            state_update["messages"] = [
                ToolMessage(
                    content=json.dumps(output, default=str),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            ]

            # Return Command that updates state
            return Command(update=state_update)

        return _run

    def _escape_cypher_value(self, value: Any) -> Any:
        """Escape special characters for safe Cypher query execution.

        Handles backslashes, double quotes, and single quotes.

        Args:
            value: Value to escape (string or non-string passthrough)

        Returns:
            Escaped string or original value if not a string
        """
        if not isinstance(value, str):
            return value
        # Order matters: escape backslashes first, then quotes
        value = value.replace("\\", "\\\\")
        value = value.replace('"', '\\"')
        value = value.replace("'", "\\'")
        return value

    def _escape_model_list(self, items: List, escape_fn) -> List:
        """Apply escaping function to all string values in Pydantic model list.

        Args:
            items: List of Pydantic models or dicts
            escape_fn: Function to escape individual values

        Returns:
            List of dicts with escaped string values
        """
        escaped_items = []
        for item in items:
            item_dict = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            escaped_dict = {}
            for key, value in item_dict.items():
                escaped_dict[key] = escape_fn(value)
            escaped_items.append(escaped_dict)
        return escaped_items

    def _invoke_cypher_chain(self, graph_store, nodes, edges, inputtext):
        """Invoke GraphCypherQAChain with consistent setup and error handling.

        Escapes nodes and edges, creates chain, invokes with input, returns result.

        Args:
            graph_store: Neo4j graph store connection
            nodes: List of Node objects (Pydantic models)
            edges: List of Edge objects (Pydantic models)
            inputtext: JSON string to pass to chain as 'query' key

        Returns:
            Tuple of (result_dict, error). If successful, error is None.
            If failed, result_dict is None and error is the Exception.
        """
        from langchain_neo4j import GraphCypherQAChain
        from graphgen.v2.utils import get_chain_verbose, strip_thinking_tokens
        import logging

        logger = logging.getLogger(self.__class__.__module__)

        try:
            # Escape all string values in nodes/edges for Cypher safety
            nodes_escaped = self._escape_model_list(nodes, self._escape_cypher_value)
            edges_escaped = self._escape_model_list(edges, self._escape_cypher_value)

            # Create and invoke chain
            chain = GraphCypherQAChain.from_llm(
                self.model,
                memory=None,
                graph=graph_store,
                verbose=get_chain_verbose(),
                return_intermediate_steps=True,
                cypher_prompt=self.prompt,
                allow_dangerous_requests=True,
            )
            result = chain.invoke({"query": inputtext})
            # GraphCypherQAChain returns generated Cypher in intermediate_steps
            # Strip thinking tokens that may have leaked into the query
            if isinstance(result, dict) and "intermediate_steps" in result:
                cleaned_steps = []
                for step in result.get("intermediate_steps", []):
                    if isinstance(step, dict):
                        # Step is like {'query': 'MATCH ...', ...}
                        if "query" in step:
                            step["query"] = strip_thinking_tokens(step["query"])
                    elif isinstance(step, (list, tuple)) and len(step) > 1:
                        # Step might be (query_string, result) tuple
                        step_list = list(step)
                        step_list[0] = strip_thinking_tokens(str(step_list[0]))
                        step = tuple(step_list) if isinstance(step, tuple) else step_list
                    cleaned_steps.append(step)
                result["intermediate_steps"] = cleaned_steps
            return result, None
        except Exception as e:
            logger.error(f"{self.__class__.__name__} chain failed: {e}")
            return None, e
