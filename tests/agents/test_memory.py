from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qubettera.agents.memory import AgentMemory


class TestAgentMemory(unittest.TestCase):
    def test_add_and_recent_within_one_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = AgentMemory("test_agent", memory_dir=Path(tmp))
            memory.add(kind="note", topic="t1", content="first fact")
            memory.add(kind="note", topic="t1", content="second fact")

            recent = memory.recent()
            self.assertEqual(len(recent), 2)
            self.assertEqual(recent[0].content, "first fact")
            self.assertEqual(recent[1].content, "second fact")

    def test_memory_survives_recreation(self) -> None:
        """Interaction 1 (write) happens with one AgentMemory instance;
        interaction 2 (read) happens with a brand-new instance pointed at
        the same directory -- this is the persistence guarantee itself."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            first_session = AgentMemory("test_agent", memory_dir=tmp_path)
            first_session.add(
                kind="note",
                topic="latency_budget",
                content="User said the latency budget is 50ms p99.",
            )

            second_session = AgentMemory("test_agent", memory_dir=tmp_path)
            recalled = second_session.recent()

            self.assertEqual(len(recalled), 1)
            self.assertIn("50ms p99", recalled[0].content)

    def test_agents_have_isolated_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            agent_a = AgentMemory("agent_a", memory_dir=tmp_path)
            agent_b = AgentMemory("agent_b", memory_dir=tmp_path)

            agent_a.add(kind="note", topic="t", content="only agent_a knows this")

            self.assertEqual(len(agent_a.recent()), 1)
            self.assertEqual(len(agent_b.recent()), 0)


if __name__ == "__main__":
    unittest.main()
