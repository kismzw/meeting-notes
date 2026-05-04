from __future__ import annotations

import os
from typing import Optional

from domain.entities import SpeakerSpan
from domain.schemas import DiarizationResult, ModelRun
from domain.value_objects import TimeRange
from ports.diarization import DiarizationBackendPort


class PyannoteDiarizationBackend(DiarizationBackendPort):
    def __init__(self, model_name: str, model_version: str, config_version: str, hf_token: Optional[str] = None):
        self.model_run = ModelRun(
            backend="pyannote",
            model_name=model_name,
            model_version=model_version,
            config_version=config_version,
        )
        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise RuntimeError("pyannote.audio is not installed") from exc
        token = hf_token or os.getenv("HF_TOKEN")
        try:
            self._pipeline = Pipeline.from_pretrained(model_name, token=token)
        except TypeError:
            # Backward compatibility with older pyannote versions.
            self._pipeline = Pipeline.from_pretrained(model_name, use_auth_token=token)

    def diarize(self, audio_path: str) -> DiarizationResult:
        diar = self._pipeline(audio_path)
        spans: list[SpeakerSpan] = []
        for turn, _, speaker in diar.itertracks(yield_label=True):
            spans.append(
                SpeakerSpan(
                    speaker_id=str(speaker),
                    span=TimeRange(start_sec=float(turn.start), end_sec=float(turn.end)),
                )
            )
        return DiarizationResult(spans=spans, model_run=self.model_run)
