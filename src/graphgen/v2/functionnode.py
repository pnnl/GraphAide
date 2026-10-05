import logging
import math
import os
import re
import sys
import traceback

import openai
import tiktoken
from langchain_community.document_loaders import PyPDFLoader
from langgraph.constants import Send

from graphgen.v2.state import KGGenerationState

logger = logging.getLogger("graphgen.v2.functionnode")


def fileloader(state: KGGenerationState):
    """Reads text content from file_path OR input_text and splits into segments based on token limits.

    If input_text is provided, it takes precedence over file_path.

    Args:
        state: KGGenerationState with file_path OR input_text
    Returns:
        dict with segments and metadata
    """
    file_path = state.get("file_path", "")
    input_text = state.get("input_text")
    max_tokens_per_segment = state.get("max_tokens_per_segment", 4096)

    input_text_preview = f"<{len(input_text)} chars>" if input_text else None
    logger.info(f"DEBUG fileloader: file_path={file_path!r}, input_text={input_text_preview!r}")

    try:
        # Priority: input_text > file_path
        if input_text:
            logger.info(f"Processing input_text ({len(input_text)} chars)")
            logger.debug(f"\n{'='*80}\nFILELOADER INPUT_TEXT (first 500 chars):\n{'='*80}")
            logger.debug(input_text[:500])
            logger.debug(f"{'='*80}\n")
            segments = getTextSegments(input_text, max_tokens=max_tokens_per_segment)
            # For input_text, set file_path to placeholder if not provided
            if not file_path:
                file_path = "<input_text>"
        elif file_path:
            logger.debug(f"\n{'='*80}\nFILELOADER READING FILE:\n{'='*80}")
            logger.debug(f"File path: {file_path}")
            if file_path.endswith(".pdf"):
                segments = parse_pdf_file(file_path=file_path)
            elif file_path.endswith((".txt", ".md")):
                segments = parse_text_file(file_path=file_path, max_tokens=max_tokens_per_segment)
            else:
                # Treat unknown file types as text
                segments = parse_text_file(file_path=file_path, max_tokens=max_tokens_per_segment)
            if segments:
                logger.debug(f"First segment (first 500 chars):\n{segments[0][:500]}")
            logger.debug(f"{'='*80}\n")
        else:
            raise ValueError("Either file_path or input_text must be provided")

        return {
            "messages": [f"Successfully generated {len(segments)} segments."],
            "rag_context": state.get("rag_context"),
            "segments": segments,
            "file_path": file_path,  # Ensure file_path is in state
            "lensegments": len(segments),
        }
    except openai.PermissionDeniedError as e:
        logger.error(f"Permission denied [{e.status_code}]: {e.body}")
        return {"messages": [f"Permission denied: {e.body}"]}
    except Exception as e:
        logger.error(f"Segment extraction failed: {e}")
        return {
            "messages": [f"Error during segment generation: {str(e)}"]
        }


def make_segment_dispatcher(target_node: str):
    """Factory that creates a segment dispatcher for any target node.

    Args:
        target_node: Name of the node to send segments to (e.g., "knowledgegraphloader" or "extractor")

    Returns:
        A dispatcher function compatible with add_conditional_edges
    """

    def dispatch(state: KGGenerationState) -> list[Send]:
        segments = state.get("segments", [])
        file_path = state.get("file_path", "")
        logger.info(f"Dispatching {len(segments)} segments to {target_node}")
        return [
            Send(
                target_node,
                {
                    "raw_text": segment,
                    "file_path": file_path,
                    "segments": [segment],
                    "rag_context": state.get("rag_context"),
                    "vector_store_configs": state.get("vector_store_configs"),  # Preserve for multi-retriever
                    "messages": [
                        f"Successfully sent segment for extraction. total segments: {len(segments)}"
                    ],
                    "lensegments_map": len(segments),
                },
            )
            for segment in segments
        ]

    return dispatch


def map_fileloader(state: KGGenerationState) -> list[Send]:
    """Legacy dispatcher - targets 'extractor' node directly.

    For subgraph workflows, use make_segment_dispatcher('subgraph_name') instead.
    """
    return make_segment_dispatcher("extractor")(state)


