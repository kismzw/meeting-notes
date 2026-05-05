from __future__ import annotations

from typing import Literal, Optional

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


class MeetingTopic(BaseModel):
    main_topic: str
    subtopics: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)
    seed_terms: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SuspiciousSpan(BaseModel):
    start_char: int
    end_char: int
    text: str
    sentence_index: Optional[int] = None
    reason: str
    surrounding_context: Optional[str] = None
    suspicion_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchQuery(BaseModel):
    query: str
    purpose: Literal["topic_discovery", "entity_discovery", "entity_confirmation", "canonical_spelling"]
    suspicious_spans: list[str] = Field(default_factory=list)
    expected_entity_types: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    title: str
    snippet: str
    url: str
    source: Optional[str] = None


class VocabularyTerm(BaseModel):
    canonical: str
    term_type: str
    readings: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    source: Literal["glossary", "web", "llm", "user_accepted"]
    evidence: list[str] = Field(default_factory=list)
    source_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CorrectionCandidate(BaseModel):
    span: SuspiciousSpan
    replacement: str
    term_type: str
    phonetic_score: float = Field(ge=0.0, le=1.0)
    topic_score: float = Field(ge=0.0, le=1.0)
    context_score: float = Field(ge=0.0, le=1.0)
    entity_consistency_score: float = Field(ge=0.0, le=1.0)
    source_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: list[str] = Field(default_factory=list)


class TranscriptCorrection(BaseModel):
    start_char: int
    end_char: int
    original: str
    replacement: str
    confidence: float = Field(ge=0.0, le=1.0)
    apply_mode: Literal["auto", "review", "reject"]
    reason: str
    scores: dict
    evidence: list[str] = Field(default_factory=list)


class PolishResult(BaseModel):
    topic: MeetingTopic
    suspicious_spans: list[SuspiciousSpan] = Field(default_factory=list)
    search_queries: list[SearchQuery] = Field(default_factory=list)
    search_results: list[SearchResult] = Field(default_factory=list)
    vocabulary_terms: list[VocabularyTerm] = Field(default_factory=list)
    correction_candidates: list[CorrectionCandidate] = Field(default_factory=list)
    corrections: list[TranscriptCorrection] = Field(default_factory=list)
    polished_transcript: str
