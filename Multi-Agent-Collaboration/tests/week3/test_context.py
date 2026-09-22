from week3.context import (
    render_evidence_block,
    render_messages_block,
    render_turn_prompt,
    select_incoming_messages,
)
from week3.models import DiscussionBrief, EvidenceItem, RoutedMessage, TurnRequest


def make_message(sender_id, recipient_ids, content="content", round_number=1, phase="discussion"):
    return RoutedMessage(
        message_id=f"msg-{sender_id}",
        discussion_id="discussion-1",
        phase=phase,
        round_number=round_number,
        sequence_number=1,
        sender_id=sender_id,
        recipient_ids=recipient_ids,
        content=content,
        opinion=content,
    )


def test_select_incoming_messages_filters_by_recipient():
    snapshot = (
        make_message("a", ("b", "c")),
        make_message("d", ("c",)),
        make_message("e", ("b",)),
    )

    delivered_to_b = select_incoming_messages(snapshot, "b")
    delivered_to_c = select_incoming_messages(snapshot, "c")

    assert [m.sender_id for m in delivered_to_b] == ["a", "e"]
    assert [m.sender_id for m in delivered_to_c] == ["a", "d"]


def test_select_incoming_messages_excludes_agents_not_routed_to():
    snapshot = (make_message("a", ("b",)),)

    assert select_incoming_messages(snapshot, "z") == ()


def test_render_messages_block_handles_empty_and_populated():
    assert render_messages_block(()) == "- None"
    rendered = render_messages_block((make_message("a", ("b",), content="claim text"),))
    assert rendered == "- a: claim text"


def test_render_evidence_block_handles_empty_and_populated():
    assert "No externally supplied evidence" in render_evidence_block(())
    evidence = (EvidenceItem(text="Some passage.", title="Paper", url="https://example.org/p"),)
    rendered = render_evidence_block(evidence)
    assert "Paper" in rendered
    assert "https://example.org/p" in rendered
    assert "Some passage." in rendered


def test_render_turn_prompt_includes_previous_opinion_messages_and_evidence():
    brief = DiscussionBrief(
        objective="Pick an architecture.",
        constraints=("One GPU.",),
        topics=("MoE vs dense.",),
    )
    incoming = (make_message("prof_elena", ("dr_aris",), content="MoE increases capacity."),)
    evidence = (EvidenceItem(text="Routing overhead is nontrivial.", title="MoE Systems", url="https://x/y"),)
    request = TurnRequest(
        discussion_id="discussion-1",
        phase="discussion",
        round_number=2,
        sequence_number=6,
        agent_id="dr_aris",
        recipient_ids=("prof_elena",),
        brief=brief,
        incoming_messages=incoming,
        previous_opinion="Dense is preferable for memory reasons.",
        retrieval_query="MoE dense memory efficiency",
        evidence=evidence,
    )

    prompt = render_turn_prompt(request)

    assert "Pick an architecture." in prompt
    assert "discussion round 2" in prompt
    assert "Dense is preferable for memory reasons." in prompt
    assert "prof_elena: MoE increases capacity." in prompt
    assert "MoE dense memory efficiency" in prompt
    assert "Routing overhead is nontrivial." in prompt
