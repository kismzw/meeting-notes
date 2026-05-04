from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from domain.value_objects import TimeRange


class AudioAsset(BaseModel):
    source_path: str
    canonical_path: Optional[str] = None
    sample_rate_hz: int = 16000
    channels: int = 1
    format: str = "wav"


class SpeechSpan(BaseModel):
    span: TimeRange
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class SpeakerSpan(BaseModel):
    speaker_id: str
    span: TimeRange


class TranscriptSegment(BaseModel):
    segment_id: str
    span: TimeRange
    text: str
    speaker_id: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class TokenTiming(BaseModel):
    token: str
    span: TimeRange
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class MeetingNotes(BaseModel):
    summary: str
    decisions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    clean_transcript: str = ""
