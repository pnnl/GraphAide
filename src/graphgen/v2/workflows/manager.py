"""WorkflowManager: Main orchestrator for all workflows using LangGraph."""

import json
import logging
import os
import time
from typing import Any, Callable, Dict, Optional, Type, Union

logger = logging.getLogger("graphgen.workflow")

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send
from pydantic import BaseModel

from graphgen.v2.agents.chunktrackeragent import ChunkTrackerAgent
from graphgen.v2.agents.chunkgraphloadagent import ChunkGraphLoadAgent
from graphgen.v2.agents.edgesloader import EdgesLoaderAgent
from graphgen.v2.agents.embeddingprojector import EmbeddingProjectorAgent
from graphgen.v2.agents.embeddingvisualizer import EmbeddingVisualizerAgent
from graphgen.v2.agents.extractmerger import ExtractMergerAgent
from graphgen.v2.agents.extractor import ExtractorAgent
from graphgen.v2.agents.intentpredictor import IntentPredictorAgent
from graphgen.v2.agents.jsonlloader import JSONLLoaderAgent
from graphgen.v2.agents.neo4jpostprocessor import Neo4jPostProcessorAgent
from graphgen.v2.agents.neo4jqueryrunner import Neo4jQueryRunnerAgent
from graphgen.v2.agents.nodes4edgesloader import Nodes4EdgesLoaderAgent
from graphgen.v2.agents.nodesloader import NodesLoaderAgent
from graphgen.v2.agents.ontologygenerator import OntologyGeneratorAgent
from graphgen.v2.agents.ontologyloader import OntologyLoaderAgent
from graphgen.v2.agents.questiongraphgenerator import QuestionGraphGeneratorAgent
from graphgen.v2.agents.simplerag import SimpleRAGAgent
from graphgen.v2.agents.vectordbloader import VectorDBLoaderAgent
from graphgen.v2.functionnode import fileloader, jsonl_segment_dispatcher, make_segment_dispatcher
from graphgen.v2.state import KGGenerationState, KGQuestionAnswerState
from graphgen.v2.workflows.base import (
    WorkflowConfig,
    WorkflowInfo,
    WorkflowRegistry,
    WorkflowResult,
)
from graphgen.v2.workflows.schemas import (
    KGExtractInput,
    KGExtractMergeInput,
    KGExtractMergeOutput,
    KGExtractOutput,
    KGIngestInput,
    KGIngestOutput,
    KGLoadJsonInput,
    KGLoadJsonOutput,
    KGQueryInput,
    KGQueryOutput,
    OntologyGenerateInput,
    OntologyGenerateOutput,
    VectorDBIngestInput,
    VectorDBIngestOutput,
    VectorDBVisualizeInput,
    VectorDBVisualizeOutput,
)
from graphgen.v2.workflows.utils import (
    get_agent_factory,
    init_kg_generation_state,
    init_kg_qa_state,
)


