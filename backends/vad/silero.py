from __future__ import annotations

from domain.entities import SpeechSpan
from domain.schemas import ModelRun, VADResult
from domain.value_objects import TimeRange
from ports.vad import VADBackendPort


class SileroVADBackend(VADBackendPort):
    def __init__(self, model_name: str, model_version: str, config_version: str, threshold: float = 0.5):
        self.model_run = ModelRun(
            backend="silero",
            model_name=model_name,
            model_version=model_version,
            config_version=config_version,
        )
        self.threshold = threshold
        try:
            from silero_vad import get_speech_timestamps, load_silero_vad, read_audio
        except ImportError as exc:
            raise RuntimeError("silero-vad is not installed") from exc
        self._get_speech_timestamps = get_speech_timestamps
        self._read_audio = read_audio
        self._model = load_silero_vad()

    def detect(self, audio_path: str) -> VADResult:
        wav = self._read_audio(audio_path, sampling_rate=16000)
        chunks = self._get_speech_timestamps(wav, self._model, threshold=self.threshold, sampling_rate=16000)
        spans = [
            SpeechSpan(
                span=TimeRange(start_sec=c["start"] / 16000.0, end_sec=c["end"] / 16000.0),
                confidence=float(c.get("confidence", 1.0)),
            )
            for c in chunks
        ]
        return VADResult(spans=spans, model_run=self.model_run)
