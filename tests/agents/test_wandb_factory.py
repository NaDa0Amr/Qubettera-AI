from qubettera.agents.llm.factory import get_chat_model


def test_wandb_model_precedence_and_project_header(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "wandb")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("WANDB_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")
    monkeypatch.setenv("WANDB_API_KEY", "test-placeholder")
    monkeypatch.setenv("WANDB_BASE_URL", "https://api.inference.wandb.ai/v1")
    monkeypatch.setenv("WANDB_PROJECT", "team/project")
    model = get_chat_model()
    assert model.model_name == "Qwen/Qwen3-30B-A3B-Instruct-2507"
    assert model.default_headers == {"OpenAI-Project": "team/project"}


def test_explicit_model_override_takes_precedence(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "test-placeholder")
    monkeypatch.setenv("WANDB_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")
    assert get_chat_model(provider="wandb", model="openai/gpt-oss-20b").model_name == "openai/gpt-oss-20b"
