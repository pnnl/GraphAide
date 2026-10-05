"""LangFuse configuration and callback setup for observability."""

import logging
import os
from typing import Optional

from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel, Field

logger = logging.getLogger("graphgen.langfuse")


class LangFuseConfig(BaseModel):
    """Configuration for LangFuse observability integration."""

    enabled: bool = Field(
        default=False,
        description="Enable LangFuse tracing (auto-detected if LANGFUSE_* env vars present)",
    )
    public_key: Optional[str] = Field(
        default=None,
        description="LangFuse public key (from LANGFUSE_PUBLIC_KEY env var)",
    )
    secret_key: Optional[str] = Field(
        default=None,
        description="LangFuse secret key (from LANGFUSE_SECRET_KEY env var)",
    )
    base_url: Optional[str] = Field(
        default="https://us.cloud.langfuse.com",
        description="LangFuse server URL (default: us.cloud.langfuse.com for US, cloud.langfuse.com for EU)",
    )
    session_name: Optional[str] = Field(
        default="GraphAide",
        description="Session name for grouping traces (e.g., 'GraphAide-Production')",
    )
    trace_enabled: bool = Field(
        default=True,
        description="Enable trace-level tracing (model calls) vs workflow level only",
    )

    @classmethod
    def from_env(cls) -> "LangFuseConfig":
        """Load config from environment variables.

        Supports both Langfuse v3 and v4+ variable names.

        Checks for (in order):
        - LANGFUSE_PUBLIC_KEY (v3/v4 standard)
        - LANGFUSE_API_KEY (v4 alternative)
        - LANGFUSE_SECRET_KEY (v3/v4 standard)
        - LANGFUSE_BASEURL (v4 alternative)
        - LANGFUSE_BASE_URL (v3 standard)

        If both keys are present, enabled=True.
        """
        # Try v3/v4 standard names first, then v4 alternatives
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY") or os.getenv("LANGFUSE_API_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        base_url = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_BASEURL") or "https://us.cloud.langfuse.com"
        session_name = os.getenv("LANGFUSE_SESSION_NAME") or os.getenv("LANGFUSE_SESSION") or "GraphAide"
        trace_enabled = os.getenv("LANGFUSE_TRACE_ENABLED", "true").lower() == "true"

        enabled = bool(public_key and secret_key)

        if enabled:
            logger.info(f"LangFuse enabled. Session: {session_name}")
            logger.debug(f"  Public Key set: {bool(public_key)}")
            logger.debug(f"  Secret Key set: {bool(secret_key)}")
            logger.debug(f"  Base URL: {base_url}")
        else:
            logger.debug(f"LangFuse disabled:")
            logger.debug(f"  LANGFUSE_PUBLIC_KEY: {bool(os.getenv('LANGFUSE_PUBLIC_KEY'))}")
            logger.debug(f"  LANGFUSE_API_KEY: {bool(os.getenv('LANGFUSE_API_KEY'))}")
            logger.debug(f"  LANGFUSE_SECRET_KEY: {bool(os.getenv('LANGFUSE_SECRET_KEY'))}")

        return cls(
            enabled=enabled,
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
            session_name=session_name,
            trace_enabled=trace_enabled,
        )


