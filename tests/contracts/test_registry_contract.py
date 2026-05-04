from infrastructure.config.settings import BackendChoice, PipelineConfig


def test_registry_uses_config_for_enabled_backends(monkeypatch):
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
    monkeypatch.setattr(mod, "WhisperASRBackend", FakeASR)
    monkeypatch.setattr(mod, "MockSummarizationBackend", FakeSUM)

    cfg = PipelineConfig(
        config_version="v1",
        vad=BackendChoice(name="silero", model_name="silero-vad"),
        asr=BackendChoice(name="whisper", model_name="small"),
        summarization=BackendChoice(name="mock", model_name="mock"),
        diarization=BackendChoice(name="pyannote", model_name="pyannote", enabled=False),
        alignment=BackendChoice(name="qwen_aligner", model_name="qwen", enabled=False),
    )

    reg = mod.build_backend_registry(cfg)
    assert isinstance(reg.vad, FakeVAD)
    assert isinstance(reg.asr, FakeASR)
    assert isinstance(reg.summarization, FakeSUM)
    assert reg.diarization is None
    assert reg.alignment is None
