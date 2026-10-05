import importlib
import logging
import os
import re
import traceback
from typing import Any, List

import tiktoken
from langchain.tools import tool
from langchain_core.documents import Document
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

import graphgen.v2.globalconfig as gc

logger = logging.getLogger("graphgen.v2.tools")


@tool
def parse_text_file(file_path: str) -> str:
    """Reads a text file and splits its content into segments based on token limits.
    Returns a list of text segments.

    Args:
        file_path (str): _description_

    Returns:
        str: _description_
    """

    try:
        logger.info(f"Reading: {file_path}")
        tokenizer = tiktoken.get_encoding("cl100k_base")
        with open(file_path, "r", encoding="utf-8") as file:
            file_name = os.path.basename(file_path)

            file_content_raw = file.read()
            file_content = decode_unicode(file_content_raw)
            text_segments = getTextSegments(file_content)

        return text_segments
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


@tool
def getTextSegments(text_data: str) -> list:
    """_summary_

    Args:
        text_data (str): _description_

    Returns:
        list: _description_
    """
    file_content = decode_unicode(text_data)
    tokenizer = tiktoken.get_encoding("cl100k_base")
    # DONT print raw content becuase on windows + python, encoding raise excpetion
    try:
        import sys
        original_stdout = sys.stdout
        # Ensure stdout supports reconfigure
        if hasattr(sys.stdout, "reconfigure"):
            # Reconfigure stdout to use UTF-8 encoding
            sys.stdout.reconfigure(encoding="utf-8")
        else:
            pass  # stdout reconfigure not supported
    except Exception as e1:
        # print("************Fails to print raw content")
        tb = traceback.extract_tb(e1.__traceback__)
        traceback.print_exc()

    # Tokenize the text
    tokens = tokenizer.encode(file_content)

    # Split the token list into chunks of max_tokens_per_segment
    segments = list(split_tokens(tokens, 96000))  # max is 128000
    # TODO: even after removing schema as a variable from the prompt, some version of it (much smaller) is added to the final msg.
    # Decode tokens back to text segments
    text_segments = [tokenizer.decode(segment) for segment in segments]

    ##print(f"len of segments {len(text_segments)}")
    # Now you have text split into segments that respect the token limit
    return text_segments


@tool
# Function to split the tokens into chunks
def split_tokens(tokens, max_size):
    """Splits a list of tokens into smaller chunks of a specified maximum size.

    Args:
        tokens (list): The list of tokens to be split.
        max_size (int): The maximum size of each chunk.

    Yields:
        list: Chunks of tokens with a maximum size of max_size.
    """
    for i in range(0, len(tokens), max_size):
        yield tokens[i : i + max_size]


@tool
def decode_unicode(data):
    """_summary_

    Args:
        data (_type_): _description_
    """

    def needs_decoding(s):
        """
        Checks if a string contains Unicode escape sequences or patterns that require decoding.
        """
        if not isinstance(s, str):
            return False
        # Look for patterns like \uXXXX, \xXX, or other escape sequences
        return bool(re.search(r"\\u[\dA-Fa-f]{4}|\\x[\dA-Fa-f]{2}|\\[a-z]", s))

    if isinstance(data, str):
        # Check if the string needs decoding
        if needs_decoding(data):
            try:
                return data.encode("utf-8").decode("unicode_escape")
            except UnicodeDecodeError:
                return data  # Return the original string if decoding fails
        return data  # Return the string as-is if no decoding is needed
    elif isinstance(data, dict):
        # Recursively decode keys and values
        return {decode_unicode(k): decode_unicode(v) for k, v in data.items()}
    elif isinstance(data, list):
        # Recursively decode each item in the list
        return [decode_unicode(item) for item in data]
    return data  # Return non-string, non-list, non-dict data as-is


@tool
def removeDot(local_graph):
    """Replaces dots in node types and edge types with underscores in the given graph.

    Args:
        local_graph (_type_): _description_

    Returns:
        _type_: _description_
    """
    tmpnodes = []

    for nd in local_graph.nodes:
        ##print("*************ND********"+str(nd))
        if isinstance(nd, dict):  # new pydentic object is a dict
            if "type" in nd:
                nd["type"] = nd["type"].replace(".", "_")
            ndlist = list(nd.values())
        else:  # its a tuple
            ndlist = list(nd)
            ndlist[1] = ndlist[1].replace(".", "_")
        tmpnodes.append(tuple(ndlist))

    local_graph.nodes = tmpnodes
    tmpedges = []
    for ed in local_graph.edges:
        ##print("*************ED********"+str(ed))
        if isinstance(ed, dict):
            if "edge_type" in ed:
                ed["edge_type"] = ed["edge_type"].replace(".", "_")
            edlist = list(ed.values())
        else:
            edlist = list(ed)
            edlist[1] = edlist[1].replace(".", "_")
        tmpedges.append(tuple(edlist))
    local_graph.edges = tmpedges

    return local_graph


