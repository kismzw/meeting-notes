from backends.vad.silero import SileroVADBackend
from domain.schemas import ModelRun


def test_silero_backend_normalizes_output():
    backend = SileroVADBackend.__new__(SileroVADBackend)
    backend.model_run = ModelRun(backend="silero", model_name="m", model_version="1", config_version="v1")
    backend._read_audio = lambda path, sampling_rate: [0.0]
    backend._model = object()
    backend._get_speech_timestamps = lambda wav, model, threshold, sampling_rate: [{"start": 0, "end": 16000, "confidence": 0.7}]
    backend.threshold = 0.5

    out = backend.detect("x.wav")
    assert out.spans[0].span.start_sec == 0
    assert out.spans[0].span.end_sec == 1
    assert out.model_run.backend == "silero"
