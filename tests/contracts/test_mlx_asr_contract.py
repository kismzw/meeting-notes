from backends.asr.mlx_whisper import MLXWhisperASRBackend
from domain.schemas import ModelRun


def test_mlx_whisper_backend_normalizes_segments():
    backend = MLXWhisperASRBackend.__new__(MLXWhisperASRBackend)
    backend.model_run = ModelRun(backend="mlx_whisper", model_name="m", model_version="1", config_version="v1")

    class FakeMLXWhisper:
        @staticmethod
        def transcribe(audio_path, **kwargs):
            return {
                "language": "en",
                "segments": [
                    {"start": 0.0, "end": 1.2, "text": " hello mlx "},
                ],
            }

    backend._mlx_whisper = FakeMLXWhisper()
    backend._model_name = "mlx-community/whisper-tiny"

    out = backend.transcribe("a.wav")
    assert out.language == "en"
    assert out.segments[0].text == "hello mlx"
    assert out.segments[0].span.end_sec == 1.2
