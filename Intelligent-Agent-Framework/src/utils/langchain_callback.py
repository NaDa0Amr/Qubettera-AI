"""
LangChain callback handler to capture LLM requests/responses and tool executions.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Union
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class AgentCallbackHandler(BaseCallbackHandler):
    """
    Custom callback handler that logs LLM calls, tool calls, and chain events.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    # ----- LLM Events -----
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Log when an LLM call starts."""
        logger.info(f"LLM CALL START (run_id={run_id})")
        if self.verbose:
            for i, prompt in enumerate(prompts):
                logger.debug(f"   Prompt {i+1}: {prompt[:200]}...")

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Log when an LLM call completes."""
        logger.info(f"LLM CALL END (run_id={run_id})")
        for i, generation in enumerate(response.generations):
            if generation:
                text = generation[0].text
                logger.info(f"   Response {i+1}: {text[:500]}...")
                if self.verbose:
                    logger.debug(f"   Full response: {text}")

    def on_llm_error(
        self,
        error: Exception,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Log LLM errors."""
        logger.error(f"LLM ERROR (run_id={run_id}): {error}")

    # ----- Tool Events -----
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Log when a tool call starts."""
        tool_name = serialized.get("name", "unknown_tool")
        logger.info(f"TOOL START: {tool_name} (run_id={run_id})")
        logger.info(f"   Input: {input_str[:200]}...")

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Log when a tool call completes."""
        logger.info(f"TOOL END (run_id={run_id})")
        logger.info(f"   Output: {output[:500]}...")
        if self.verbose:
            logger.debug(f"   Full output: {output}")

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Log tool errors."""
        logger.error(f"TOOL ERROR (run_id={run_id}): {error}")

    # ----- Chain Events (optional) -----
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Log when a chain (graph node) starts."""
        logger.info(f"CHAIN START: {serialized.get('name', 'unknown')} (run_id={run_id})")

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Log when a chain ends."""
        logger.info(f"CHAIN END (run_id={run_id})")