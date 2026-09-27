"""Generate optional report narrative from analytics."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ConfigDict, Field

from qubettera.agents.llm.factory import get_chat_model


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

# The system prompt carries the rules the model must obey. Keeping it as a
# separate message (rather than inlining it into the user turn) gives the
# rules greater weight in chat-tuned and reasoning models, which is exactly
# what we want: the constraints matter more than the data.
_SYSTEM_PROMPT = """\
You are an analyst writing the narrative sections of a report about a
multi-agent technical debate. The debate is a structured discussion where AI
agents with distinct personas argue about a technology decision, express
evolving stances over several rounds, and address messages to specific
neighbors according to a fixed communication graph.

Rules:
1. Ground every claim in the numbers provided by the user. Do not invent,
   estimate, or round differently than the provided values. If you refer to
   a number, cite the value as given.
2. Do not claim causation. The influence metric measures statistical
   association, not persuasion. Write "showed the highest estimated
   influence" or "was associated with stance changes in the agents it
   addressed", never "convinced", "persuaded", or "caused".
3. Sentiment measures emotional tone, not stance. A positive sentiment
   score does not imply support for the proposition; a negative one does
   not imply opposition. Do not conflate the two.
4. Note limitations honestly. If a metric is missing, empty, null, or has
   an unusual value, say so. Do not paper over gaps.
5. Be specific. Prefer "Agent A moved from +0.82 to +0.55 over rounds 0
   through 3" over "Agent A's opinion changed significantly."
6. Hedge appropriately. Where the data supports only a weak claim, write a
   weak claim. Where the data is strong, you may state it plainly.
7. Write in Markdown prose: short paragraphs, bulleted lists where useful,
   bold for emphasis. Do not include headings in your sections; the
   renderer supplies them."""

# The user message carries the data. It contains a single JSON-encoded
# facts packet. No prose is added here beyond a short framing sentence,
# because the model's behavior is fully specified by the system message
# and the output schema.
_HUMAN_PROMPT = """\
Here are the analytics facts for one discussion. Write the narrative
sections described in the system message.

```json
{facts_json}
```"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ReportAgentError(RuntimeError):
    """Raised when the LLM fails to produce a valid narrative.

    Callers that want a deterministic fallback (for example, the CLI on
    transient provider errors) catch this exception and call
    ``report.write_report`` instead.
    """


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class ReportNarrative(BaseModel):
    """Structured narrative sections produced by the report agent.

    Every field is prose except ``key_findings``, which is a list of
    single-sentence findings. The renderer inserts these sections between
    the deterministic tables.

    The model config sets ``frozen=True`` so instances are immutable after
    construction, matching the convention used by the other result
    dataclasses in this package (``SentimentResult``, ``StanceResult``).

    Field descriptions are part of the schema the LLM sees when it produces
    structured output, so they double as instructions. Keep them concise
    and behaviorally meaningful.
    """

    model_config = ConfigDict(frozen=True)

    executive_summary: str = Field(
        ...,
        description=(
            "Two to three sentences summarizing what happened in the "
            "discussion. Ground every claim in the provided facts."
        ),
    )
    opinion_analysis: str = Field(
        ...,
        description=(
            "One or two paragraphs analyzing how stances changed across "
            "rounds: who moved, in which direction, and what the trajectory "
            "suggests. Cite specific agents and specific values."
        ),
    )
    agreement_analysis: str = Field(
        ...,
        description=(
            "One paragraph analyzing how group alignment evolved across "
            "rounds. Reference the agreement score for specific rounds."
        ),
    )
    influence_analysis: str = Field(
        ...,
        description=(
            "One paragraph analyzing the estimated influence scores. "
            "Include the association-not-causation caveat."
        ),
    )
    sentiment_analysis: str = Field(
        ...,
        description=(
            "One paragraph analyzing the emotional tone of the discussion "
            "and any patterns by agent or by round. Do not conflate "
            "sentiment with stance."
        ),
    )
    key_findings: list[str] = Field(
        ...,
        description=(
            "Three to six single-sentence findings. Each finding must be "
            "grounded in a number or a named agent from the facts."
        ),
    )
    conclusion: str = Field(
        ...,
        description=(
            "One paragraph summarizing the overall picture and any "
            "notable caveats."
        ),
    )


# ---------------------------------------------------------------------------
# Facts packet
# ---------------------------------------------------------------------------

