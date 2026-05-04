from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from domain.entities import MeetingNotes, SpeakerSpan, SpeechSpan, TokenTiming, TranscriptSegment
from domain.enums import PipelineStage


class ModelRun(BaseModel):
    backend: str
    model_name: str
    model_version: str
    config_version: str


class ArtifactRecord(BaseModel):
    run_id: str
    stage: PipelineStage
    artifact_type: str
    path: str
    model_run: ModelRun
    created_at_utc: str
    metadata: dict[str, str] = Field(default_factory=dict)


class VADResult(BaseModel):
    spans: list[SpeechSpan]
    model_run: ModelRun


class DiarizationResult(BaseModel):
    spans: list[SpeakerSpan]
    model_run: ModelRun


class ASRResult(BaseModel):
    segments: list[TranscriptSegment]
    language: Optional[str] = None
    model_run: ModelRun


class AlignmentResult(BaseModel):
    tokens: list[TokenTiming]
    model_run: ModelRun


class SummarizationResult(BaseModel):
    notes: MeetingNotes
    model_run: ModelRun
