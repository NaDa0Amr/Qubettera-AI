"""Citation-instruction consistency tests.

The discussion prompt (``system.jinja``) and the standalone opinion prompt
(``opinion.jinja``) must agree on a single citation format. They previously
contradicted each other: ``opinion.jinja`` mandated ``[Source: URL]`` while
``system.jinja`` asked for verbatim URLs. Neither matched what agents actually
emit — a census of a live run found 0/20 turns using ``[Source: URL]``, while
15/20 cited the bracketed arXiv identifier and 12/20 cited an evidence number.

The agreed format therefore accepts both the evidence number and the paper
identifier already present in the evidence titles.
"""
from __future__ import annotations

from dataclasses import dataclass

from qubettera.agents.pipelines.opinion import render_opinion_prompt
from qubettera.agents.personas import load_persona
from qubettera.agents.utils.prompt_loader import load_prompt

FORBIDDEN = ("[Source: URL]", "verbatim")


@dataclass
class Document:
    title: str
    text: str
    url: str


def discussion_prompt(**overrides) -> str:
    return load_prompt(
        "system.jinja",
        persona=load_persona("moe_efficiency"),
        task="Recommend a Transformer architecture.",
        synthesis_mode=False,
        **overrides,
    )


def opinion_prompt() -> str:
    return render_opinion_prompt(
        persona=load_persona("moe_efficiency"),
        topic="Recommend a Transformer architecture.",
        documents=[
            Document(
                title="[2604.21330] Sparse Routing Study",
                text="Routing improves throughput.",
                url="https://arxiv.org/abs/2604.21330",
            )
        ],
    )


def test_discussion_prompt_does_not_mandate_source_url_format():
    prompt = discussion_prompt()
    for phrase in FORBIDDEN:
        assert phrase not in prompt, f"system.jinja must not require {phrase!r}"


def test_opinion_prompt_does_not_mandate_source_url_format():
    prompt = opinion_prompt()
    for phrase in FORBIDDEN:
        assert phrase not in prompt, f"opinion.jinja must not require {phrase!r}"


def test_discussion_prompt_documents_both_supported_citation_forms():
    prompt = discussion_prompt()
    assert "[3]" in prompt, "the evidence-number form must be shown"
    assert "[2604.21330]" in prompt, "the paper-identifier form must be shown"
    assert "evidence list" in prompt, "the [n] resolution rule must be stated"


def test_opinion_prompt_documents_both_supported_citation_forms():
    prompt = opinion_prompt()
    assert "[2]" in prompt, "the evidence-number form must be shown"
    assert "[2604.21330]" in prompt, "the paper-identifier form must be shown"
    assert "evidence list" in prompt, "the [n] resolution rule must be stated"


def test_opinion_evidence_block_numbers_its_entries():
    # An [n] citation is only resolvable if the evidence block is numbered.
    prompt = opinion_prompt()
    assert "[1]" in prompt, "the evidence block must expose a 1-based number"


def test_both_prompts_share_the_same_no_invented_reference_rule():
    for prompt in (discussion_prompt(), opinion_prompt()):
        assert "invent" in prompt, "both prompts must forbid invented references"
