from types import SimpleNamespace

from backends.asr.whisper import WhisperASRBackend
from domain.schemas import ModelRun


def test_whisper_backend_normalizes_segments():
    backend = WhisperASRBackend.__new__(WhisperASRBackend)
    backend.model_run = ModelRun(backend="whisper", model_name="m", model_version="1", config_version="v1")

    class FakeModel:
        def transcribe(self, audio_path, language=None):
            segs = [SimpleNamespace(start=0.0, end=1.1, text=" hello ")]
            info = SimpleNamespace(language="en")
            return segs, info

    backend._model = FakeModel()

    out = backend.transcribe("a.wav")
    assert out.language == "en"
    assert out.segments[0].text == "hello"
    assert out.segments[0].span.end_sec == 1.1
