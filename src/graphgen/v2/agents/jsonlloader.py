"""JSONLLoaderAgent - Read JSONL file, parse, and prepare batch for parallel extraction."""

import json
import logging
import math
from typing import Any, Dict

from langgraph.types import Command

from graphgen.v2.agents.base import GraphAideAgent
from graphgen.v2.state import KGGenerationState

logger = logging.getLogger(__name__)


class JSONLLoaderAgent(GraphAideAgent):
    """Load and parse JSONL file, prepare batch for parallel extraction.

    Reads JSONL file (one JSON object per line), validates field exists,
    and prepares a batch of lines for parallel extraction.
    """

    def __call__(self, state: KGGenerationState, config: Dict[str, Any] = None) -> Command:
        """Load JSONL batch and prepare for dispatch.

        Args:
            state: Current workflow state
            config: Configuration dict

        Returns:
            Command updating state with batch metadata
        """
        jsonl_path = state.get("file_path")
        field_name = state.get("jsonl_field_name", "text")
        lines_per_batch = state.get("jsonl_lines_per_batch", 4)

        if not jsonl_path:
            logger.error("❌ file_path not provided")
            return Command(update={
                "messages": ["Error: file_path required"],
                "current_agent": [self.__class__.__name__],
            })

        logger.info(f"🔍 Loading JSONL from: {jsonl_path}")
        logger.info(f"   Field to extract: '{field_name}'")

        try:
            # Read all lines from JSONL (in real implementation, would read batch_size lines)
            all_lines = []
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if field_name not in obj:
                            logger.warning(f"   ⚠️ Line {line_num}: Missing field '{field_name}', skipping")
                            continue
                        all_lines.append({
                            "line_number": line_num,
                            "content": str(obj[field_name]),
                            "raw_json": obj
                        })
                    except json.JSONDecodeError as e:
                        logger.warning(f"   ⚠️ Line {line_num}: Invalid JSON - {e}")
                        continue

            if not all_lines:
                logger.error(f"❌ No valid lines found in {jsonl_path}")
                return Command(update={
                    "messages": ["Error: No valid JSONL lines found"],
                    "current_agent": [self.__class__.__name__],
                })

            # Prepare state for dispatch
            jsonl_lines = [{"content": l["content"]} for l in all_lines]
            jsonl_line_numbers = [l["line_number"] for l in all_lines]

            logger.info(f"✅ Loaded {len(jsonl_lines)} lines from JSONL")
            logger.info(f"   Lines per batch: {lines_per_batch}")
            logger.info(f"   Parallel jobs: ceil({len(jsonl_lines)}/{lines_per_batch}) = {math.ceil(len(jsonl_lines) / lines_per_batch)}")
            logger.info(f"   DEBUG: First line #{jsonl_line_numbers[0]}: {jsonl_lines[0]['content'][:80]}...")

            return Command(update={
                "jsonl_lines": jsonl_lines,
                "jsonl_line_numbers": jsonl_line_numbers,
                "jsonl_failed_lines": [],
                "messages": [f"Loaded {len(jsonl_lines)} lines from JSONL for batch processing"],
                "current_agent": [self.__class__.__name__],
            })

        except FileNotFoundError:
            logger.error(f"❌ JSONL file not found: {jsonl_path}")
            return Command(update={
                "messages": [f"Error: JSONL file not found: {jsonl_path}"],
                "current_agent": [self.__class__.__name__],
            })
        except Exception as e:
            logger.error(f"❌ Error loading JSONL: {e}", exc_info=True)
            return Command(update={
                "messages": [f"Error loading JSONL: {str(e)}"],
                "current_agent": [self.__class__.__name__],
            })