class SimilaritySearchInput(BaseModel):
    """Input schema for similarity search tool."""

    query: str = Field(description="The search query text to find similar documents")
    k: int = Field(
        default=gc.DEFAULT_K, description="Number of similar documents to return"
    )


def similarity_search(
    state_or_dict: dict,
    vector_store: Any,
    query_key: str = "query",
    k_key: str = "k",
    default_k: int = gc.DEFAULT_K,
) -> dict:
    """Perform similarity search on a vector store.

    Can be used as a standalone function or as part of a GraphAide-LangGraph workflow.

    Args:
        state_or_dict: Agent state or dict containing query and optionally k.
            Expected keys: query_key (str) for the search text, k_key (int) for result count.
        vector_store: The vector store instance to search.
        query_key: Key in state_or_dict containing the query string. Default "query".
        k_key: Key in state_or_dict containing k value. Default "k".
        default_k: Default number of results if k not provided. Default gc.DEFAULT_K.

    Returns:
        dict with keys:
            - search_results: List of Document objects
            - search_results_text: Formatted string of results
            - messages: Status message

    Example:
        # As standalone function
        results = similarity_search(
            {"query": "What is ATO?", "k": 5},
            vector_store=my_vector_store
        )

        # In a LangGraph workflow
        def my_node(state):
            return similarity_search(state, vector_store)
    """
    importlib.reload(gc)  # Ensure we have the latest global config
    query = state_or_dict.get(query_key, "")
    k = state_or_dict.get(k_key, default_k)

    if not query:
        return {
            "search_results": [],
            "search_results_text": "No query provided",
            "messages": ["Error: No query provided for similarity search"],
        }

    if not vector_store:
        return {
            "search_results": [],
            "search_results_text": "No vector store provided",
            "messages": ["Error: No vector store available for similarity search"],
        }

    try:
        docs: List[Document] = vector_store.similarity_search(query, k=k)

        # Format results as text
        results_text = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", doc.metadata.get("title", "Unknown"))
            results_text.append(
                f"[{i + 1}] {source}\n{doc.page_content[: gc.CONTENT_LABEL_LIMIT]}..."
            )

        formatted_text = (
            "\n\n".join(results_text) if results_text else "No results found"
        )

        return {
            "search_results": docs,
            "search_results_text": formatted_text,
            "messages": [
                f"Found {len(docs)} similar documents for query: {query[:50]}..."
            ],
        }
    except Exception as e:
        return {
            "search_results": [],
            "search_results_text": f"Error: {str(e)}",
            "messages": [f"Error during similarity search: {str(e)}"],
        }


def create_similarity_search_tool(vector_store: Any, name: str = "similarity_search"):
    """Create a StructuredTool for similarity search with injected vector store.

    Args:
        vector_store: The vector store instance to use for searches.
        name: Tool name. Default "similarity_search".

    Returns:
        StructuredTool that can be used with LLM agents.

    Example:
        search_tool = create_similarity_search_tool(my_vector_store)
        tools = [search_tool, other_tool]
        agent = create_agent(llm, tools)
    """

    def _search(query: str, k: int = gc.DEFAULT_K) -> str:
        result = similarity_search({"query": query, "k": k}, vector_store=vector_store)
        return result["search_results_text"]

    return StructuredTool.from_function(
        func=_search,
        name=name,
        description="Search the vector database for documents similar to the query. "
        "Use this to find relevant information from loaded documents. "
        "Returns the most similar document chunks.",
        args_schema=SimilaritySearchInput,
    )


def wrap_agent_as_tool(
    agent_instance,
    name: str,
    description: str,
    input_schema: BaseModel,
    input_mapping: dict,  # Maps tool input fields to state keys
    output_key: str,  # Which key from result to return
):
    """
    Wrap a GraphAideAgent as a LangChain StructuredTool.

    Args:
        agent_instance: The instantiated GraphAideAgent
        name: Tool name (used by LLM to call it)
        description: What this tool does (LLM reads this to decide when to use it)
        input_schema: Pydantic model defining the tool's inputs
        input_mapping: Dict mapping input_schema fields -> state keys
        output_key: Which key from the agent's output to return
    """

    def _run(**kwargs) -> str:
        # Build state from tool inputs using the mapping
        state = {}
        for tool_field, state_key in input_mapping.items():
            if tool_field in kwargs:
                state[state_key] = kwargs[tool_field]

        # Run the agent
        result = agent_instance(state)

        # Return the relevant output
        output = result.get(output_key, str(result.get("messages", ["No output"])))
        return str(output) if not isinstance(output, str) else output

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=description,
        args_schema=input_schema,
    )
