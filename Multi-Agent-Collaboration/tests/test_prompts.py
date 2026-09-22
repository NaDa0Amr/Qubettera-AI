from __future__ import annotations

import unittest

from src.personas import PersonaConfig
from src.prompts import build_system_prompt

TEST_PERSONA = PersonaConfig(
    persona_id="test_persona",
    name="Test Persona",
    background="background",
    stance="stance",
    communication_style="style",
)


class TestToolAvailabilityMatchesPrompt(unittest.TestCase):
    def test_no_tools_prompt_does_not_mention_search_knowledge_base(self) -> None:
        prompt = build_system_prompt(TEST_PERSONA, tools_available=False)
        self.assertNotIn("search_knowledge_base", prompt)
        self.assertIn("No tools are available", prompt)

    def test_tools_available_prompt_mentions_search_knowledge_base(self) -> None:
        prompt = build_system_prompt(TEST_PERSONA, tools_available=True)
        self.assertIn("search_knowledge_base", prompt)

    def test_default_is_tools_available_true(self) -> None:
        """generate_opinion() relies on the default matching its own
        tools=schemas call -- if this default ever flips, that call site
        must be updated to pass tools_available explicitly."""
        default_prompt = build_system_prompt(TEST_PERSONA)
        explicit_prompt = build_system_prompt(TEST_PERSONA, tools_available=True)
        self.assertEqual(default_prompt, explicit_prompt)


if __name__ == "__main__":
    unittest.main()