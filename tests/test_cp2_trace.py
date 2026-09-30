from unittest.mock import Mock

from app import mock_llm, mock_rag


def test_retrieval_and_generation_are_observed_without_raw_io() -> None:
    assert hasattr(mock_rag.retrieve, "__wrapped__")
    assert hasattr(mock_llm.FakeLLM.generate, "__wrapped__")


def test_generation_records_model_usage_and_cost(monkeypatch) -> None:
    client = Mock()
    monkeypatch.setattr(mock_llm, "get_langfuse_client", lambda: client)

    response = mock_llm.FakeLLM.generate.__wrapped__(
        mock_llm.FakeLLM(model="test-model"), "short safe prompt"
    )

    update = client.update_current_generation.call_args.kwargs
    assert update["model"] == "test-model"
    assert update["usage_details"] == {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }
    assert update["cost_details"]["total"] == (
        update["cost_details"]["input"] + update["cost_details"]["output"]
    )
    assert "input" not in update
    assert "output" not in update
