from __future__ import annotations

from typing import Optional

from domain.entities import TranscriptSegment
from domain.schemas import ASRResult, ModelRun
from domain.value_objects import TimeRange
from ports.asr import ASRBackendPort


class WhisperASRBackend(ASRBackendPort):
    def __init__(
        self,
        model_name: str,
        model_version: str,
        config_version: str,
        device: str = "auto",
        compute_type: str = "auto",
    ):
        self.model_run = ModelRun(
            backend="whisper",
            model_name=model_name,
            model_version=model_version,
            config_version=config_version,
        )
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed") from exc
        self._model = WhisperModel(model_name, device=device, compute_type=compute_type)

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> ASRResult:
        segments, info = self._model.transcribe(audio_path, language=language)
        normalized: list[TranscriptSegment] = []
        for idx, seg in enumerate(segments):
            normalized.append(
                TranscriptSegment(
                    segment_id=f"seg-{idx}",
                    span=TimeRange(start_sec=float(seg.start), end_sec=float(seg.end)),
                    text=seg.text.strip(),
                    confidence=None,
                )
            )
        return ASRResult(segments=normalized, language=getattr(info, "language", language), model_run=self.model_run)