def _build_facts_packet(analytics: dict[str, Any]) -> dict[str, Any]:
    """Extract a compact view of the analytics dict for the LLM.

    Drops verbose fields that would waste tokens without adding signal:
    per-message sentiment metadata (``text_length``, ``token_count``,
    ``truncated``, ``confidence``), stance scoring reasoning strings, and
    the individual per-message sentiment results.

    Keeps everything the narrative needs to reference a number or a name:

    - ``discussion_id``, ``objective``, ``proposition``, ``topics``
    - ``agents``, ``rounds``, ``edges``
    - per-agent, per-round stance and change
    - per-round agreement
    - per-agent influence and its diagnostic note
    - sentiment distribution, per-agent averages, per-round averages
    """
    sentiment = analytics.get("sentiment", {})
    return {
        "discussion_id": analytics.get("discussion_id", ""),
        "objective": analytics.get("objective", ""),
        "proposition": analytics.get("proposition", ""),
        "topics": list(analytics.get("topics", [])),
        "agents": list(analytics.get("agent_ids", [])),
        "rounds": list(analytics.get("rounds", [])),
        "communication_edges": [list(e) for e in analytics.get("edges", [])],
        "opinion_change": [
            {
                "agent": row.get("agent_id"),
                "round": row.get("round"),
                "stance": row.get("stance"),
                "change": row.get("change"),
            }
            for row in analytics.get("opinion_change", [])
        ],
        "agreement": [
            {
                "round": row.get("round"),
                "agreement": row.get("agreement"),
                "n_agents": row.get("n_agents"),
            }
            for row in analytics.get("agreement", [])
        ],
        "influence": [
            {
                "agent": row.get("agent_id"),
                "influence": row.get("influence"),
                "note": row.get("note"),
            }
            for row in analytics.get("influence", [])
        ],
        "sentiment": {
            "distribution": sentiment.get("distribution", {}),
            "by_agent": sentiment.get("by_agent", {}),
            "by_round": sentiment.get("by_round", {}),
            "model": sentiment.get("method", ""),
        },
    }


# ---------------------------------------------------------------------------
# ReportAgent
# ---------------------------------------------------------------------------

class ReportAgent:
    """LLM-backed narrative generator for the discussion report.

    The agent composes a `ChatPromptTemplate` with a structured-output
    binding on the supplied chat model. The chain is built once in the
    constructor and reused for every discussion the agent handles.

    Parameters
    ----------
    llm : BaseChatModel, optional
        A pre-built LangChain chat model. When omitted, one is constructed
        via the shared `get_chat_model()` factory using the environment's provider
        configuration. Providing an explicit model is useful for tests
        (inject a fake) and for callers that want to reuse a single client
        across many discussions.
    temperature : float, optional
        Sampling temperature passed to the factory when `llm` is not given.
        Defaults to 0.0 for stable output. Ignored when `llm` is provided.
    system_prompt : str, optional
        Override the module-level system prompt. Useful for tests and for
        callers that want to try different prompt phrasings without editing
        the module. When omitted, `_SYSTEM_PROMPT` is used.
    human_prompt : str, optional
        Override the module-level human prompt template. Must contain a
        single `{facts_json}` placeholder.

    Raises
    ------
    ReportAgentError
        If the chat model cannot be constructed or the chain cannot be
        built (for example, a provider that does not support structured
        output).
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        *,
        temperature: float = 0.0,
        system_prompt: str | None = None,
        human_prompt: str | None = None,
    ) -> None:
        self.llm = (
            llm if llm is not None else get_chat_model(temperature=temperature)
        )
        self._system_prompt = system_prompt or _SYSTEM_PROMPT
        self._human_prompt = human_prompt or _HUMAN_PROMPT
        self._chain = self._build_chain()

    # -- Public API ---------------------------------------------------------

    def generate(self, analytics: dict[str, Any]) -> ReportNarrative:
        """Generate the narrative sections for one discussion.

        Parameters
        ----------
        analytics : dict
            The dict returned by `engine.get_analytics`.

        Returns
        -------
        ReportNarrative
            A structured set of prose sections.

        Raises
        ------
        ReportAgentError
            When the LLM invocation fails or returns data that does not
            conform to `ReportNarrative`. Wraps the underlying exception
            so callers can catch a single type.
        """
        facts = _build_facts_packet(analytics)
        facts_json = json.dumps(facts, indent=2, default=str)

        try:
            result = self._chain.invoke({"facts_json": facts_json})
        except Exception as exc:  # noqa: BLE001 â€” surface any provider error
            raise ReportAgentError(
                f"LLM failed to produce a valid report narrative: {exc}"
            ) from exc

        # `with_structured_output` returns a ReportNarrative on success, but
        # a provider that silently falls back to unstructured output could
        # theoretically return a dict. Coerce defensively.
        if isinstance(result, dict):
            try:
                result = ReportNarrative.model_validate(result)
            except Exception as exc:  # noqa: BLE001 â€” pydantic validation
                raise ReportAgentError(
                    f"LLM response did not match the ReportNarrative schema: {exc}"
                ) from exc

        if not isinstance(result, ReportNarrative):
            raise ReportAgentError(
                f"unexpected structured-output type: {type(result).__name__}"
            )
        return result

    # -- Internal -----------------------------------------------------------

    def _build_chain(self):
        """Build the prompt | structured-llm chain once.

        Raises ``ReportAgentError`` if the model does not support
        structured output (for example, an Ollama model without grammar
        support). The error is raised here rather than at invocation time
        so the caller sees the failure immediately at construction.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._system_prompt),
            ("human", self._human_prompt),
        ])

        try:
            structured_llm = self.llm.with_structured_output(ReportNarrative)
        except Exception as exc:  # noqa: BLE001 â€” provider capability error
            raise ReportAgentError(
                f"the configured LLM does not support structured output: {exc}"
            ) from exc

        return prompt | structured_llm

