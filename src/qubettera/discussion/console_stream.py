"""Stream a running discussion to the console while the event sink logs it.

The orchestrator emits one ``turn_completed`` event per agent turn. Wrapping a
sink in :class:`ConsoleTurnStream` prints each turn as it arrives and then
delegates the write, so the operator sees the debate unfold instead of waiting
for a silent, multi-minute run to finish.
"""

from __future__ import annotations

from .interfaces import EventSink

from qubettera.agents.personas.loader import load_persona


def resolve_persona_names(agent_ids: tuple[str, ...]) -> dict[str, str]:
    """Map agent IDs to human-readable persona names, falling back to the ID."""
    names: dict[str, str] = {}
    for agent_id in agent_ids:
        try:
            names[agent_id] = load_persona(agent_id).name
        except Exception:
            # A missing or invalid persona file must not abort a run that would
            # otherwise succeed; the raw agent ID is still unambiguous.
            names[agent_id] = agent_id
    return names


class ConsoleTurnStream:
    """Print a debate's progress live while delegating writes to the wrapped sink."""

    OPINION_LIMIT = 500
    QUERY_LIMIT = 120

    def __init__(self, sink: EventSink, persona_names: dict[str, str]):
        self._sink = sink
        self._persona_names = persona_names

    def write_event(self, event: dict) -> None:
        kind = event.get("event")
        if kind == "discussion_started":
            config = event.get("config", {})
            print(
                f"\nDebate starting: {len(config.get('participant_ids', []))} agents "
                f"over {config.get('num_rounds', 0)} rounds.\n",
                flush=True,
            )
        elif kind == "turn_completed":
            self._print_turn(event["message"])
        elif kind == "discussion_failed":
            # The orchestrator raises straight after this event, so the caller's
            # own summary never runs; surface the failure here instead.
            print(
                f"\nDebate failed after {event.get('completed_message_count', 0)} turn(s): "
                f"{event.get('error', 'unknown error')}\n",
                flush=True,
            )
        self._sink.write_event(event)

    def _print_turn(self, message: dict) -> None:
        sender_id = message["sender_id"]
        sender = self._persona_names.get(sender_id, sender_id)
        if message["phase"] == "initial":
            stage = "opening"
        else:
            stage = f"round {message['round_number']}"
        recipients = ", ".join(message["recipient_ids"]) or "(nobody)"
        print(f"\n[{stage}] {sender} ({sender_id}) -> {recipients}\n{'-' * 70}", flush=True)
        opinion = message["opinion"]
        print(
            opinion[: self.OPINION_LIMIT] + "..."
            if len(opinion) > self.OPINION_LIMIT
            else opinion,
            flush=True,
        )
        query = message.get("retrieval_query")
        if query:
            if len(query) > self.QUERY_LIMIT:
                query = query[: self.QUERY_LIMIT] + "..."
            print(f"[retrieval] {query}", flush=True)
        if message.get("evidence"):
            print(f"[evidence] {len(message['evidence'])} item(s)", flush=True)
