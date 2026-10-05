import logging
import os
from typing import Any, Dict, Optional

import boto3  # For Neptune management if needed
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from pydantic import BaseModel

import graphgen.v2.globalconfig as globalconfig

logger = logging.getLogger("graphgen.v2.graphdbmanager")


class GraphDBConfig(BaseModel):
    uri: str
    username: Optional[str] = None
    password: Optional[str] = None
    database: str = "neo4j"
    provider: str


class GraphDBFactory:
    def __init__(self, graphdb_config: Optional[GraphDBConfig] = None):
        # Load .env file if exists (for local dev), then try env vars
        if os.path.exists(globalconfig.ENV_PATH):
            load_dotenv(globalconfig.ENV_PATH, override=True)

        # Always try to load from environment variables
        self._graphdb_configs: Dict[str, GraphDBConfig] = {}
        self._load_config_from_env()

        # If no config found from env and explicit config provided, use it
        if not self._graphdb_configs and graphdb_config:
            logger.info(f"Using runtime config [{graphdb_config.provider}]")
            self._graphdb_configs = {graphdb_config.provider: graphdb_config}
        elif not self._graphdb_configs:
            logger.warning("No config provided")
        self._gdb_singlton_driver: Any = None  # We have driver to be a singleton, but we also want to support runtime config in the future if needed, so we initialize it as None here and will set it in get_driver() when we have the config available.
        self._graphdb_drivers: Dict[
            str, Any
        ] = {}  # Cache for multiple drivers if we want to support that in the future

    def _load_config_from_env(self):
        # Defaulting to Neo4j as an example
        provider = os.getenv("GRAPH_PROVIDER", "neo4j")
        if provider == "neo4j":
            neo4j_uri = os.getenv("NEO4J_URI")
            if neo4j_uri:  # Only configure if URI is provided
                self._graphdb_configs["neo4j"] = GraphDBConfig(
                    uri=neo4j_uri,
                    username=os.getenv("NEO4J_USERNAME"),
                    password=os.getenv("NEO4J_PASSWORD"),
                    database=os.getenv("NEO4J_DATABASE", "neo4j"),
                    provider="neo4j",
                )
        elif (
            provider == "neptune"
        ):  # TODO: dummy Neptune config for now, we can add more graph databases in the future as needed.
            self._graphdb_configs["neptune"] = GraphDBConfig(
                uri=os.getenv("NEPTUNE_URI"),
                username=os.getenv("NEPTUNE_USERNAME"),
                password=os.getenv("NEPTUNE_PASSWORD"),
                database=os.getenv("NEPTUNE_DATABASE", "neptune"),
                provider="neptune",
            )
        else:
            logger.warning(f"Unsupported graph database provider '{provider}', cannot initialize driver without valid configuration")
            self._graphdb_configs: Dict[str, GraphDBConfig] = {}

    def get_driver(self, graphdb_config: Optional[GraphDBConfig] = None) -> Any:
        """Initializes and returns a singleton Driver object."""
        # TODO: support per-request initialization with different configs if needed in the future
        myconfig = (
            graphdb_config
            if graphdb_config
            else next(iter(self._graphdb_configs.values()), None)
        )

        if myconfig is None:
            raise ValueError(
                "GraphDB: no configuration available. "
                "Set NEO4J_URI environment variable or provide graphdb_config."
            )

        if myconfig.provider in self._graphdb_drivers:
            return self._graphdb_drivers[myconfig.provider]
        else:
            logger.info(f"Connecting to {myconfig.provider} with database {myconfig.database}")
            self._graphdb_configs[myconfig.provider] = myconfig
            if "neo4j" in myconfig.provider:
                try:
                    self._graphdb_drivers["neo4j"] = Neo4jGraph(
                        myconfig.uri,
                        myconfig.username,
                        myconfig.password,
                        database=myconfig.database,
                    )
                except Exception as e:
                    logger.warning(f"Could not connect to Neo4j at {myconfig.uri} (okay if only extracting): {e}")
                    # Return None instead of failing - workflows that don't need GraphDB will continue
                    self._graphdb_drivers["neo4j"] = None
                return self._graphdb_drivers["neo4j"]
            elif "neptune" in myconfig.provider:
                self._graphdb_drivers["neptune"] = boto3.client(
                    "neptunedata", endpoint_url=myconfig.uri
                )
                return self._graphdb_drivers["neptune"]
            else:
                logger.error(f"Unsupported provider '{myconfig.provider}'")
            return self._graphdb_drivers.get(myconfig.provider)

    def close(self):
        """Properly shut down the driver when the app closes."""
        if self._gdb_singlton_driver:
            self._gdb_singlton_driver.close()
