from backends.summarization.mock import MockSummarizationBackend


def test_mock_summarization_contract():
    backend = MockSummarizationBackend(model_name="mock", model_version="1", config_version="v1")
    out = backend.summarize("line1\nline2")
    assert out.notes.summary.startswith("[MOCK] Summary")
    assert out.notes.open_questions == []
    assert out.notes.risks == []
    assert out.notes.clean_transcript == "line1\nline2"
    assert out.model_run.backend == "mock"