def jsonl_segment_dispatcher(state: KGGenerationState) -> list[Send]:
    """Dispatch JSONL batch lines to parallel extractor workers.

    Chunks batch into groups based on max_workers. Each Send contains
    a subset of lines + metadata for parallel extraction.

    Returns:
        List of Send objects, one per worker
    """
    jsonl_lines = state.get("jsonl_lines", [])
    jsonl_line_numbers = state.get("jsonl_line_numbers", [])
    lines_per_batch = state.get("jsonl_lines_per_batch", 4)
    jsonl_field_name = state.get("jsonl_field_name", "text")
    ontology_path = state.get("ontology_path")

    if not jsonl_lines:
        logger.warning("⚠️ jsonl_segment_dispatcher: No lines to dispatch")
        return []

    # Calculate number of parallel jobs based on lines_per_batch
    num_parallel_batches = math.ceil(len(jsonl_lines) / lines_per_batch)
    logger.info(f"🔍 Dispatching {len(jsonl_lines)} lines to {num_parallel_batches} parallel jobs")
    logger.debug(f"   Lines per job: {lines_per_batch}, num jobs: {num_parallel_batches}")

    sends = []
    for i in range(0, len(jsonl_lines), lines_per_batch):
        chunk_lines = jsonl_lines[i:i+lines_per_batch]
        chunk_line_nums = jsonl_line_numbers[i:i+lines_per_batch]

        # Combine lines into single text for extraction
        combined_text = "\n---JSONL_SEPARATOR---\n".join([line.get("content", "") for line in chunk_lines])

        logger.debug(f"   → Job {i//lines_per_batch}: lines {chunk_line_nums[0]}-{chunk_line_nums[-1]} ({len(chunk_lines)} lines)")

        send_obj = Send(
            "extractor",
            {
                "raw_text": combined_text,
                "input_text": combined_text,
                "file_path": f"{state.get('jsonl_file_path')}:lines_{chunk_line_nums[0]}-{chunk_line_nums[-1]}",
                "ontology_path": ontology_path,
                "jsonl_lines": chunk_lines,
                "jsonl_line_numbers": chunk_line_nums,
                "jsonl_field_name": jsonl_field_name,
                "jsonl_tracking": state.get("jsonl_tracking", True),
                "vector_store_configs": state.get("vector_store_configs", []),
                "rag_context": state.get("rag_context"),
                "messages": [f"Dispatched {len(chunk_lines)} lines for extraction"],
            }
        )
        sends.append(send_obj)

    logger.info(f"✅ Created {len(sends)} Send objects for parallel dispatch")
    return sends


def parse_pdf_file(file_path: str) -> list[str]:
    """Reads a PDF file and splits its content into segments based on token limits.
    Returns a list of text segments.

    Args:
        file_path (str): _description_
    Returns:
        list[str]: _description_
    """
    loader = PyPDFLoader(file_path)
    try:
        docs = loader.load()
    except Exception as e:
        logger.error(f"Error loading PDF file at {file_path}: {e}")
        docs = []
    logger.info(f"Loaded {len(docs)} documents from {file_path} using PyPDFLoader")
    return [doc.page_content for doc in docs]


def parse_text_file(file_path: str, max_tokens: int = 4096) -> list[str]:
    """Reads a text file and splits its content into segments based on token limits.
    Returns a list of text segments.

    Args:
        file_path (str): Path to text file
        max_tokens (int): Maximum tokens per segment (default 4096)

    Returns:
        list[str]: List of text segments
    """

    try:
        logger.info(f"Reading: {file_path}")
        tokenizer = tiktoken.get_encoding("cl100k_base")
        with open(file_path, "r", encoding="utf-8") as file:
            file_name = os.path.basename(file_path)
            try:
                file_content_raw = file.read()
                file_content = decode_unicode(file_content_raw)
                text_segments = getTextSegments(file_content, max_tokens=max_tokens)
                logger.info(f"Created {len(text_segments)} segments (max {max_tokens} tokens each)")
                return text_segments
            except Exception as ed:
                logger.error(f"Read error: {ed}")
                return [f"Error reading file content: {str(ed)}"]
    except FileNotFoundError as fe:
        logger.error(f"File not found: {os.path.abspath(fe.filename)}")
        return [f"Error: Could not find file at: {os.path.abspath(fe.filename)}"]
    except Exception as e:
        return [f"Error reading file {file_path}: {str(e)}"]


def getTextSegments(text_data: str, max_tokens: int = 4096) -> list:
    """Split text into segments based on token limits.

    Args:
        text_data (str): Text content to segment
        max_tokens (int): Maximum tokens per segment (default 4096)

    Returns:
        list: List of text segments
    """
    file_content = decode_unicode(text_data)
    tokenizer = tiktoken.get_encoding("cl100k_base")
    # DONT print raw content becuase on windows + python, encoding raise excpetion
    try:
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

    # Split the token list into chunks of max_tokens
    segments = list(split_tokens(tokens, max_tokens))
    # Decode tokens back to text segments
    text_segments = [tokenizer.decode(segment) for segment in segments]

    # Now you have text split into segments that respect the token limit
    return text_segments


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
