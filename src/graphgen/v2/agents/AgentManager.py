import importlib
import logging
import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

import graphgen.v2.globalconfig as globalconfig
from graphgen.v2.GraphDBManager import GraphDBConfig, GraphDBFactory
from graphgen.v2.ModelManager import ModelConfig, ModelFactory
from graphgen.v2.VectorStoreManager import VectorDBConfig, VectorFactory
from graphgen.v2.utils import mask_sensitive_value

from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agent_manager")


class AgentConfig(BaseModel):
    importlib.reload(
        globalconfig
    )  # Ensure we have the latest env vars if they were updated at runtime
    template_dir: str = globalconfig.AGENT_TEMPLATE_DIR
    config_path: str = (globalconfig.AGENT_CONFIG_PATH,)
    template_path: Optional[str] = None


class AgentFactory:
    def __init__(
        self,
        model_factory: ModelFactory,
        vector_store_factory: VectorFactory,
        graphdb_factory: GraphDBFactory = None,
        config_path: Path = globalconfig.AGENT_CONFIG_PATH,
        template_dir: Path = globalconfig.AGENT_TEMPLATE_DIR,
        agent_config: Optional[AgentConfig] = None,
        model_config: Optional[ModelConfig] = None,
        vectordb_config: Optional[VectorDBConfig] = None,
        graphdb_config: Optional[GraphDBConfig] = None,
    ):
        importlib.reload(
            globalconfig
        )  # Ensure we have the latest env vars if they were updated at runtime
        self.model_factory = model_factory
        self.vector_store_factory: VectorFactory = vector_store_factory
        self.template_dir = template_dir
        self.graph_factory: GraphDBFactory = graphdb_factory
        self.DEFAULT_TEMPLATE_INSTRUCTION = """
        "\n Reply to the user input based on the system prompt instructions. 
        If you don't have enough information to answer, say 'I don't know'. Input is {raw_text}."""

        # 2. Make the template_dir absolute
        self.template_dir = template_dir
        # Get the absolute path of the directory where THIS script lives
        if agent_config and agent_config.template_dir:
            self.template_dir = Path(agent_config.template_dir)

        # set configs
        self.model_config = model_config
        self.vectordb_config = vectordb_config
        self.graphdb_config = graphdb_config

    # def bulk_build(
    #     self,
    #     agent_classes: list[type[GraphAideAgent]],
    #     agent_ids: list[str] = None,
    #     partials_map: dict = {},
    #     structured_output_schema_map: dict[str, BaseModel] = None,
    #     agent_config: Optional[AgentConfig] = None,
    #     model_config: Optional[ModelConfig] = None,
    #     vectordb_config: Optional[VectorDBConfig] = None,
    #     graphdb_config: Optional[GraphDBConfig] = None,
    # ) -> dict[str, GraphAideAgent]:
    #     agents = {}
    #     for index, agent_class in enumerate(agent_classes):
    #         agent_id = agent_ids[index] if agent_ids else agent_class.__name__
    #         partials = partials_map.get(agent_id) if partials_map else {}
    #         structured_output_schema = (
    #             structured_output_schema_map.get(agent_id)
    #             if structured_output_schema_map
    #             else None
    #         )
    #         agents[agent_id] = self.build(
    #             agent_class,
    #             agent_id,
    #             partials,
    #             structured_output_schema,
    #             agent_config,
    #             model_config,
    #             vectordb_config,
    #             graphdb_config,
    #         )
    #     return agents

    def build_all_agents(
        self,
        agent_dict: dict[str, type[GraphAideAgent]],
        agent_config: Optional[AgentConfig] = None,
    ) -> dict[str, GraphAideAgent]:
        agents = {}
        for agent_id, agent_class in agent_dict.items():
            agents[agent_id] = self.build(
                agent_class,
                agent_id,
                agent_config=agent_config,
                partials={"format_instructions": "format_instructions"},
            )
        return agents

    def build_all_agents_as_tools(
        self, agent_dict: dict[str, type[GraphAideAgent]]
    ) -> dict[str, StructuredTool]:
        tools = {}
        for agent_id, agent_class in agent_dict.items():
            try:
                tools[agent_id] = self.build(agent_class, agent_id).as_tool()
            except ValueError as e:
                logger.error(f"Agent '{agent_id}' cannot be converted to tool: {e}")
        return tools

    def build(
        self,
        agent_class: type[GraphAideAgent],
        agent_id: str,
        partials: dict = None,
        structured_output_schema: BaseModel = None,
        agent_config: Optional[AgentConfig] = None,
        model_config: Optional[ModelConfig] = None,
        vectordb_config: Optional[VectorDBConfig] = None,
        graphdb_config: Optional[GraphDBConfig] = None,
    ) -> GraphAideAgent:

        # 2. Setup Vector Store if defined in JSON
        vector_store = self.vector_store_factory.get_store(
            vectordb_config=vectordb_config
        )  # Default to the first store for now. TODO: support multiple stores and specify in JSON config

        if model_config is None:
            model_config = next(iter(self.model_factory._model_configs.values()), None)

        # Mask sensitive values in model config before printing
        config_str = str(model_config)
        if model_config and hasattr(model_config, 'api_key') and model_config.api_key:
            config_str = config_str.replace(
                model_config.api_key,
                mask_sensitive_value(model_config.api_key)
            )
        logger.debug(f"Agent '{agent_id}': model={config_str}")

        template_path = str(Path(self.template_dir) / f"{agent_id}.template")
        if agent_config and agent_config.template_path:
            template_path = agent_config.template_path

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_str = f.read()
                logger.debug(f"Agent '{agent_id}': template={template_path}")
        except FileNotFoundError:
            if partials and "system_prompt" in partials:
                template_str = (
                    partials["system_prompt"] + self.DEFAULT_TEMPLATE_INSTRUCTION
                )
            else:
                template_str = "Default template string."

        # 3. Inject into Agent
        return agent_class(
            model=self.model_factory.get_model(
                model_config.provider,
                model_config.model_name,
                model_config=model_config,
            )
            if structured_output_schema is None
            else self.model_factory.get_model(
                model_config.provider,
                model_config.model_name,
                model_config=model_config,
            ).with_structured_output(structured_output_schema),
            template_str=template_str,
            settings={
                "partials": partials or {},
                # "persist_directory": model_config["vector_path_env"],
                "vector_store": vector_store,  # Agent now has the RIGHT store
                "graph_store": self.graph_factory.get_driver(
                    graphdb_config=graphdb_config
                )
                if self.graph_factory
                else None,
                "model_config": model_config,  # Pass model_config so agents can use correct embeddings
            },
        )
