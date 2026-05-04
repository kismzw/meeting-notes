from infrastructure.config.settings import BackendChoice, PipelineConfig


def test_registry_selects_local_llm_summarization(monkeypatch):
    from backends import registry as mod

    class FakeVAD:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeASR:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeSUM:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(mod, "SileroVADBackend", FakeVAD)
    monkeypatch.setattr(mod, "MLXWhisperASRBackend", FakeASR)
    monkeypatch.setattr(mod, "LocalLLMSummarizationBackend", FakeSUM)

    cfg = PipelineConfig(
        config_version="v1",
        vad=BackendChoice(name="silero", model_name="silero-vad"),
        asr=BackendChoice(name="mlx_whisper", model_name="mlx-community/whisper-tiny"),
        summarization=BackendChoice(name="local_llm", model_name="qwen3:8b", options={"base_url": "http://127.0.0.1:11434"}),
        diarization=BackendChoice(name="pyannote", model_name="pyannote", enabled=False),
        alignment=BackendChoice(name="qwen_aligner", model_name="qwen", enabled=False),
    )

    reg = mod.build_backend_registry(cfg)
    assert isinstance(reg.summarization, FakeSUM)
