"""Task 4: message routing between agents.

``AgentGraph`` (Task 1) is the single source of truth for which edges exist.
This module does not duplicate that graph; it only gives the orchestrator
(and tests) an explicit, named boundary for "who does a message from this
sender reach directly", so routing behavior can be exercised without pulling
in the whole orchestrator.
"""

from __future__ import annotations

from dataclasses import replace

from .agent_graph import AgentGraph
from .models import RoutedMessage


def get_recipients(sender_id: str, graph: AgentGraph) -> tuple[str, ...]:
    """Direct recipients of a message sent by ``sender_id``, per the graph.

    An edge ``sender -> recipient`` in the Task 1 graph is what allows direct
    delivery. Removing that edge removes the recipient from this result and
    therefore from the next round's incoming messages for that agent.
    """
    return graph.recipients(sender_id)


def route_message(message: RoutedMessage, graph: AgentGraph) -> RoutedMessage:
    """Return ``message`` with ``recipient_ids`` recomputed from the graph.

    Useful for callers that already have a ``RoutedMessage`` (for example when
    replaying or re-routing persisted messages) and need its recipients
    resolved against the current graph rather than supplied at construction
    time.
    """
    return replace(message, recipient_ids=get_recipients(message.sender_id, graph))


def filter_delivered(
    messages: tuple[RoutedMessage, ...],
    recipient_id: str,
) -> tuple[RoutedMessage, ...]:
    """Return only the messages from ``messages`` actually routed to ``recipient_id``.

    This is the routing half of Task 3's round-boundary rule: given a complete
    previous-round snapshot, keep only what the graph allowed to reach this
    agent. See ``week3.context.select_incoming_messages`` for the call site
    used by the orchestrator.
    """
    return tuple(message for message in messages if recipient_id in message.recipient_ids)