def get_langfuse_callback():
    """Create and return LangFuse CallbackHandler if configured.

    Returns the LangFuse CallbackHandler for attaching to LangChain models.
    This enables tracing for all model invocations, including custom endpoints.

    The handler uses environment variables for credentials:
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_BASE_URL

    Supports both Langfuse v3 and v4+ APIs for forward compatibility.

    Returns:
        CallbackHandler if configured, None otherwise.
    """
    config = LangFuseConfig.from_env()

    if not config.enabled:
        logger.debug("LangFuse not enabled - missing credentials")
        return None

    try:
        # v4 API (new location)
        try:
            from langfuse.integrations.langchain import CallbackHandler
            from langfuse import Langfuse as LangfuseClient
            logger.debug("✓ Using Langfuse v4+ CallbackHandler API")
        except ImportError:
            # v3 fallback
            from langfuse.langchain import CallbackHandler
            from langfuse import Langfuse as LangfuseClient
            logger.debug("✓ Using Langfuse v3 CallbackHandler API")

        logger.debug(f"Initializing LangFuse CallbackHandler with base_url={config.base_url}")
        logger.debug(f"  Public Key: {config.public_key[:20] if config.public_key else 'None'}...")
        logger.debug(f"  Secret Key: {'***' + config.secret_key[-10:] if config.secret_key else 'None'}")
        logger.debug(f"  Session: {config.session_name}")

        # Initialize Langfuse SDK client first to ensure global state is set up
        # This is required for CallbackHandler to work properly
        try:
            lf_client = LangfuseClient()
            logger.debug(f"🔍 Langfuse SDK client initialized: {type(lf_client)}")
            logger.debug(f"  Base URL: {lf_client.base_url if hasattr(lf_client, 'base_url') else 'N/A'}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Langfuse SDK client: {e}")
            raise

        # Create LangFuse callback handler for LangChain
        # v4 and v3 have different constructor signatures
        try:
            # Try v4 API first (accepts session_name)
            try:
                callback = CallbackHandler(session_name=config.session_name)
                logger.debug(f"🔍 LangFuse v4 CallbackHandler created with session_name")
            except TypeError:
                # Fall back to v3 API (no session_name parameter)
                callback = CallbackHandler()
                logger.debug(f"🔍 LangFuse v3 CallbackHandler created (no session_name)")

            logger.debug(f"🔍 LangFuse CallbackHandler created successfully")
            logger.debug(f"  Callback type: {type(callback)}")
            logger.debug(f"  Has on_llm_start: {hasattr(callback, 'on_llm_start')}")
            logger.debug(f"  Has on_llm_end: {hasattr(callback, 'on_llm_end')}")
        except Exception as e:
            logger.error(f"✗ Failed to create CallbackHandler: {e}")
            raise

        logger.info(
            f"✓ LangFuse CallbackHandler initialized. "
            f"Public Key: {config.public_key[:20]}..., "
            f"Base URL: {config.base_url}, "
            f"Session: {config.session_name}"
        )
        return callback

    except ImportError as ie:
        logger.warning(
            "LangFuse is configured but langfuse package not installed. "
            "Install with: pip install 'langfuse>=4.0.0'"
        )
        logger.debug(f"Import error details: {ie}")
        return None
    except TypeError as te:
        logger.error(
            f"✗ CallbackHandler initialization failed - parameter mismatch: {te}. "
            f"This may indicate a version mismatch between langfuse and langchain.",
            exc_info=True
        )
        return None
    except Exception as e:
        logger.error(f"✗ Failed to initialize LangFuse CallbackHandler: {e}", exc_info=True)
        return None


class DebugCallback(BaseCallbackHandler):
    """Debug callback to verify LangChain events are firing."""

    def on_llm_start(self, serialized, prompts, **kwargs):
        logger.info(f"✓ [DEBUG_CALLBACK] LLM START: {serialized.get('name', 'unknown')}")

    def on_llm_end(self, response, **kwargs):
        logger.info(f"✓ [DEBUG_CALLBACK] LLM END: got response")

    def on_llm_error(self, error, **kwargs):
        logger.error(f"✗ [DEBUG_CALLBACK] LLM ERROR: {error}")

    def on_chain_start(self, serialized, inputs, **kwargs):
        logger.info(f"✓ [DEBUG_CALLBACK] CHAIN START: {serialized.get('name', 'unknown')}")

    def on_chain_end(self, outputs, **kwargs):
        logger.info(f"✓ [DEBUG_CALLBACK] CHAIN END")

    def on_chain_error(self, error, **kwargs):
        logger.error(f"✗ [DEBUG_CALLBACK] CHAIN ERROR: {error}")


def get_debug_callback():
    """Get a debug callback for testing if LangChain events fire."""
    return DebugCallback()


def get_langfuse_config() -> LangFuseConfig:
    """Get LangFuse configuration from environment.

    Returns:
        LangFuseConfig instance with current settings.
    """
    return LangFuseConfig.from_env()


def flush_langfuse_traces():
    """Flush any pending LangFuse traces to the cloud.

    Call this after extraction completes to ensure traces are sent.
    """
    try:
        from langfuse import Langfuse
        lf = Langfuse()
        logger.debug("🔍 Flushing LangFuse traces...")
        lf.flush()
        logger.info("✓ LangFuse traces flushed to cloud")
    except Exception as e:
        logger.debug(f"Could not flush LangFuse traces: {e}")


def get_langfuse_sdk_client():
    """Get the global Langfuse SDK client for manual tracing.

    For use cases where CallbackHandler doesn't work, use this to manually
    create traces via SDK.
    """
    try:
        from langfuse import Langfuse
        return Langfuse()
    except Exception as e:
        logger.debug(f"Could not get Langfuse SDK client: {e}")
        return None
