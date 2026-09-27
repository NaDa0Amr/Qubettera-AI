"""Prompt behavior migrated to the active Jinja template."""
from qubettera.agents.personas import load_persona
from qubettera.agents.utils.prompt_loader import load_prompt


def render(**kwargs):
    return load_prompt("system.jinja", persona=load_persona("dr_aris"), task="Choose architecture",
                       neighbor_opinions={}, tools_available=True, **kwargs)


def test_discussion_prompt_assigns_internal_retrieval_to_orchestrator():
    prompt = render(discussion_mode=True, synthesis_mode=False)
    assert "Never call internal retrieval tools" in prompt
    assert "External web tools are optional fallback" in prompt
    assert "MUST first execute" not in prompt


def test_exhausted_tool_budget_requires_direct_answer():
    assert "No tools remain this turn" in render(discussion_mode=True, synthesis_mode=True)


def test_standalone_agent_retains_retrieval_instruction():
    assert "knowledge_retrieval" in render(discussion_mode=False, synthesis_mode=False)
