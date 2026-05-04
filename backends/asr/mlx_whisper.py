from __future__ import annotations

from typing import Optional

from domain.entities import TranscriptSegment
from domain.schemas import ASRResult, ModelRun
from domain.value_objects import TimeRange
from ports.asr import ASRBackendPort


class MLXWhisperASRBackend(ASRBackendPort):
    def __init__(self, model_name: str, model_version: str, config_version: str):
        self.model_run = ModelRun(
            backend="mlx_whisper",
            model_name=model_name,
            model_version=model_version,
            config_version=config_version,
        )
        try:
            import mlx_whisper
        except ImportError as exc:
            raise RuntimeError("mlx-whisper is not installed") from exc
        self._mlx_whisper = mlx_whisper
        self._model_name = model_name

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> ASRResult:
        kwargs = {"path_or_hf_repo": self._model_name}
        if language:
            kwargs["language"] = language
        result = self._mlx_whisper.transcribe(audio_path, **kwargs)

        normalized: list[TranscriptSegment] = []
        for idx, seg in enumerate(result.get("segments", [])):
            normalized.append(
                TranscriptSegment(
                    segment_id=f"seg-{idx}",
                    span=TimeRange(start_sec=float(seg.get("start", 0.0)), end_sec=float(seg.get("end", 0.0))),
                    text=str(seg.get("text", "")).strip(),
                    confidence=None,
                )
            )

        return ASRResult(
            segments=normalized,
            language=result.get("language", language),
            model_run=self.model_run,
        )
