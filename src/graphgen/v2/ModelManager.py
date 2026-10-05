import logging
import os
from typing import Any

import boto3
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_aws import BedrockEmbeddings, ChatBedrock
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field

from graphgen.v2 import globalconfig
from graphgen.v2.LangFuseManager import get_langfuse_callback

logger = logging.getLogger("graphgen.v2.modelmanager")


# ModelConfig: Controls LLM output limits
# For input chunk/segment size, see max_tokens_per_segment in CLI (--max-tokens-per-segment) or workflows
class ModelConfig(BaseModel):
    provider: str
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.0
    max_output_tokens_limit_llm: int = globalconfig.DEFAULT_MAX_OUTPUT_TOKENS_LIMIT_LLM  # LLM output token limit. For input chunk size, see max_tokens_per_segment in workflows
    embedding_model_name: str | None = Field(default="text-embedding-3-small-project")
    service_name: str | None = (
        "bedrock-runtime"  # For AWS services like Bedrock, specify the service name (e.g., "bedrock-runtime")
    )
    region_name: str | None = "us-west-2"  # For AWS services, specify the region
    profile_name: str | None = (
        None  # For AWS services, specify the credentials profile name if needed
    )


class ModelFactory:
    def __init__(self, model_config: ModelConfig | None = None):
        self._model_configs: dict[str, ModelConfig] = {}

        # If explicit model_config provided, use it with highest priority (skip .env)
        if model_config:
            logger.info(f"Using runtime config [{model_config.provider}]")
            MODEL_OBJECT_KEY = f"{model_config.provider}_{model_config.model_name}"
            self._model_configs = {MODEL_OBJECT_KEY: model_config}
        else:
            # Load .env file if exists and no runtime config provided
            if os.path.exists(globalconfig.ENV_PATH):
                logger.debug(
                    f"Loading environment variables from {globalconfig.ENV_PATH}"
                )
                load_dotenv(globalconfig.ENV_PATH, override=True)

            # Load config from environment variables
            self._load_config_from_env()

        # Verify config was loaded
        if not self._model_configs:
            logger.warning("No config provided")

        self._model_objects: dict[
            str, Any
        ] = {}  # Cache for initialized model instances

        # Initialize LangFuse client for tracing (optional)
        # LangFuse 4.15.4+ auto-instruments LangChain via env vars
        self._langfuse_client = get_langfuse_callback()
        if self._langfuse_client:
            logger.debug(f"🔍 [ModelFactory] LangFuse callback initialized: {self._langfuse_client}")
        else:
            logger.debug("🔍 [ModelFactory] LangFuse not available for this session")

    def _load_config_from_env(self):
        """
        Reads env variables and maps them to internal settings.
        Example env format: OPENAI_MODEL_NAME, OPENAI_API_KEY, etc.
        """
        # Define the models you want to support based on your .env keys
        providers = ["openai", "anthropic", "google", "bedrock", "lmstudio"]

        for p in providers:
            api_key = os.getenv(f"{p.upper()}_API_KEY")
            if api_key:
                # Store settings in the Pydantic model for validation
                MODEL_OBJECT_KEY = (
                    f"{p}_{os.getenv(f'{p.upper()}_MODEL_NAME', 'default')}"
                )
                self._model_configs[MODEL_OBJECT_KEY] = ModelConfig(
                    provider=p,
                    model_name=os.getenv(f"{p.upper()}_MODEL_NAME", "default"),
                    api_key=api_key,
                    base_url=os.getenv(f"{p.upper()}_BASE_URL"),
                    temperature=float(os.getenv(f"{p.upper()}_TEMPERATURE", 0.0)),
                    max_tokens=int(os.getenv(f"{p.upper()}_MAX_TOKENS", 8192)),
                    embedding_model_name=os.getenv(
                        f"{p.upper()}_EMBEDDING_MODEL_NAME",
                        "text-embedding-3-small-project",
                    ),
                )

    def get_model(
        self, provider: str, model_name: str, model_config: ModelConfig | None = None
    ) -> Any:
        """Returns the initialized LangChain model instance."""
        MODEL_OBJECT_KEY = f"{provider}_{model_name}"
        if MODEL_OBJECT_KEY in self._model_objects:
            return self._model_objects[MODEL_OBJECT_KEY]

        if MODEL_OBJECT_KEY not in self._model_configs:
            logger.warning(f"Model not configured: {provider}/{model_name}")

        try:
            if model_config is None:
                model_config = self._model_configs[MODEL_OBJECT_KEY]
            # TODO: _model behaves different than vector store and graphdb store beuase it is an object of settings rather a dict of vector driver (in vector manager) or graph driver (in graph manager). We should streamline this in the future to avoid confusion. Maybe we can have a _model_settings and then we create the model instance in get_model() method based on the settings, similar to how we do in vector and graph manager.

            if model_config.provider == "openai":
                model = ChatOpenAI(
                    model=model_config.model_name,
                    api_key=model_config.api_key,
                    openai_api_base=model_config.base_url,
                    base_url=model_config.base_url,
                    temperature=model_config.temperature,
                    max_tokens=model_config.max_output_tokens_limit_llm,
                )
                if self._langfuse_client:
                    logger.debug(f"🔍 [ModelFactory] Attaching LangFuse callbacks to OpenAI model")
                    model = model.with_config(callbacks=[self._langfuse_client])
                self._model_objects[MODEL_OBJECT_KEY] = model
            elif model_config.provider == "anthropic":
                model = ChatAnthropic(
                    model=model_config.model_name,
                    api_key=model_config.api_key,
                    anthropic_api_base=model_config.base_url,
                    temperature=model_config.temperature,
                    max_tokens=model_config.max_output_tokens_limit_llm,
                )
                if self._langfuse_client:
                    logger.debug(f"🔍 [ModelFactory] Attaching LangFuse callbacks to Anthropic model")
                    model = model.with_config(callbacks=[self._langfuse_client])
                self._model_objects[MODEL_OBJECT_KEY] = model
            elif model_config.provider == "google":
                model = ChatGoogleGenerativeAI(
                    model=model_config.model_name,
                    api_key=model_config.api_key,
                    temperature=model_config.temperature,
                    max_output_tokens=model_config.max_output_tokens_limit_llm,
                )
                if self._langfuse_client:
                    logger.debug(f"🔍 [ModelFactory] Attaching LangFuse callbacks to Google model")
                    model = model.with_config(callbacks=[self._langfuse_client])
                self._model_objects[MODEL_OBJECT_KEY] = model
            elif model_config.provider == "bedrock":
                bedrock_runtime = boto3.client(
                    service_name=model_config.service_name,
                    region_name=model_config.region_name,
                )
                model = ChatBedrock(
                    client=bedrock_runtime,
                    model_id=model_config.model_name,
                    max_tokens=model_config.max_output_tokens_limit_llm,
                    model_kwargs={"temperature": model_config.temperature},
                )
                if self._langfuse_client:
                    logger.debug(f"🔍 [ModelFactory] Attaching LangFuse callbacks to Bedrock model")
                    model = model.with_config(callbacks=[self._langfuse_client])
                self._model_objects[MODEL_OBJECT_KEY] = model
            elif model_config.provider == "lmstudio":
                base_url = model_config.base_url or "http://localhost:1234/v1"
                model = ChatOpenAI(
                    model=model_config.model_name,
                    api_key=model_config.api_key or "lm-studio",
                    base_url=base_url,
                    temperature=model_config.temperature,
                    max_tokens=model_config.max_output_tokens_limit_llm,
                )
                if self._langfuse_client:
                    logger.debug(f"🔍 [ModelFactory] Attaching LangFuse callbacks to LMStudio model")
                    model = model.with_config(callbacks=[self._langfuse_client])
                self._model_objects[MODEL_OBJECT_KEY] = model

            logger.debug(f"🔍 [ModelFactory] Model ready: provider={model_config.provider}")
            return self._model_objects[MODEL_OBJECT_KEY]
        except Exception as e:
            raise ValueError(f"Error initializing model for provider '{provider}': {e}")

    def get_embeddings(self, provider: str = None, model_name: str = None) -> Any:
        """Returns the initialized LangChain embeddings instance."""
        # Auto-detect provider from available configs if not specified
        if provider is None:
            first_config = next(iter(self._model_configs.values()), None)
            if first_config:
                provider = first_config.provider
            else:
                provider = "bedrock"  # fallback

        MODEL_OBJECT_KEY = f"{provider}_{model_name or 'default'}"

        # Get config from available configs
        config = None
        for key, cfg in self._model_configs.items():
            if provider in key:
                config = cfg
                break

        if provider == "openai":
            # OpenAI embeddings
            api_key = config.api_key if config else os.getenv("OPENAI_API_KEY")
            base_url = config.base_url if config else os.getenv("OPENAI_BASE_URL")
            embedding_model = (
                config.embedding_model_name
                if config
                else os.getenv("OPENAI_EMBEDDING_MODEL_NAME", "text-embedding-3-small")
            )
            return OpenAIEmbeddings(
                api_key=api_key,
                base_url=base_url,
                model=embedding_model,
            )
        elif provider == "lmstudio":
            # LMStudio: use local embedding model via OpenAI-compatible endpoint
            # Disable tiktoken to send raw text (not tokens) - LMStudio expects strings
            base_url = (
                config.base_url
                if config
                else os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
            )
            embedding_model = (
                config.embedding_model_name
                if config
                else os.getenv(
                    "LMSTUDIO_EMBEDDING_MODEL_NAME",
                    "text-embedding-multilingual-e5-base",
                )
            )
            return OpenAIEmbeddings(
                api_key="lm-studio",
                base_url=base_url,
                model=embedding_model,
                # CRITICAL: tiktoken_enabled=False for local APIs (e.g., LMStudio, Ollama)
                # OpenAI SDK converts text→tokens before sending. Local APIs expect raw strings.
                # With tiktoken enabled: converts "text"→[token_ids] → API rejects with 400 error
                # Issue: "Error code: 400 - {'error': "'input' field must be a string or an array of strings"}"
                #
                tiktoken_enabled=False,
                check_embedding_ctx_length=False,
            )
        else:
            # Bedrock embeddings
            profile = config.profile_name if config else None
            return BedrockEmbeddings(
                credentials_profile_name=profile,
                region_name="us-west-2",
                model_id="amazon.titan-embed-text-v1",
            )
