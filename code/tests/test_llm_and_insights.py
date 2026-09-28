import os

from src.llm import _ChatAdapter, get_llm, llm_enabled
from src.nodes.insights import _as_list, _as_text, _flatten_item


def test_as_text_joins_list():
    assert _as_text(["a", "b", "c"]) == "a b c"


def test_as_text_handles_none():
    assert _as_text(None) == ""


def test_as_list_wraps_scalar():
    assert _as_list("only") == ["only"]


def test_flatten_item_extracts_action_key():
    item = {"region": "R1", "action": "reduce cost"}
    assert _flatten_item(item) == "reduce cost"


def test_flatten_item_joins_plain_dict():
    assert _flatten_item({"a": 1, "b": 2}) == "a: 1; b: 2"


def test_as_list_flattens_dicts():
    result = _as_list([{"action": "x"}, {"recommendation": "y"}])
    assert result == ["x", "y"]


def test_default_provider_is_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    llm = get_llm()
    assert hasattr(llm, "invoke")
    assert type(llm).__name__ == "OllamaLLM"


def test_unknown_provider_falls_back_to_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    llm = get_llm()
    assert type(llm).__name__ == "OllamaLLM"


def test_llm_enabled_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm_enabled() is True


def test_llm_disabled_for_demo(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert llm_enabled() is False


def test_chat_adapter_extracts_content():
    class FakeMsg:
        content = "hello"

    class FakeModel:
        def invoke(self, messages):
            return FakeMsg()

    adapter = _ChatAdapter(FakeModel())
    assert adapter.invoke([{"role": "user", "content": "hi"}]) == "hello"