class WorkflowManager:
    """Unified interface for executing GraphAide workflows using LangGraph.

    The WorkflowManager provides:
    - A registry of all available workflows
    - Hierarchical configuration (global + per-call overrides)
    - LangGraph-based workflow building with parallel execution
    - High-level run() API for simple usage
    - build_workflow() for advanced users who want the compiled graph
    """

    def __init__(self, global_config: Optional[WorkflowConfig] = None):
        """Initialize WorkflowManager with optional global configuration.

        Args:
            global_config: Global configuration applied to all workflows.
                          Can be overridden per workflow call.
        """
        # Auto-initialize logging if not already set up
        from graphgen.v2.utils import setup_logging
        graphgen_logger = logging.getLogger("graphgen")
        if not graphgen_logger.handlers:
            setup_logging(log_level="INFO")

        self.registry = WorkflowRegistry()
        self.global_config = global_config or WorkflowConfig()
        self._register_builtin_workflows()

    def _add_parallel_loaders(self, workflow, source_node: str, target_nodes: list, merger_node: str):
        """Add parallel node/edge loader edges to workflow.

        Consolidates repeated pattern:
            - Dispatch source_node to multiple target nodes in parallel
            - Merge results back to merger_node

        Args:
            workflow: StateGraph instance
            source_node: Node to dispatch from (e.g., "nodes4edgesloader")
            target_nodes: List of nodes to dispatch to (e.g., ["nodesloader", "edgesloader"])
            merger_node: Node to merge results back to (e.g., "neo4jpostprocessor")
        """
        workflow.add_conditional_edges(
            source_node,
            lambda state: [Send(node, state) for node in target_nodes],
            target_nodes,
        )
        for node in target_nodes:
            workflow.add_edge(node, merger_node)

    def _serialize_graph_data(self, nodes, edges, include_field_remaps: bool = True):
        """Convert Pydantic models to dicts with optional field renaming.

        Consolidates the repeated pattern of:
        1. Converting Pydantic models to dicts (with hasattr fallback)
        2. Renaming grounding_id → node_id for nodes
        3. Renaming source/target node names → source_id/target_id for edges

        Args:
            nodes: List of Node objects (Pydantic models)
            edges: List of Edge objects (Pydantic models)
            include_field_remaps: If True, apply field name remapping (default True)

        Returns:
            Tuple of (nodes_data, edges_data) as list of dicts
        """
        nodes_data = []
        for n in nodes:
            node_dict = n.model_dump() if hasattr(n, "model_dump") else dict(n)
            if include_field_remaps and "grounding_id" in node_dict:
                node_dict["node_id"] = node_dict.pop("grounding_id")
            nodes_data.append(node_dict)

        edges_data = []
        for e in edges:
            edge_dict = e.model_dump() if hasattr(e, "model_dump") else dict(e)
            if include_field_remaps:
                if "source_node_english_name" in edge_dict:
                    edge_dict["source_id"] = edge_dict.pop("source_node_english_name")
                if "target_node_english_name" in edge_dict:
                    edge_dict["target_id"] = edge_dict.pop("target_node_english_name")
            edges_data.append(edge_dict)

        return nodes_data, edges_data

    def build_workflow(
        self, workflow_name: str, config: Optional[WorkflowConfig] = None
    ):
        """Build and return compiled LangGraph app.

        For advanced users who want full control over the workflow graph.
        Can stream, inspect, or customize the execution.

        Args:
            workflow_name: Name of the workflow to build
            config: Optional WorkflowConfig with overrides

        Returns:
            Compiled LangGraph app ready to invoke/stream

        Raises:
            KeyError: If workflow not found
        """
        config = config or self.global_config

        if workflow_name == "kg_extract":
            return self._build_kg_extract_workflow(config)
        elif workflow_name == "kg_extract_merge":
            return self._build_kg_extract_merge_workflow(config)
        elif workflow_name == "kg_extract_chunk_aware":
            return self._build_kg_extract_chunk_aware_workflow(config)
        elif workflow_name == "kg_extract_jsonl_batch":
            return self._build_kg_extract_jsonl_batch_workflow(config)
        elif workflow_name == "kg_ingest":
            return self._build_kg_ingest_workflow(config)
        elif workflow_name == "kg_ingest_chunk_aware":
            return self._build_kg_ingest_chunk_aware_workflow(config)
        elif workflow_name == "kg_ingest_jsonl_batch":
            return self._build_kg_ingest_jsonl_batch_workflow(config)
        elif workflow_name == "kg_load_json":
            return self._build_kg_load_json_workflow(config)
        elif workflow_name == "kg_query":
            return self._build_kg_query_workflow(config)
        elif workflow_name == "vectordb_ingest":
            return self._build_vectordb_ingest_workflow(config)
        elif workflow_name == "vectordb_visualize":
            return self._build_vectordb_visualize_workflow(config)
        elif workflow_name == "ontology_generate":
            return self._build_ontology_generate_workflow(config)
        else:
            raise KeyError(
                f"Workflow '{workflow_name}' not found. Available: kg_extract, kg_extract_merge, kg_extract_chunk_aware, kg_extract_jsonl_batch, kg_ingest, kg_ingest_chunk_aware, kg_ingest_jsonl_batch, kg_load_json, kg_query, vectordb_ingest, vectordb_visualize, ontology_generate"
            )

    def run(
        self,
        workflow_name: str,
        inputs: Union[Dict[str, Any], BaseModel],
        config_overrides: Optional[WorkflowConfig] = None,
    ) -> WorkflowResult:
        """Execute a workflow and return standardized result.

        High-level API for simple usage. Handles:
        - Building the workflow
        - Initializing state
        - Executing the graph
        - Packaging results as WorkflowResult

        Args:
            workflow_name: Name of the workflow to run
            inputs: Dictionary or Pydantic model with workflow inputs
            config_overrides: Configuration overrides for this run

        Returns:
            WorkflowResult with success status, data, stats, and errors
        """
        start_time = time.time()

        try:
            # Log workflow start
            from graphgen.v2.utils import log_workflow_start
            log_workflow_start(workflow_name)

            # 1. Merge configs hierarchically
            merged_config = self.global_config.merge_with(config_overrides)

            # 2. Get workflow definition for validation
            workflow_def = self.registry.get_workflow(workflow_name)

            # 3. Validate & coerce inputs via Pydantic schema
            if isinstance(inputs, dict):
                logger.debug(f"WorkflowManager.run: Input dict keys = {list(inputs.keys())}")
                logger.debug(f"  'vector_stores' in inputs? {'vector_stores' in inputs}, value = {inputs.get('vector_stores', 'NOT_PRESENT')}")
                validated_inputs = workflow_def.input_schema(**inputs)
                logger.debug(f"  After validation: hasattr vector_stores? {hasattr(validated_inputs, 'vector_stores')}")
                if hasattr(validated_inputs, 'vector_stores'):
                    logger.debug(f"  validated_inputs.vector_stores = {validated_inputs.vector_stores}")
            else:
                validated_inputs = inputs

            # 4. Build the workflow
            app = self.build_workflow(workflow_name, merged_config)

            # 5. Initialize state
            if workflow_name in ["kg_extract", "kg_extract_merge", "kg_extract_chunk_aware", "kg_extract_jsonl_batch", "kg_ingest", "kg_ingest_chunk_aware", "kg_ingest_jsonl_batch"]:
                file_path = getattr(validated_inputs, "file_path", None)
                input_text = getattr(validated_inputs, "input_text", None)
                ontology_path = getattr(validated_inputs, "ontology_path", None)
                input_text_preview = f"<{len(input_text)} chars>" if input_text else None
                logger.info(f"DEBUG manager.run: file_path={file_path!r}, input_text={input_text_preview!r}")
                filter_flag = getattr(validated_inputs, "filter_by_ontology", False)
                logger.debug(f"DEBUG: filter_by_ontology from validated_inputs: {filter_flag}")
                initial_state = init_kg_generation_state(
                    file_path=file_path,
                    input_text=input_text,
                    ontology_path=ontology_path,
                    max_tokens_per_segment=getattr(
                        validated_inputs, "max_tokens_per_segment", 4096
                    ),
                    filter_by_ontology=filter_flag,
                )
                state_input_text = initial_state.get('input_text')
                state_input_preview = f"<{len(state_input_text)} chars>" if state_input_text else None
                logger.info(f"DEBUG initial_state: file_path={initial_state.get('file_path')!r}, input_text={state_input_preview!r}")

                # Log full initial state for debugging
                logger.debug(f"\n{'='*80}\nINITIAL STATE (after init_kg_generation_state):\n{'='*80}")
                logger.debug(f"State keys: {list(initial_state.keys())}")
                logger.debug(f"raw_text: {repr(initial_state.get('raw_text', '')[:200])}...")
                logger.debug(f"segments: {len(initial_state.get('segments', []))} segments")
                logger.debug(f"file_path: {initial_state.get('file_path')}")
                logger.debug(f"ontology_file_path: {initial_state.get('ontology_file_path')}")
                logger.debug(f"filter_by_ontology: {initial_state.get('filter_by_ontology')}")
                logger.debug(f"max_tokens_per_segment: {initial_state.get('max_tokens_per_segment')}")
                logger.debug(f"nodes (initial): {len(initial_state.get('nodes', []))} nodes")
                logger.debug(f"edges (initial): {len(initial_state.get('edges', []))} edges")
                logger.debug(f"{'='*80}\n")

                # Pass vector_store_configs to state for dynamic retriever creation
                vector_stores = getattr(validated_inputs, "vector_stores", None)
                logger.debug(f"WorkflowManager.run: vector_stores from validated_inputs = {vector_stores}")
                if vector_stores:
                    initial_state["vector_store_configs"] = vector_stores
                    logger.info(f"{len(vector_stores)} vector store(s) configured")
                    logger.debug(f"  Set initial_state['vector_store_configs'] = {initial_state['vector_store_configs']}")
                else:
                    logger.debug(f"  No vector_stores in validated_inputs")

                # Add JSONL-specific fields for JSONL workflows
                if workflow_name in ["kg_extract_jsonl_batch", "kg_ingest_jsonl_batch"]:
                    jsonl_field_name = getattr(validated_inputs, "jsonl_field_name", "text")
                    jsonl_lines_per_batch = getattr(validated_inputs, "jsonl_lines_per_batch", 4)
                    initial_state["jsonl_field_name"] = jsonl_field_name
                    initial_state["jsonl_lines_per_batch"] = jsonl_lines_per_batch
                    logger.debug(f"Added JSONL fields: field_name='{jsonl_field_name}', lines_per_batch={jsonl_lines_per_batch}")

                # Add merge_output flag if provided (for both JSONL and regular workflows)
                merge_output = getattr(validated_inputs, "merge_output", False)
                if merge_output:
                    initial_state["merge_output"] = merge_output
                    logger.debug(f"Set merge_output={merge_output}")
            elif workflow_name == "kg_load_json":
                # Load JSON and initialize state with nodes/edges
                json_path = validated_inputs.json_path
                if not os.path.exists(json_path):
                    raise FileNotFoundError(f"JSON file not found: {json_path}")

                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Convert dict nodes/edges to Node/Edge objects
                from graphgen.v2.state import Edge, Node

                nodes_list = []
                for node_dict in data.get("nodes", []):
                    nodes_list.append(
                        Node(
                            node_name=node_dict.get(
                                "node_name",
                                node_dict.get(
                                    "name", node_dict.get("english_name", "")
                                ),
                            ),
                            node_type=node_dict.get(
                                "node_type", node_dict.get("type", "")
                            ),
                            english_name=node_dict.get("english_name", ""),
                            wikidata_id=node_dict.get("wikidata_id"),
                            node_id=node_dict.get("node_id"),
                            raw_source=node_dict.get("raw_source"),
                        )
                    )

                edges_list = []
                for edge_dict in data.get("edges", []):
                    edges_list.append(
                        Edge(
                            source_id=edge_dict.get(
                                "source_id", edge_dict.get("source_node_english_name", edge_dict.get("source", ""))
                            ),
                            target_id=edge_dict.get(
                                "target_id", edge_dict.get("target_node_english_name", edge_dict.get("target", ""))
                            ),
                            edge_type=edge_dict.get(
                                "edge_type", edge_dict.get("relationship", "")
                            ),
                            argument_role=edge_dict.get("argument_role"),
                            start_datetime=edge_dict.get("start_datetime"),
                            end_datetime=edge_dict.get("end_datetime"),
                            raw_source=edge_dict.get("raw_source"),
                        )
                    )

                # Process nodes and edges in batches
                logger.info(f"Loading {len(nodes_list)} nodes and {len(edges_list)} edges from {json_path}")
                logger.debug(f"Using batch sizes: nodes={merged_config.node_batch_size}, edges={merged_config.edge_batch_size}")

                # Split into batches
                node_batches = [
                    nodes_list[i : i + merged_config.node_batch_size]
                    for i in range(0, len(nodes_list), merged_config.node_batch_size)
                ]
                edge_batches = [
                    edges_list[i : i + merged_config.edge_batch_size]
                    for i in range(0, len(edges_list), merged_config.edge_batch_size)
                ]

                logger.info(f"Node batches: {len(node_batches)}, Edge batches: {len(edge_batches)}")

                # Process node batches sequentially
                accumulated_nodes = []
                kg_load_json_result_state = None
                for batch_idx, node_batch in enumerate(node_batches):
                    logger.info(f"Processing node batch {batch_idx + 1}/{len(node_batches)} ({len(node_batch)} nodes)")
                    initial_state = init_kg_generation_state(
                        file_path=json_path,
                        nodes=node_batch,
                        edges=[],  # No edges during node loading
                    )
                    result_state = app.invoke(initial_state)
                    accumulated_nodes.extend(result_state.get("nodes", []))
                    kg_load_json_result_state = result_state  # Track for later use

                # Process edge batches sequentially (after all nodes loaded)
                accumulated_edges = []
                for batch_idx, edge_batch in enumerate(edge_batches):
                    logger.info(f"Processing edge batch {batch_idx + 1}/{len(edge_batches)} ({len(edge_batch)} edges)")
                    initial_state = init_kg_generation_state(
                        file_path=json_path,
                        nodes=[],  # No nodes - already in Neo4j, nodes will be matched from Neo4j
                        edges=edge_batch,
                    )
                    result_state = app.invoke(initial_state)
                    accumulated_edges.extend(result_state.get("edges", []))
                    kg_load_json_result_state = (
                        result_state  # Overwrite with edge batch result
                    )

                # For result packaging, keep initial_state for other workflows
                initial_state = None
            # NOTE: kg_extract_jsonl_batch and kg_ingest_jsonl_batch are now handled in the first if block above
            # These elif blocks are kept for backwards compatibility but should not execute
            elif workflow_name == "kg_query":
                initial_state = init_kg_qa_state(validated_inputs.question)
            elif workflow_name == "vectordb_ingest":
                initial_state = init_kg_generation_state(file_path="")
                initial_state["file_paths"] = validated_inputs.file_paths
                initial_state["append"] = validated_inputs.append
                initial_state["split_docs"] = validated_inputs.split_docs
            elif workflow_name == "vectordb_visualize":
                output_dir = validated_inputs.output_dir
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                embedding_file = os.path.join(output_dir, "umap_embeddings.npy")

                initial_state = init_kg_generation_state(file_path="")
                initial_state["embedding_file_path"] = embedding_file
                initial_state["reuse_embedding_file_path"] = (
                    validated_inputs.reuse_embedding
                )
                initial_state["output_dir"] = output_dir
            elif workflow_name == "ontology_generate":
                initial_state = init_kg_generation_state(file_path="")
                initial_state["node_types"] = validated_inputs.node_types
                initial_state["edge_types"] = validated_inputs.edge_types
                initial_state["output_path"] = validated_inputs.output_path
            else:
                raise KeyError(f"Unknown workflow: {workflow_name}")

            # 6. Execute workflow
            try:
                if workflow_name == "kg_load_json":
                    # Batching already ran the full workflow for each batch
                    # Skip final invocation - use the result_state from the last batch
                    result_state = kg_load_json_result_state
                else:
                    # Non-batched workflows run full app
                    result_state = app.invoke(initial_state)
            except Exception as e:
                logger.error(f"Workflow execution error: {type(e).__name__}: {e}")
                import traceback

                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                raise

            # 7. Package results
            return self._package_result(
                workflow_name, result_state, time.time() - start_time, merged_config
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Workflow '{workflow_name}' failed: {str(e)}"
            logger.error(error_msg)

            # DEBUG: More detailed error info
            import traceback

            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            return WorkflowResult(
                success=False,
                workflow_name=workflow_name,
                execution_time_seconds=execution_time,
                errors=[error_msg],
            )

    # ============================================================================
    # WORKFLOW BUILDERS (Return compiled LangGraph apps)
    # ============================================================================

    def _extract_result_packer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Pack extracted nodes/edges to JSON file (for kg_extract_chunk_aware).

        Collects all nodes/edges from parallel segment processing and saves to JSON.
        Output file saved to same directory as input file.
        """
        import json
        import os
        from datetime import datetime

        nodes = state.get("nodes", [])
        edges = state.get("edges", [])

        # Convert to dict for JSON serialization
        nodes_data = []
        for n in nodes:
            node_dict = n.model_dump() if hasattr(n, "model_dump") else dict(n)
            nodes_data.append(node_dict)

        edges_data = []
        for e in edges:
            edge_dict = e.model_dump() if hasattr(e, "model_dump") else dict(e)
            edges_data.append(edge_dict)

        # Get input file directory to save JSON in same location
        file_path = state.get("file_path", "")
        if file_path and os.path.isfile(file_path):
            output_dir = os.path.dirname(os.path.abspath(file_path))
        else:
            output_dir = os.getcwd()

        # Save to JSON in same dir as input file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_json_path = os.path.join(output_dir, f"GraphAide_KG_Extract_{timestamp}.json")

        output_data = {
            "nodes": nodes_data,
            "edges": edges_data,
            "segments_processed": len(state.get("segments", [])),
        }

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"KG Extract Chunk-Aware saved to: {output_json_path}")

        return {
            "output_json_path": output_json_path,
            "messages": [f"✓ Results packed to: {output_json_path}"],
        }

    def _jsonl_extract_result_packer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Pack nodes/edges from JSONL extraction for JSON save.

        Called after extractmerger in kg_extract_jsonl_batch workflow.
        If merge_output=True: outputs only merged nodes/edges (deduplication).
        If merge_output=False: outputs raw nodes/edges (may have duplicates).
        """
        import os
        from datetime import datetime

        merge_output = state.get("merge_output", False)

        if merge_output:
            # Output only merged/deduplicated nodes and edges
            nodes = state.get("merged_nodes", [])
            edges = state.get("merged_edges", [])
            logger.info(f"JSONL result packer: merge_output=True, outputting {len(nodes)} merged nodes, {len(edges)} merged edges")
        else:
            # Output raw nodes (may have duplicates if same entity in multiple batches)
            nodes = state.get("nodes", [])
            edges = state.get("edges", [])
            logger.info(f"JSONL result packer: merge_output=False, outputting {len(nodes)} raw nodes (may have duplicates), {len(edges)} raw edges")

        # Get input file directory to save JSON in same location
        file_path = state.get("file_path", "")
        if file_path and os.path.isfile(file_path):
            output_dir = os.path.dirname(os.path.abspath(file_path))
        else:
            output_dir = os.getcwd()

        # Create output path in same dir as input file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_json_path = os.path.join(output_dir, f"GraphAide_KG_Extract_{timestamp}.json")

        return {
            "nodes": nodes,
            "edges": edges,
            "output_json_path": output_json_path,
            "messages": [f"✓ JSONL extraction ready for JSON save (merge={merge_output})"],
        }

    def _build_kg_extract_workflow(self, config: WorkflowConfig):
        """Build KG extraction workflow.

        Extracts nodes/edges from document segments without loading to database.
        Flow: ontologyloader → fileloader → [extractor per segment] → END

        Multi-retriever pattern: if vector_store_configs are in state, ExtractorAgent
        will query each retriever sequentially and accumulate context.
        """
        agent_factory = get_agent_factory(config)

        # Build agents
        ontology_loader = agent_factory.build(
            OntologyLoaderAgent,
            "ontologyloader",
            partials={"format_instructions": "format_instructions"},
        )
        extractor = agent_factory.build(ExtractorAgent, "extractor")

        # Create workflow
        workflow = StateGraph(KGGenerationState)
        workflow.add_node("ontologyloader", ontology_loader)
        workflow.add_node("fileloader", fileloader)
        workflow.add_node("extractor", extractor)

        # ontologyloader loads ontology types first
        workflow.add_edge(START, "ontologyloader")
        workflow.add_edge("ontologyloader", "fileloader")

        # Dispatch each segment to extractor in parallel
        workflow.add_conditional_edges(
            "fileloader",
            make_segment_dispatcher("extractor"),
            ["extractor"],
        )

        workflow.add_edge("extractor", END)

        return workflow.compile()

    def _build_kg_extract_merge_workflow(self, config: WorkflowConfig):
        """Build KG extraction + merging workflow.

        Extracts nodes/edges and consolidates duplicates by node_id.
        Flow: ontologyloader → fileloader → [extractor per segment] → extractmerger → END
        """
        agent_factory = get_agent_factory(config)

        # Build agents
        ontology_loader = agent_factory.build(
            OntologyLoaderAgent,
            "ontologyloader",
            partials={"format_instructions": "format_instructions"},
        )
        extractor = agent_factory.build(ExtractorAgent, "extractor")
        extract_merger = agent_factory.build(ExtractMergerAgent, "extractmerger")

        # Create workflow
        workflow = StateGraph(KGGenerationState)
        workflow.add_node("ontologyloader", ontology_loader)
        workflow.add_node("fileloader", fileloader)
        workflow.add_node("extractor", extractor)
        workflow.add_node("extractmerger", extract_merger)

        # ontologyloader loads ontology types first
        workflow.add_edge(START, "ontologyloader")
        workflow.add_edge("ontologyloader", "fileloader")

        # Dispatch each segment to extractor in parallel
        workflow.add_conditional_edges(
            "fileloader",
            make_segment_dispatcher("extractor"),
            ["extractor"],
        )

        # After extraction, merge nodes and edges
        workflow.add_edge("extractor", "extractmerger")
        workflow.add_edge("extractmerger", END)

        return workflow.compile()

    def _build_kg_extract_chunk_aware_workflow(self, config: WorkflowConfig):
        """Build chunk-aware KG extraction workflow with provenance tracking.

        Extracts nodes/edges with chunk tracking (SourceDocument/ChunkParagraph metadata).
        Does NOT load to database—saves results to JSON file only.
        Flow: ontologyloader → fileloader → [chunktracker per segment] → result_packer → END
        """
        agent_factory = get_agent_factory(config)

        # Build agents
        ontology_loader = agent_factory.build(
            OntologyLoaderAgent,
            "ontologyloader",
            partials={"format_instructions": "format_instructions"},
        )
        extractor = agent_factory.build(ExtractorAgent, "extractor")
        chunk_tracker = ChunkTrackerAgent(wrapped_extractor=extractor)

        # Create workflow
        workflow = StateGraph(KGGenerationState)
        workflow.add_node("ontologyloader", ontology_loader)
        workflow.add_node("fileloader", fileloader)
        workflow.add_node("chunktracker", chunk_tracker)
        workflow.add_node("result_packer", self._extract_result_packer)

        # Sequential: ontologyloader → fileloader
        workflow.add_edge(START, "ontologyloader")
        workflow.add_edge("ontologyloader", "fileloader")

        # Dispatch each segment to chunktracker in parallel
        workflow.add_conditional_edges(
            "fileloader",
            make_segment_dispatcher("chunktracker"),
            ["chunktracker"],
        )

        # After all segments processed, pack results to JSON
        workflow.add_edge("chunktracker", "result_packer")
        workflow.add_edge("result_packer", END)

        return workflow.compile()

    def _build_kg_ingest_workflow(self, config: WorkflowConfig):
        """Build KG ingestion workflow with parallel execution.

        Extracts nodes/edges and loads them into Neo4j with:
        - Parallel node/edge loading
        - Conditional routing via Send()
        - Retry policies
        - Subgraph composition
        """
        agent_factory = get_agent_factory(config)

        # Build the KG loader subgraph (parallel extraction + loading)
        kg_loader_subgraph = self._build_kg_loader_subgraph(agent_factory)

        # Retry policy for robustness
        retry_policy = RetryPolicy(
            initial_interval=1.0,
            backoff_factor=2.0,
            max_interval=60.0,
            max_attempts=config.retry_max_attempts,
            jitter=True,
        )

        # Build ontology loader
        ontology_loader = agent_factory.build(
            OntologyLoaderAgent,
            "ontologyloader",
            partials={"format_instructions": "format_instructions"},
        )

        # Main workflow
        workflow = StateGraph(KGGenerationState)

        # Add nodes
        workflow.add_node("ontologyloader", ontology_loader)
        workflow.add_node("fileloader", fileloader, retry_policy=retry_policy)
        workflow.add_node(
            "knowledgegraphloader", kg_loader_subgraph, retry_policy=retry_policy
        )

        # Define sequence with conditional routing
        workflow.add_edge(START, "ontologyloader")
        workflow.add_edge("ontologyloader", "fileloader")

        # Conditional edge: dispatch segments to KG loader in parallel
        workflow.add_conditional_edges(
            "fileloader",
            make_segment_dispatcher("knowledgegraphloader"),
            ["knowledgegraphloader"],
        )

        workflow.add_edge("knowledgegraphloader", END)

        return workflow.compile()

    def _build_kg_ingest_chunk_aware_workflow(self, config: WorkflowConfig):
        """Build chunk-aware KG ingestion workflow with provenance tracking.

        Extracts nodes/edges with chunk tracking and loads directly to Neo4j.
        Creates SourceDocument and ChunkParagraph nodes for entity provenance.
        Flow: ontologyloader → fileloader → [chunktracker per segment] → chunk-aware loader subgraph → END
        """
        agent_factory = get_agent_factory(config)

        # Build ontology loader
        ontology_loader = agent_factory.build(
            OntologyLoaderAgent,
            "ontologyloader",
            partials={"format_instructions": "format_instructions"},
        )

        # Build chunk-aware loader subgraph
        chunk_aware_loader_subgraph = self._build_chunk_aware_loader_subgraph(agent_factory)

        # Retry policy for robustness
        retry_policy = RetryPolicy(
            initial_interval=1.0,
            backoff_factor=2.0,
            max_interval=60.0,
            max_attempts=config.retry_max_attempts,
            jitter=True,
        )

        # Main workflow
        workflow = StateGraph(KGGenerationState)

        # Add nodes
        workflow.add_node("ontologyloader", ontology_loader)
        workflow.add_node("fileloader", fileloader, retry_policy=retry_policy)
        workflow.add_node(
            "chunk_aware_loader", chunk_aware_loader_subgraph, retry_policy=retry_policy
        )

        # Define sequence with conditional routing
        workflow.add_edge(START, "ontologyloader")
        workflow.add_edge("ontologyloader", "fileloader")

        # Conditional edge: dispatch segments to chunk-aware loader in parallel
        workflow.add_conditional_edges(
            "fileloader",
            make_segment_dispatcher("chunk_aware_loader"),
            ["chunk_aware_loader"],
        )

        workflow.add_edge("chunk_aware_loader", END)

        return workflow.compile()

    def _build_kg_ingest_jsonl_batch_workflow(self, config: WorkflowConfig):
        """Build JSONL batch ingestion workflow with parallel extraction.

        Reads JSONL batch (prepared by Python caller), dispatches lines to
        parallel extractors, then loads to Neo4j.
        Flow: jsonlloader → jsonl_segment_dispatcher → [parallel extractors]
              → extract_merger → kg_loader_subgraph → END
        """
        agent_factory = get_agent_factory(config)

        # Build JSONL loader
        jsonl_loader = agent_factory.build(
            JSONLLoaderAgent,
            "jsonlloader",
        )

        # Build KG loader subgraph (parallel extraction + loading)
        kg_loader_subgraph = self._build_kg_loader_subgraph(agent_factory)

        # Retry policy for robustness
        retry_policy = RetryPolicy(
            initial_interval=1.0,
            backoff_factor=2.0,
            max_interval=60.0,
            max_attempts=config.retry_max_attempts,
            jitter=True,
        )

        # Main workflow
        workflow = StateGraph(KGGenerationState)

        # Add nodes
        workflow.add_node("jsonlloader", jsonl_loader, retry_policy=retry_policy)
        workflow.add_node("extractor", agent_factory.build(ExtractorAgent, "extractor"), retry_policy=retry_policy)
        workflow.add_node(
            "knowledgegraphloader", kg_loader_subgraph, retry_policy=retry_policy
        )

        # Define sequence with conditional routing
        workflow.add_edge(START, "jsonlloader")

        # Conditional edge: dispatch JSONL lines to extractors in parallel
        workflow.add_conditional_edges(
            "jsonlloader",
            jsonl_segment_dispatcher,
            ["extractor"],
        )

        workflow.add_edge("extractor", "knowledgegraphloader")
        workflow.add_edge("knowledgegraphloader", END)

        logger.info("✅ kg_ingest_jsonl_batch workflow compiled")
        return workflow.compile()

    def _build_kg_extract_jsonl_batch_workflow(self, config: WorkflowConfig):
        """Build JSONL batch extraction workflow with parallel processing.

        Reads JSONL batch (prepared by Python caller), dispatches lines to
        parallel extractors, merges results, and returns extracted nodes/edges.
        Flow: ontologyloader → jsonlloader → jsonl_segment_dispatcher → [parallel extractors]
              → extract_merger → result_packer → END

        Similar to kg_ingest_jsonl_batch but WITHOUT Neo4j loading.
        """
        agent_factory = get_agent_factory(config)

        # Build ontology loader (same as regular extraction)
        ontology_loader = agent_factory.build(
            OntologyLoaderAgent,
            "ontologyloader",
            partials={"format_instructions": "format_instructions"},
        )

        # Build JSONL loader
        jsonl_loader = agent_factory.build(
            JSONLLoaderAgent,
            "jsonlloader",
        )

        # Build extractor and merger
        extractor = agent_factory.build(ExtractorAgent, "extractor")
        extract_merger = agent_factory.build(ExtractMergerAgent, "extractmerger")

        # Retry policy for robustness
        retry_policy = RetryPolicy(
            initial_interval=1.0,
            backoff_factor=2.0,
            max_interval=60.0,
            max_attempts=config.retry_max_attempts,
            jitter=True,
        )

        # Main workflow
        workflow = StateGraph(KGGenerationState)

        # Add nodes
        workflow.add_node("ontologyloader", ontology_loader, retry_policy=retry_policy)
        workflow.add_node("jsonlloader", jsonl_loader, retry_policy=retry_policy)
        workflow.add_node("extractor", extractor, retry_policy=retry_policy)
        workflow.add_node("extractmerger", extract_merger, retry_policy=retry_policy)
        workflow.add_node("result_packer", self._jsonl_extract_result_packer)

        # Define sequence with conditional routing
        workflow.add_edge(START, "ontologyloader")
        workflow.add_edge("ontologyloader", "jsonlloader")

        # Conditional edge: dispatch JSONL lines to extractors in parallel
        workflow.add_conditional_edges(
            "jsonlloader",
            jsonl_segment_dispatcher,
            ["extractor"],
        )

        workflow.add_edge("extractor", "extractmerger")
        workflow.add_edge("extractmerger", "result_packer")
        workflow.add_edge("result_packer", END)

        logger.info("✅ kg_extract_jsonl_batch workflow compiled")
        return workflow.compile()

    def _build_kg_load_json_workflow(self, config: WorkflowConfig):
        """Build KG loading workflow from pre-extracted JSON.

        Takes JSON from kg_extract output and loads into Neo4j with postprocessing:
        - NodesLoader → Create nodes
        - EdgesLoader → Create edges
        - Neo4jPostProcessor → Convert edge types and add labels

        Does NOT include extraction since JSON already has nodes/edges.
        """
        agent_factory = get_agent_factory(config)

        # Build simplified loader subgraph (no extraction needed)
        loader_subgraph = self._build_kg_json_loader_subgraph(agent_factory)

        # Create a simple workflow: JSON nodes/edges → loader subgraph
        workflow = StateGraph(KGGenerationState)
        workflow.add_node("knowledgegraphloader", loader_subgraph)
        workflow.add_edge(START, "knowledgegraphloader")
        workflow.add_edge("knowledgegraphloader", END)

        return workflow.compile()

    def _build_chunk_aware_loader_subgraph(self, agent_factory):
        """Build chunk-aware KG loader subgraph with chunk provenance tracking.

        Flow: chunktracker → chunkgraphload → nodes4edgesloader → [nodesloader, edgesloader] → postprocessor
        """
        # Build agents
        extractor = agent_factory.build(ExtractorAgent, "extractor")
        chunk_tracker = ChunkTrackerAgent(wrapped_extractor=extractor)
        chunk_graph_load = agent_factory.build(ChunkGraphLoadAgent, "chunkgraphload")
        nodes_loader = agent_factory.build(NodesLoaderAgent, "nodesloader")
        edges_loader = agent_factory.build(EdgesLoaderAgent, "edgesloader")
        nodes4edges_loader = agent_factory.build(
            Nodes4EdgesLoaderAgent, "nodes4edgesloader"
        )
        neo4j_postprocessor = agent_factory.build(
            Neo4jPostProcessorAgent, "neo4jpostprocessor"
        )

        # Create subgraph
        workflow = StateGraph(KGGenerationState)

        # Add nodes
        workflow.add_node("chunktracker", chunk_tracker)
        workflow.add_node("chunkgraphload", chunk_graph_load)
        workflow.add_node("nodes4edgesloader", nodes4edges_loader)
        workflow.add_node("nodesloader", nodes_loader)
        workflow.add_node("edgesloader", edges_loader)
        workflow.add_node("neo4jpostprocessor", neo4j_postprocessor)

        # Sequential: chunk tracker → chunk graph load
        workflow.add_edge(START, "chunktracker")
        workflow.add_edge("chunktracker", "chunkgraphload")

        # Sequential: chunkgraphload → nodes4edgesloader (validate edge->node references)
        workflow.add_edge("chunkgraphload", "nodes4edgesloader")

        # Parallel execution: Send to both loaders after nodes4edges → post-process
        self._add_parallel_loaders(workflow, "nodes4edgesloader", ["nodesloader", "edgesloader"], "neo4jpostprocessor")

        workflow.add_edge("neo4jpostprocessor", END)

        return workflow.compile()

    def _build_kg_loader_subgraph(self, agent_factory):
        """Build KG loader subgraph with parallel node/edge loading.

        Flow: extractor → nodes4edgesloader → [nodesloader, edgesloader] → postprocessor
        """
        # Build agents
        extractor = agent_factory.build(ExtractorAgent, "extractor")
        nodes_loader = agent_factory.build(NodesLoaderAgent, "nodesloader")
        edges_loader = agent_factory.build(EdgesLoaderAgent, "edgesloader")
        nodes4edges_loader = agent_factory.build(
            Nodes4EdgesLoaderAgent, "nodes4edgesloader"
        )
        neo4j_postprocessor = agent_factory.build(
            Neo4jPostProcessorAgent, "neo4jpostprocessor"
        )

        # Create subgraph
        workflow = StateGraph(KGGenerationState)

        # Add nodes (removed redundant neo4jloader)
        workflow.add_node("extractor", extractor)
        workflow.add_node("nodes4edgesloader", nodes4edges_loader)
        workflow.add_node("nodesloader", nodes_loader)
        workflow.add_node("edgesloader", edges_loader)
        workflow.add_node("neo4jpostprocessor", neo4j_postprocessor)

        # Sequential: extract → nodes4edges (prepare nodes for edges)
        workflow.add_edge(START, "extractor")
        workflow.add_edge("extractor", "nodes4edgesloader")

        # Parallel execution: Send to both loaders after nodes4edges → post-process
        self._add_parallel_loaders(workflow, "nodes4edgesloader", ["nodesloader", "edgesloader"], "neo4jpostprocessor")

        workflow.add_edge("neo4jpostprocessor", END)

        return workflow.compile()

    def _build_kg_json_loader_subgraph(self, agent_factory):
        """Build simplified KG loader subgraph for pre-extracted JSON.

        For kg_load_json workflow: loads pre-extracted nodes/edges without extraction.
        Sequential processing avoids complexity and state duplication issues.

        Flow: nodesloader → edgesloader → neo4jpostprocessor → END

        NOTE: Nodes4EdgesLoaderAgent removed from workflow (see TODO.md).
              Bring back later when edge source/target node creation is needed.
        """
        # Build agents (no extractor needed, JSON already has nodes/edges)
        nodes_loader = agent_factory.build(NodesLoaderAgent, "nodesloader")
        edges_loader = agent_factory.build(EdgesLoaderAgent, "edgesloader")
        neo4j_postprocessor = agent_factory.build(
            Neo4jPostProcessorAgent, "neo4jpostprocessor"
        )

        # Create subgraph
        workflow = StateGraph(KGGenerationState)

        # Add nodes
        workflow.add_node("nodesloader", nodes_loader)
        workflow.add_node("edgesloader", edges_loader)
        workflow.add_node("neo4jpostprocessor", neo4j_postprocessor)

        # Sequential flow (no batching, no parallelization)
        # Load all nodes first, then load edges
        workflow.add_edge(START, "nodesloader")
        workflow.add_edge("nodesloader", "edgesloader")
        workflow.add_edge("edgesloader", "neo4jpostprocessor")
        workflow.add_edge("neo4jpostprocessor", END)

        return workflow.compile()

    def _build_kg_query_workflow(self, config: WorkflowConfig):
        """Build KG query workflow with parallel vector retrieval and graph query.

        Queries knowledge graph with natural language questions.
        Flow: intent prediction → parallel (vector retrieval + Cypher generation/execution)
        """
        agent_factory = get_agent_factory(config)

        # Build agents
        intent_predictor = agent_factory.build(IntentPredictorAgent, "intentpredictor")
        rag_agent = agent_factory.build(SimpleRAGAgent, "simplerag")
        graph_generator = agent_factory.build(
            QuestionGraphGeneratorAgent, "questiongraphgenerator"
        )
        query_runner = agent_factory.build(Neo4jQueryRunnerAgent, "neo4jqueryrunner")

        # Create workflow
        workflow = StateGraph(KGQuestionAnswerState)

        # Add nodes
        workflow.add_node("intentpredictor", intent_predictor)
        workflow.add_node("simplerag", rag_agent)
        workflow.add_node("questiongraphgenerator", graph_generator)
        workflow.add_node("neo4jqueryrunner", query_runner)

        # Sequential: predict intent first
        workflow.add_edge(START, "intentpredictor")

        # Parallel: SimpleRAG (vector retrieval + answer) + Graph query pipeline
        workflow.add_conditional_edges(
            "intentpredictor",
            lambda state: [
                Send("simplerag", state),
                Send("questiongraphgenerator", state),
            ],
            ["simplerag", "questiongraphgenerator"],
        )

        # Both branches merge and end
        workflow.add_edge("simplerag", END)
        workflow.add_edge("questiongraphgenerator", "neo4jqueryrunner")
        workflow.add_edge("neo4jqueryrunner", END)

        return workflow.compile()

    def _build_vectordb_ingest_workflow(self, config: WorkflowConfig):
        """Build vector store ingestion workflow.

        Loads documents into vector store using VectorDBLoaderAgent.
        Flow: vectordbloader → END
        """
        agent_factory = get_agent_factory(config)

        # Build agent
        vectordb_loader = agent_factory.build(VectorDBLoaderAgent, "vectordbloader")

        # Create workflow
        workflow = StateGraph(KGGenerationState)
        workflow.add_node("vectordbloader", vectordb_loader)
        workflow.add_edge(START, "vectordbloader")
        workflow.add_edge("vectordbloader", END)

        return workflow.compile()

    def _build_vectordb_visualize_workflow(self, config: WorkflowConfig):
        """Build vector store visualization workflow.

        Projects embeddings to 2D and creates visualization.
        Flow: embeddingprojector → embeddingvisualizer → END
        """
        agent_factory = get_agent_factory(config)

        # Build agents
        embedding_projector = agent_factory.build(
            EmbeddingProjectorAgent, "embeddingprojector"
        )
        embedding_visualizer = agent_factory.build(
            EmbeddingVisualizerAgent, "embeddingvisualizer"
        )

        # Create workflow
        workflow = StateGraph(KGGenerationState)
        workflow.add_node("embeddingprojector", embedding_projector)
        workflow.add_node("embeddingvisualizer", embedding_visualizer)

        workflow.add_edge(START, "embeddingprojector")
        workflow.add_edge("embeddingprojector", "embeddingvisualizer")
        workflow.add_edge("embeddingvisualizer", END)

        return workflow.compile()

    def _build_ontology_generate_workflow(self, config: WorkflowConfig):
        """Build ontology generation workflow.

        Generates N-Triple format RDF ontology from node and edge type lists.
        Flow: ontologygenerator → END
        """
        # Ontology generation doesn't need LLM or databases, so just create agent directly

        ontology_generator = OntologyGeneratorAgent(
            model=None, template_str="", settings={}
        )

        # Create workflow
        workflow = StateGraph(KGGenerationState)
        workflow.add_node("ontologygenerator", ontology_generator)

        workflow.add_edge(START, "ontologygenerator")
        workflow.add_edge("ontologygenerator", END)

        return workflow.compile()

    # ============================================================================
    # RESULT PACKAGING
    # ============================================================================

    def _package_result(
        self,
        workflow_name: str,
        result_state: Dict[str, Any],
        execution_time: float,
        config: WorkflowConfig,
    ) -> WorkflowResult:
        """Package workflow result state as WorkflowResult.

        Args:
            workflow_name: Name of the workflow
            result_state: Final state dict from LangGraph execution
            execution_time: Execution time in seconds
            config: Merged workflow configuration

        Returns:
            WorkflowResult with formatted data
        """
        if workflow_name in ["kg_extract", "kg_extract_chunk_aware", "kg_extract_merge", "kg_extract_jsonl_batch", "kg_ingest", "kg_ingest_chunk_aware", "kg_ingest_jsonl_batch"]:
            nodes = result_state.get("nodes", [])
            edges = result_state.get("edges", [])
            messages = result_state.get("messages", [])

            if workflow_name == "kg_extract":
                stats = {
                    "segments_processed": len(result_state.get("segments", [])),
                    "nodes_extracted": len(nodes),
                    "edges_extracted": len(edges),
                }

                # Save nodes/edges to JSON file
                output_json_path = result_state.get("output_json_path")
                if not output_json_path:
                    # Create output path in same dir as input file if not already set
                    from datetime import datetime
                    file_path = result_state.get("file_path", "")
                    if file_path and os.path.isfile(file_path):
                        output_dir = os.path.dirname(os.path.abspath(file_path))
                    else:
                        output_dir = os.getcwd()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_json_path = os.path.join(output_dir, f"GraphAide_KG_Extract_{timestamp}.json")

                if output_json_path:
                    try:
                        # Convert Pydantic models to dicts with field remapping
                        nodes_data, edges_data = self._serialize_graph_data(nodes, edges)

                        # Check if filtering was applied by looking for filter metadata in result_state
                        filter_stats = result_state.get("filter_stats", {})
                        has_filtering = filter_stats.get("filtered_nodes", 0) > 0 or filter_stats.get("filtered_edges", 0) > 0

                        file_path = result_state.get("file_path", "")
                        output_data = {
                            "source_file": os.path.basename(file_path),
                            "file_path": file_path,
                            "ontology_file_path": result_state.get(
                                "ontology_file_path"
                            ),
                            "segments_processed": stats["segments_processed"],
                            "filtering_applied": has_filtering,
                            "filter_stats": filter_stats if has_filtering else None,
                            "nodes": nodes_data,
                            "edges": edges_data,
                        }

                        # Add prefix "Filtered_" if filtering was applied
                        if has_filtering:
                            output_json_path = output_json_path.replace(
                                "GraphAide_KG_Extract_", "GraphAide_KG_Extract_Filtered_"
                            )
                            filtered_count = filter_stats.get("filtered_nodes", 0) + filter_stats.get("filtered_edges", 0)
                            logger.debug(f"Extractor: filtered {filter_stats.get('filtered_nodes', 0)} nodes, {filter_stats.get('filtered_edges', 0)} edges")

                        with open(output_json_path, "w", encoding="utf-8") as f:
                            json.dump(output_data, f, indent=2, ensure_ascii=False)
                        logger.info(f"KG Extract saved to: {output_json_path}")
                        stats["output_json_path"] = output_json_path
                    except Exception as e:
                        logger.error(f"Failed to save JSON output: {e}")
                        stats["output_json_error"] = str(e)

                return WorkflowResult(
                    success=True,
                    workflow_name=workflow_name,
                    execution_time_seconds=execution_time,
                    nodes=nodes,
                    edges=edges,
                    stats=stats,
                    messages=messages,
                )

            elif workflow_name == "kg_extract_chunk_aware":
                stats = {
                    "segments_processed": len(result_state.get("segments", [])),
                    "nodes_extracted": len(nodes),
                    "edges_extracted": len(edges),
                    "chunks_tracked": len(result_state.get("chunk_paragraphs", [])),
                }

                # Save nodes/edges to JSON file (same format as kg_extract)
                output_json_path = result_state.get("output_json_path")
                if output_json_path:
                    try:
                        # Convert Pydantic models to dicts (no field remapping for chunk_aware)
                        nodes_data, edges_data = self._serialize_graph_data(nodes, edges, include_field_remaps=False)

                        file_path = result_state.get("file_path", "")
                        output_data = {
                            "source_file": os.path.basename(file_path),
                            "file_path": file_path,
                            "ontology_file_path": result_state.get(
                                "ontology_file_path"
                            ),
                            "segments_processed": stats["segments_processed"],
                            "chunks_tracked": stats["chunks_tracked"],
                            "nodes": nodes_data,
                            "edges": edges_data,
                        }

                        with open(output_json_path, "w", encoding="utf-8") as f:
                            json.dump(output_data, f, indent=2, ensure_ascii=False)
                        logger.info(f"KG Extract Chunk-Aware saved to: {output_json_path}")
                        stats["output_json_path"] = output_json_path
                    except Exception as e:
                        logger.error(f"Failed to save JSON output: {e}")
                        stats["output_json_error"] = str(e)

                return WorkflowResult(
                    success=True,
                    workflow_name=workflow_name,
                    execution_time_seconds=execution_time,
                    nodes=nodes,
                    edges=edges,
                    stats=stats,
                    messages=messages,
                )

            elif workflow_name == "kg_extract_jsonl_batch":
                # Same as kg_extract - JSONL just has parallel processing
                stats = {
                    "nodes_extracted": len(nodes),
                    "edges_extracted": len(edges),
                }

                # Save nodes/edges to JSON file (same format as kg_extract)
                output_json_path = result_state.get("output_json_path")
                if output_json_path:
                    try:
                        # Convert Pydantic models to dicts with field remapping
                        nodes_data, edges_data = self._serialize_graph_data(nodes, edges)

                        file_path = result_state.get("file_path", "")
                        output_data = {
                            "source_file": os.path.basename(file_path),
                            "file_path": file_path,
                            "ontology_file_path": result_state.get("ontology_path"),
                            "segments_processed": stats["nodes_extracted"],
                            "nodes": nodes_data,
                            "edges": edges_data,
                        }

                        # Check if filtering was applied by looking for filter metadata in result_state
                        filter_stats = result_state.get("filter_stats", {})
                        has_filtering = any([
                            result_state.get("filter_by_ontology", False),
                            filter_stats.get("filtered_nodes", 0) > 0,
                            filter_stats.get("filtered_edges", 0) > 0,
                        ])

                        # Add prefix "Filtered_" if filtering was applied
                        if has_filtering:
                            output_json_path = output_json_path.replace(
                                "GraphAide_KG_Extract_", "GraphAide_KG_Extract_Filtered_"
                            )
                            filtered_count = filter_stats.get("filtered_nodes", 0) + filter_stats.get("filtered_edges", 0)
                            logger.debug(f"JSONL Extractor: filtered {filter_stats.get('filtered_nodes', 0)} nodes, {filter_stats.get('filtered_edges', 0)} edges")

                        with open(output_json_path, "w", encoding="utf-8") as f:
                            json.dump(output_data, f, indent=2, ensure_ascii=False)
                        logger.info(f"KG Extract JSONL saved to: {output_json_path}")
                        stats["output_json_path"] = output_json_path
                    except Exception as e:
                        logger.error(f"Failed to save JSON output: {e}")
                        stats["output_json_error"] = str(e)

                return WorkflowResult(
                    success=True,
                    workflow_name=workflow_name,
                    execution_time_seconds=execution_time,
                    nodes=nodes,
                    edges=edges,
                    stats=stats,
                    messages=messages,
                )

            elif workflow_name == "kg_extract_merge":
                merged_nodes = result_state.get("merged_nodes", [])
                merged_edges = result_state.get("merged_edges", [])
                stats = {
                    "segments_processed": len(result_state.get("segments", [])),
                    "nodes_merged": len(merged_nodes),
                    "edges_merged": len(merged_edges),
                }

                # Save nodes/edges to JSON file with "Merged" in filename
                output_json_path = result_state.get("output_json_path")
                if not output_json_path:
                    # Create output path in same dir as input file if not already set
                    from datetime import datetime
                    file_path = result_state.get("file_path", "")
                    if file_path and os.path.isfile(file_path):
                        output_dir = os.path.dirname(os.path.abspath(file_path))
                    else:
                        output_dir = os.getcwd()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_json_path = os.path.join(output_dir, f"GraphAide_KG_Extract_{timestamp}.json")

                if output_json_path:
                    try:
                        # Insert "Merged" into filename
                        output_json_path = output_json_path.replace(
                            "GraphAide_KG_Extract_", "GraphAide_KG_Extract_Merged_"
                        )
                        # Convert Pydantic models to dicts with field remapping
                        merged_nodes_data, merged_edges_data = self._serialize_graph_data(merged_nodes, merged_edges)

                        file_path = result_state.get("file_path", "")
                        output_data = {
                            "source_file": os.path.basename(file_path),
                            "file_path": file_path,
                            "ontology_file_path": result_state.get(
                                "ontology_file_path"
                            ),
                            "segments_processed": stats["segments_processed"],
                            "nodes": merged_nodes_data,
                            "edges": merged_edges_data,
                        }
                        with open(output_json_path, "w", encoding="utf-8") as f:
                            json.dump(output_data, f, indent=2, ensure_ascii=False)
                        logger.info(f"KG Extract Merged saved to: {output_json_path}")
                        stats["output_json_path"] = output_json_path
                    except Exception as e:
                        logger.error(f"Failed to save merged JSON output: {e}")
                        stats["output_json_error"] = str(e)

                return WorkflowResult(
                    success=True,
                    workflow_name=workflow_name,
                    execution_time_seconds=execution_time,
                    data={
                        "nodes": merged_nodes,
                        "edges": merged_edges,
                    },
                    stats=stats,
                    messages=messages,
                )

            elif workflow_name == "kg_ingest_chunk_aware":
                stats = {
                    "segments_processed": len(result_state.get("segments", [])),
                    "nodes_created": len(nodes),
                    "edges_created": len(edges),
                    "chunks_tracked": len(result_state.get("chunk_paragraphs", [])),
                }

                return WorkflowResult(
                    success=True,
                    workflow_name=workflow_name,
                    execution_time_seconds=execution_time,
                    stats=stats,
                    messages=messages,
                )

            else:  # kg_ingest
                stats = {
                    "segments_processed": len(result_state.get("segments", [])),
                    "nodes_created": len(nodes),
                    "edges_created": len(edges),
                }

                return WorkflowResult(
                    success=True,
                    workflow_name=workflow_name,
                    execution_time_seconds=execution_time,
                    stats=stats,
                    messages=messages,
                )

        elif workflow_name == "kg_query":
            return WorkflowResult(
                success=True,
                workflow_name=workflow_name,
                execution_time_seconds=execution_time,
                answer=result_state.get("answer"),
                nodes=result_state.get("related_nodes", []),
                edges=result_state.get("related_edges", []),
                data={
                    "question": result_state.get("question"),
                    "graph_question": result_state.get("graph_question"),
                    "graph_answer": result_state.get("graph_answer"),
                    "graph_answer_text": result_state.get("graph_answer_text"),
                },
                stats={
                    "related_nodes": len(result_state.get("related_nodes", [])),
                    "related_edges": len(result_state.get("related_edges", [])),
                    "is_answered": result_state.get("is_answered", False),
                },
                messages=result_state.get("messages", []),
            )

        elif workflow_name == "vectordb_ingest":
            stats = result_state.get("agent_status", {}).get("vectordbloader", {})
            # Get actual store name from config or env var
            actual_store_name = os.getenv("VECTOR_STORE_NAME", "GA_VDB")

            return WorkflowResult(
                success=True,
                workflow_name=workflow_name,
                execution_time_seconds=execution_time,
                stats={
                    "documents_loaded": stats.get("documents_loaded", 0),
                    "chunks_created": stats.get("chunks_created", 0),
                    "vector_store_name": stats.get(
                        "vector_store_name", actual_store_name
                    ),
                    "vector_store_path": stats.get("vector_store_path", "./chroma"),
                },
                messages=result_state.get("messages", []),
            )

        elif workflow_name == "vectordb_visualize":
            stats = result_state.get("agent_status", {})
            return WorkflowResult(
                success=True,
                workflow_name=workflow_name,
                execution_time_seconds=execution_time,
                stats={
                    "projection_file_path": result_state.get("embedding_file_path", ""),
                    "num_embeddings_projected": len(result_state.get("nodes", [])),
                },
                data={
                    "projection_file_path": result_state.get("embedding_file_path"),
                    "visualization_image_path": stats.get(
                        "embeddingvisualizer", {}
                    ).get("visualization_path", ""),
                    "projection_metadata_path": result_state.get(
                        "embedding_file_path", ""
                    )
                    + ".metadata.json",
                },
                messages=result_state.get("messages", []),
            )

        elif workflow_name == "kg_load_json":
            nodes = result_state.get("nodes", [])
            edges = result_state.get("edges", [])
            messages = result_state.get("messages", [])

            # Query Neo4j for actual total counts after workflow
            total_nodes = 0
            total_edges = 0
            if config and config.graphdb_config:
                try:
                    from graphgen.v2.GraphDBManager import GraphDBFactory

                    graph_store = GraphDBFactory.create(config.graphdb_config)
                    nodes_result = graph_store.query(
                        "MATCH (n) RETURN COUNT(n) as count"
                    )
                    total_nodes = nodes_result[0]["count"] if nodes_result else 0
                    edges_result = graph_store.query(
                        "MATCH ()-[r:REL]->() RETURN COUNT(r) as count"
                    )
                    total_edges = edges_result[0]["count"] if edges_result else 0
                except Exception as e:
                    logger.error(f"Failed to query node/edge counts from Neo4j: {e}")

            stats = {
                "nodes_created": total_nodes,
                "edges_created": total_edges,
            }

            return WorkflowResult(
                success=True,
                workflow_name=workflow_name,
                execution_time_seconds=execution_time,
                nodes=nodes,
                edges=edges,
                stats=stats,
                messages=messages,
            )

        elif workflow_name == "ontology_generate":
            ontology_file_path = result_state.get("ontology_file_path")
            messages = result_state.get("messages", [])

            # Get counts from state if available
            node_types_count = len(result_state.get("node_types", []))
            edge_types_count = len(result_state.get("edge_types", []))

            return WorkflowResult(
                success=True if ontology_file_path else False,
                workflow_name=workflow_name,
                execution_time_seconds=execution_time,
                stats={
                    "ontology_file_path": ontology_file_path,
                    "node_types_count": node_types_count,
                    "edge_types_count": edge_types_count,
                },
                data={
                    "ontology_file_path": ontology_file_path,
                },
                messages=messages,
            )

        else:
            raise ValueError(f"Unknown workflow: {workflow_name}")

    # ============================================================================
    # REGISTRY & DISCOVERY
    # ============================================================================

    def register_custom_workflow(
        self,
        name: str,
        workflow_fn: Callable[[Dict[str, Any], WorkflowConfig], WorkflowResult],
        input_schema: Type[BaseModel],
        output_schema: Type[BaseModel],
        description: str,
    ) -> None:
        """Register a custom workflow.

        For advanced users who want to add their own workflows.

        Args:
            name: Unique workflow name
            workflow_fn: Function to execute (not used for built-in workflows)
            input_schema: Pydantic model for input validation
            output_schema: Pydantic model for output structure
            description: Human-readable description

        Raises:
            ValueError: If workflow name already registered
        """
        self.registry.register(
            name=name,
            workflow_fn=workflow_fn,
            input_schema=input_schema,
            output_schema=output_schema,
            description=description,
        )

    def list_workflows(self) -> list:
        """List all registered workflows.

        Returns:
            List of WorkflowInfo objects with metadata
        """
        workflows = self.registry.list_workflows()
        return [
            WorkflowInfo(
                name=wf.name,
                description=wf.description,
                input_schema=wf.input_schema,
                output_schema=wf.output_schema,
            )
            for wf in workflows.values()
        ]

    def get_workflow_info(self, workflow_name: str) -> WorkflowInfo:
        """Get metadata and schema info for a workflow.

        Args:
            workflow_name: Name of workflow

        Returns:
            WorkflowInfo with input/output schemas and description

        Raises:
            KeyError: If workflow not found
        """
        wf = self.registry.get_workflow(workflow_name)
        return WorkflowInfo(
            name=wf.name,
            description=wf.description,
            input_schema=wf.input_schema,
            output_schema=wf.output_schema,
        )

    def _register_builtin_workflows(self) -> None:
        """Register all built-in workflows with dummy functions.

        The actual execution happens in build_workflow() which returns
        compiled LangGraph apps.
        """

        def dummy_workflow_fn(inputs, config):
            """Dummy function - actual execution via build_workflow()."""
            raise NotImplementedError("Use build_workflow() to get compiled app")

        # Register KG Extract
        self.registry.register(
            name="kg_extract",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGExtractInput,
            output_schema=KGExtractOutput,
            description="Extract knowledge graph from documents (no database loading)",
        )

        # Register KG Extract + Merge
        self.registry.register(
            name="kg_extract_merge",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGExtractMergeInput,
            output_schema=KGExtractMergeOutput,
            description="Extract knowledge graph and consolidate duplicates by node_id",
        )

        # Register KG Extract with Chunk Awareness
        self.registry.register(
            name="kg_extract_chunk_aware",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGExtractInput,
            output_schema=KGIngestOutput,
            description="Extract knowledge graph with chunk provenance tracking (SourceDocument/ChunkParagraph nodes)",
        )

        # Register KG Ingest
        self.registry.register(
            name="kg_ingest",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGIngestInput,
            output_schema=KGIngestOutput,
            description="Extract knowledge graph and load into Neo4j database",
        )

        # Register KG Ingest with Chunk Awareness
        self.registry.register(
            name="kg_ingest_chunk_aware",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGIngestInput,
            output_schema=KGIngestOutput,
            description="Extract knowledge graph with chunk provenance and load into Neo4j (SourceDocument/ChunkParagraph nodes)",
        )

        # Register KG Ingest JSONL Batch
        self.registry.register(
            name="kg_ingest_jsonl_batch",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGIngestInput,
            output_schema=KGIngestOutput,
            description="Extract knowledge graph from JSONL batch lines in parallel and load into Neo4j",
        )

        # Register KG Extract JSONL Batch
        self.registry.register(
            name="kg_extract_jsonl_batch",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGExtractInput,
            output_schema=KGExtractOutput,
            description="Extract knowledge graph from JSONL batch lines in parallel (no database loading)",
        )

        # Register KG Load JSON
        self.registry.register(
            name="kg_load_json",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGLoadJsonInput,
            output_schema=KGLoadJsonOutput,
            description="Load pre-extracted JSON into Neo4j database with postprocessing",
        )

        # Register KG Query
        self.registry.register(
            name="kg_query",
            workflow_fn=dummy_workflow_fn,
            input_schema=KGQueryInput,
            output_schema=KGQueryOutput,
            description="Query knowledge graph with natural language questions",
        )

        # Register VectorDB Ingest
        self.registry.register(
            name="vectordb_ingest",
            workflow_fn=dummy_workflow_fn,
            input_schema=VectorDBIngestInput,
            output_schema=VectorDBIngestOutput,
            description="Load documents into vector store for semantic search",
        )

        # Register VectorDB Visualize
        self.registry.register(
            name="vectordb_visualize",
            workflow_fn=dummy_workflow_fn,
            input_schema=VectorDBVisualizeInput,
            output_schema=VectorDBVisualizeOutput,
            description="Create 2D UMAP visualization of vector embeddings",
        )

        # Register Ontology Generate
        self.registry.register(
            name="ontology_generate",
            workflow_fn=dummy_workflow_fn,
            input_schema=OntologyGenerateInput,
            output_schema=OntologyGenerateOutput,
            description="Generate N-Triple RDF ontology from node and edge type lists",
        )
