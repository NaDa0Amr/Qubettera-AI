from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.personas import PersonaConfigError, load_all_personas, load_persona
from src.prompts import build_system_prompt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERSONAS_DIR = PROJECT_ROOT / "personas"


class TestPersonaLoading(unittest.TestCase):
    def test_loads_shipped_personas(self) -> None:
        personas = load_all_personas(PERSONAS_DIR)
        self.assertIn("pragmatic_engineer", personas)
        self.assertIn("research_scientist", personas)

    def test_missing_required_field_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text(json.dumps({"persona_id": "x", "name": "X"}), encoding="utf-8")
            with self.assertRaises(PersonaConfigError):
                load_persona(path)

    def test_duplicate_persona_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = {
                "persona_id": "dup",
                "name": "A",
                "background": "b",
                "stance": "s",
                "communication_style": "c",
            }
            (tmp_path / "a.json").write_text(json.dumps(payload), encoding="utf-8")
            (tmp_path / "b.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(PersonaConfigError):
                load_all_personas(tmp_path)


class TestPersonaAffectsPrompt(unittest.TestCase):
    def test_two_personas_produce_different_system_prompts(self) -> None:
        personas = load_all_personas(PERSONAS_DIR)
        engineer = personas["pragmatic_engineer"]
        scientist = personas["research_scientist"]

        prompt_a = build_system_prompt(engineer)
        prompt_b = build_system_prompt(scientist)

        self.assertNotEqual(prompt_a, prompt_b)
        # The difference must be more than the persona's name: each
        # persona's distinctive stance text should appear in its own
        # prompt and not in the other persona's prompt.
        self.assertIn(engineer.stance[:30], prompt_a)
        self.assertNotIn(engineer.stance[:30], prompt_b)
        self.assertIn(scientist.stance[:30], prompt_b)
        self.assertNotIn(scientist.stance[:30], prompt_a)

    def test_every_shipped_persona_is_pairwise_distinct(self) -> None:
        """Scales automatically as new persona files are added: every
        persona's system prompt must be unique, and every persona's own
        stance text must not leak into another persona's prompt."""
        personas = load_all_personas(PERSONAS_DIR)
        self.assertGreaterEqual(
            len(personas), 2, "Need at least two personas to demonstrate difference."
        )

        prompts = {pid: build_system_prompt(p) for pid, p in personas.items()}

        # No two personas should render to an identical system prompt.
        seen: dict[str, str] = {}
        for pid, prompt in prompts.items():
            for other_pid, other_prompt in seen.items():
                self.assertNotEqual(
                    prompt, other_prompt, f"{pid} and {other_pid} produced identical prompts."
                )
            seen[pid] = prompt

        # Each persona's stance should not bleed into another persona's prompt.
        for pid, persona in personas.items():
            stance_fragment = persona.stance[:30]
            for other_pid, other_prompt in prompts.items():
                if other_pid == pid:
                    continue
                self.assertNotIn(
                    stance_fragment,
                    other_prompt,
                    f"{pid}'s stance leaked into {other_pid}'s system prompt.",
                )


if __name__ == "__main__":
    unittest.main()