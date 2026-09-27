"""Exercise real LangChain/Ollama request serialization without network calls."""
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from ollama import Client

from qubettera.agents.agent.budget import InputBudget


@pytest.mark.parametrize("binding", ["plain", "tools", "options"])
def test_generation_cap_reaches_ollama_options_and_preserves_configuration(monkeypatch, binding):
    monkeypatch.setenv("MODEL_ANSWER_TOKENS", "321")
    model = ChatOllama(model="test-model", num_ctx=8192, temperature=.2, num_predict=999, seed=42)

    @tool
    def search(query: str) -> str:
        """Search for evidence."""
        return ""

    runnable = model
    if binding == "tools":
        runnable = model.bind_tools([search])
    elif binding == "options":
        runnable = model.bind(options={"temperature": .4, "num_ctx": 4096, "num_predict": 1000})

    # autospec enforces the actual Client.chat signature, catching the original
    # unexpected-keyword crash instead of accepting arbitrary model kwargs.
    with patch.object(Client, "chat", autospec=True) as chat:
        chat.return_value = iter([{"message": {"role": "assistant", "content": "answer"}, "done": True}])
        result = InputBudget(model).invoke(runnable, [HumanMessage(content="Question")],
                                          [search] if binding == "tools" else ())
    assert result.content == "answer"
    payload = chat.call_args.kwargs
    assert "num_predict" not in payload
    assert payload["options"]["num_predict"] == 321
    assert payload["options"]["num_ctx"] == (4096 if binding == "options" else 8192)
    assert payload["options"]["temperature"] == (.4 if binding == "options" else .2)
    if binding != "options":
        assert payload["options"]["seed"] == 42
    if binding == "tools":
        assert payload["tools"][0]["function"]["name"] == "search"
    assert model.num_predict == 999


def test_non_ollama_generation_cap_stays_max_tokens():
    from unittest.mock import Mock
    model = Mock(spec=["bind"])
    budget = InputBudget()
    budget.invoke(model, [HumanMessage(content="Question")])
    model.bind.assert_called_once_with(max_tokens=budget.answer)
