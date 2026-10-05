"""Core abstractions for the workflow system: WorkflowConfig, WorkflowResult, WorkflowRegistry."""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Type

from pydantic import BaseModel

from graphgen.v2.ModelManager import ModelConfig
from graphgen.v2.GraphDBManager import GraphDBConfig
from graphgen.v2.VectorStoreManager import VectorDBConfig
from graphgen.v2.state import Node, Edge


@dataclass
class WorkflowConfig:
    """Hierarchical configuration: global defaults + per-call overrides.

    Attributes:
        model_config: LLM configuration (provider, model name, etc.)
        graphdb_config: Graph database connection config (Neo4j, Neptune)
        vector_config: Vector store config (ChromaDB path, etc.)
        clear_existing_graph: Whether to clear existing graph before ingest
        max_segments: Limit number of segments to process
        retry_max_attempts: Max retry attempts for failed operations
        node_batch_size: Batch size for kg_load_json node loading (default 30)
        edge_batch_size: Batch size for kg_load_json edge loading (default 50)
        extra_options: Custom per-workflow parameters
    """
    model_config: Optional[ModelConfig] = None
    graphdb_config: Optional[GraphDBConfig] = None
    vector_config: Optional[VectorDBConfig] = None

    clear_existing_graph: bool = False
    max_segments: Optional[int] = None
    retry_max_attempts: int = 3
    node_batch_size: int = 30
    edge_batch_size: int = 50

    extra_options: Optional[Dict[str, Any]] = None

    def merge_with(self, other: Optional["WorkflowConfig"]) -> "WorkflowConfig":
        """Merge another config into this one (other takes precedence).

        Args:
            other: Config to merge in (overrides will take precedence)

        Returns:
            New merged WorkflowConfig
        """
        if other is None:
            return WorkflowConfig(**self.__dict__)

        return WorkflowConfig(
            model_config=other.model_config or self.model_config,
            graphdb_config=other.graphdb_config or self.graphdb_config,
            vector_config=other.vector_config or self.vector_config,
            clear_existing_graph=other.clear_existing_graph or self.clear_existing_graph,
            max_segments=other.max_segments or self.max_segments,
            retry_max_attempts=other.retry_max_attempts if other.retry_max_attempts != 3 else self.retry_max_attempts,
            extra_options={**(self.extra_options or {}), **(other.extra_options or {})},
        )


@dataclass
class WorkflowResult:
    """Standardized result format for all workflows.

    Attributes:
        success: Whether workflow completed successfully
        workflow_name: Name of the workflow that was executed
        execution_time_seconds: Total execution time
        data: Generic result data (workflow-specific)
        nodes: Extracted or queried nodes (if applicable)
        edges: Extracted or queried edges (if applicable)
        answer: Answer to query (if applicable)
        stats: Workflow-specific statistics (e.g., nodes_created, edges_created)
        messages: Agent messages/logs from execution
        errors: Error/warning messages encountered
    """
    success: bool
    workflow_name: str
    execution_time_seconds: float

    # Core outputs (workflow-specific subset populated)
    data: Optional[Dict[str, Any]] = None
    nodes: Optional[list[Node]] = None
    edges: Optional[list[Edge]] = None
    answer: Optional[str] = None

    # Metadata
    stats: Dict[str, Any] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary (with Node/Edge serialization)."""
        return {
            "success": self.success,
            "workflow_name": self.workflow_name,
            "execution_time_seconds": self.execution_time_seconds,
            "data": self.data,
            "nodes": [n.model_dump() if hasattr(n, "model_dump") else n for n in (self.nodes or [])],
            "edges": [e.model_dump() if hasattr(e, "model_dump") else e for e in (self.edges or [])],
            "answer": self.answer,
            "stats": self.stats,
            "messages": self.messages,
            "errors": self.errors,
        }


@dataclass
class WorkflowDefinition:
    """Metadata and runner for a workflow.

    Attributes:
        name: Unique workflow name
        workflow_fn: Callable that executes the workflow
        input_schema: Pydantic model validating inputs
        output_schema: Pydantic model for outputs
        description: Human-readable description
    """
    name: str
    workflow_fn: Callable
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    description: str


class WorkflowRegistry:
    """Registry of all available workflows.

    Enables workflow discovery, input validation, and decouples workflow
    registration from execution.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._workflows: Dict[str, WorkflowDefinition] = {}

    def register(
        self,
        name: str,
        workflow_fn: Callable,
        input_schema: Type[BaseModel],
        output_schema: Type[BaseModel],
        description: str,
    ) -> None:
        """Register a workflow in the registry.

        Args:
            name: Unique workflow name (e.g., "kg_extract")
            workflow_fn: Callable(inputs: Dict, config: WorkflowConfig) -> WorkflowResult
            input_schema: Pydantic model for input validation
            output_schema: Pydantic model for output validation
            description: Human-readable workflow description

        Raises:
            ValueError: If workflow with same name already registered
        """
        if name in self._workflows:
            raise ValueError(f"Workflow '{name}' already registered")

        self._workflows[name] = WorkflowDefinition(
            name=name,
            workflow_fn=workflow_fn,
            input_schema=input_schema,
            output_schema=output_schema,
            description=description,
        )

    def list_workflows(self) -> Dict[str, WorkflowDefinition]:
        """List all registered workflows.

        Returns:
            Dictionary of name -> WorkflowDefinition
        """
        return dict(self._workflows)

    def get_workflow(self, name: str) -> WorkflowDefinition:
        """Get a workflow by name.

        Args:
            name: Workflow name

        Returns:
            WorkflowDefinition

        Raises:
            KeyError: If workflow not found
        """
        if name not in self._workflows:
            raise KeyError(
                f"Workflow '{name}' not found. Available: {list(self._workflows.keys())}"
            )
        return self._workflows[name]

    def validate_inputs(self, workflow_name: str, inputs: Dict) -> BaseModel:
        """Validate inputs against workflow schema.

        Args:
            workflow_name: Name of workflow
            inputs: Input dictionary to validate

        Returns:
            Instantiated Pydantic model

        Raises:
            ValueError: If validation fails
        """
        workflow_def = self.get_workflow(workflow_name)
        try:
            return workflow_def.input_schema(**inputs)
        except Exception as e:
            raise ValueError(f"Invalid inputs for workflow '{workflow_name}': {str(e)}")

    def exists(self, name: str) -> bool:
        """Check if workflow is registered.

        Args:
            name: Workflow name

        Returns:
            True if registered, False otherwise
        """
        return name in self._workflows


@dataclass
class WorkflowInfo:
    """User-friendly workflow information."""
    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with schema info."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema() if hasattr(self.input_schema, "model_json_schema") else {},
            "output_schema": self.output_schema.model_json_schema() if hasattr(self.output_schema, "model_json_schema") else {},
        }
