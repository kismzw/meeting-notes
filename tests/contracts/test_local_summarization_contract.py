from backends.summarization.local_llm import LocalLLMSummarizationBackend


def test_local_summarization_parses_json_response(monkeypatch):
    backend = LocalLLMSummarizationBackend(
        model_name="qwen3:8b",
        model_version="1",
        config_version="v1",
    )

    monkeypatch.setattr(
        backend,
        "_generate",
        lambda prompt: '{"summary":"要約","decisions":["決定1"],"action_items":["作業1"],"open_questions":["質問1"],"risks":["リスク1"],"clean_transcript":"整形済み"}',
    )

    out = backend.summarize("本日の決定1です。次の作業1を実施します。質問1があります。リスク1があります。")
    assert out.notes.summary == "要約"
    assert out.notes.decisions == ["決定1"]
    assert out.notes.action_items == ["作業1"]
    assert out.notes.open_questions == ["質問1"]
    assert out.notes.risks == ["リスク1"]
    assert out.notes.clean_transcript == "整形済み"
    assert out.model_run.backend == "local_llm"


def test_local_summarization_fallback_when_non_json(monkeypatch):
    backend = LocalLLMSummarizationBackend(
        model_name="qwen3:8b",
        model_version="1",
        config_version="v1",
    )
    monkeypatch.setattr(backend, "_generate", lambda prompt: "これはJSONではない応答")
    out = backend.summarize("dummy")
    assert "JSONではない" in out.notes.summary
    assert out.notes.open_questions == []
    assert out.notes.risks == []
    assert out.notes.clean_transcript == "dummy"


def test_local_summarization_drops_non_explicit_items(monkeypatch):
    backend = LocalLLMSummarizationBackend(
        model_name="qwen3:8b",
        model_version="1",
        config_version="v1",
    )
    monkeypatch.setattr(
        backend,
        "_generate",
        lambda prompt: '{"summary":"要約","decisions":["明示された決定","推測の決定"],"action_items":["明示されたタスク","推測タスク"],"open_questions":["明示された質問","推測質問"],"risks":["明示されたリスク","推測リスク"],"clean_transcript":"整形文"}',
    )

    transcript = "本日の明示された決定です。次に明示されたタスクを実行します。明示された質問があります。明示されたリスクがあります。"
    out = backend.summarize(transcript)
    assert out.notes.decisions == ["明示された決定"]
    assert out.notes.action_items == ["明示されたタスク"]
    assert out.notes.open_questions == ["明示された質問"]
    assert out.notes.risks == ["明示されたリスク"]
    assert out.notes.clean_transcript == "整形文"
