"""Task 3: explicit, testable context construction for one discussion turn.

The orchestrator (Task 1/2) already produces the right *data* for a turn:
``TurnRequest.incoming_messages`` and ``TurnRequest.previous_opinion``. This
module makes the two behaviors that matter for Task 3 explicit, named, and
unit-testable instead of leaving them as inline expressions:

1. ``select_incoming_messages`` — a round only ever sees the *complete*
   previous-stage snapshot, filtered down to the messages the Task 1/4 graph
   actually routed to this agent. Never a partially built current round.
2. ``render_turn_prompt`` — the previous opinion, routed messages, retrieval
   query, and retrieved evidence all have to actually reach the LLM prompt,
   not just live as Python metadata on ``TurnRequest``.
"""

from __future__ import annotations

from typing import Iterable

from .models import EvidenceItem, RoutedMessage, TurnRequest
from .router import filter_delivered


def select_incoming_messages(
    previous_snapshot: Iterable[RoutedMessage],
    agent_id: str,
) -> tuple[RoutedMessage, ...]:
    """Return only the previous-round messages routed to ``agent_id``.

    ``previous_snapshot`` must be a *completed* round (or the initial stage):
    every message in it was produced before this call, so nothing from the
    round currently being computed can leak in. Delivery itself is Task 4's
    concern (see ``week3.router.filter_delivered``); this function only adds
    the Task 3 framing of "the previous round's slice of context for one
    agent".
    """
    return filter_delivered(tuple(previous_snapshot), agent_id)


def render_messages_block(messages: tuple[RoutedMessage, ...]) -> str:
    if not messages:
        return "- None"
    return "\n".join(f"- {message.sender_id}: {message.content}" for message in messages)


def render_evidence_block(evidence: tuple[EvidenceItem, ...]) -> str:
    if not evidence:
        return "- No externally supplied evidence for this turn. You may use your available tools."
    return "\n".join(
        f"- {item.title or 'Untitled source'} | {item.url or 'no URL'}\n  {item.text}"
        for item in evidence
    )


def render_turn_prompt(request: TurnRequest) -> str:
    """Render the full prompt supplied to the Week 2 agent runtime for one turn.

    Contains, in order: the project event, the stage instruction, the agent's
    previous opinion, the routed previous-round messages, the retrieval query,
    and the retrieved evidence — see Task 3-5 README section 8.
    """
    stage = (
        "Form your initial opinion independently. No neighboring messages are available yet."
        if request.phase == "initial"
        else f"This is discussion round {request.round_number}. Respond to the routed messages and evidence."
    )
    previous = request.previous_opinion or "No previous opinion; this is the initial stage."
    return (
        "You are an expert participant in a structured multi-agent discussion.\n\n"
        f"{request.brief.render()}\n\n"
        f"Stage instruction:\n{stage}\n\n"
        f"Your previous opinion:\n{previous}\n\n"
        "Messages delivered to you according to the communication graph:\n"
        f"{render_messages_block(request.incoming_messages)}\n\n"
        f"Retrieval query for this turn:\n{request.retrieval_query or 'Not supplied'}\n\n"
        f"Retrieved evidence:\n{render_evidence_block(request.evidence)}\n\n"
        "Return your current recommendation with reasoning. Explicitly address relevant neighboring "
        "claims. Cite the supplied or tool-retrieved sources for factual claims. Do not invent sources."
    )
