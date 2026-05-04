# architecture.md

## Overview

This document defines the architecture for a local-first meeting transcription and meeting-notes application designed for long-term maintainability, backend/model swap-ability, and future app deployment.

Primary goals:

* Support local processing first
* Allow future replacement of ASR, VAD, diarization, alignment, and summarization models with minimal code changes
* Keep the application centered on domain contracts rather than model-specific APIs
* Support later migration from single-machine batch execution to multi-worker app deployment

Non-goals for the first version:

* Full real-time live transcription
* Multi-tenant SaaS complexity
* Premature microservice decomposition

---

## Architectural Principles

### 1. Domain-first, model-second

The application must encode meeting-transcription business logic in domain and application layers, not inside model adapters.

### 2. Ports and adapters

All model-specific code must live behind explicit interfaces.

### 3. Stable internal schemas

All internal processing must use normalized domain types, not raw provider/model outputs.

### 4. Reproducibility

Every artifact must be traceable to:

* model name
* model version
* config version
* pipeline stage
* run timestamp

### 5. Restartability

Each stage must be restartable from saved artifacts.

### 6. Incremental evolution

Start as a modular monolith. Split into services only when operationally justified.

---

## High-Level Pipeline

```text
Audio Input
  -> Ingest
  -> Canonicalization
  -> Quality Analysis
  -> VAD
  -> Diarization
  -> Segment Orchestration
  -> ASR
  -> Alignment (optional)
  -> Normalization
  -> Summarization / Note Generation
  -> Export
```

---

## System Context

### Inputs

* Uploaded audio/video files
* Local file paths
* Future: microphone stream or recorded session upload

### Outputs

* Verbatim transcript
* Clean transcript
* Speaker-attributed transcript
* Time-aligned transcript
* Meeting summary
* Decisions
* Action items
* Exported markdown/html/docx/json

### External Dependencies

* ffmpeg
* Hugging Face model registry/token access where required
* Local GPU/CPU runtime
* Optional future cloud summarization backend

---

## Layered Architecture

```text
api/
  -> application/
      -> ports/
          <- backends/
      -> domain/
  -> infrastructure/
```

### Layer responsibilities

#### `domain/`

Contains business concepts and normalized data structures.
Must not import model libraries.

#### `ports/`

Contains abstract interfaces for all pluggable backends.
Must not depend on concrete model implementations.

#### `backends/`

Contains concrete integrations for:

* VAD
* diarization
* ASR
* alignment
* summarization

#### `application/`

Contains orchestration and use cases.
Knows only ports and domain models.

#### `api/`

Handles HTTP/WebSocket/API input and output.
Contains no model logic.

#### `infrastructure/`

Handles storage, database, queue, logging, settings, and process management.

---

## Repository Structure

```text
meeting-notes/
├── architecture.md
├── agents.md
├── pyproject.toml
├── README.md
├── configs/
│   ├── app.yaml
│   ├── pipeline.yaml
│   ├── models.yaml
│   └── logging.yaml
├── api/
│   ├── main.py
│   ├── dependencies.py
│   ├── routes/
│   │   ├── health.py
│   │   ├── meetings.py
│   │   ├── jobs.py
│   │   └── exports.py
│   └── schemas/
│       ├── requests.py
│       └── responses.py
├── application/
│   ├── orchestrators/
│   │   ├── transcription_pipeline.py
│   │   └── note_generation_pipeline.py
│   ├── services/
│   │   ├── segment_merger.py
│   │   ├── transcript_normalizer.py
│   │   ├── note_builder.py
│   │   └── artifact_manager.py
│   └── use_cases/
│       ├── create_meeting_job.py
│       ├── transcribe_meeting.py
│       ├── summarize_meeting.py
│       ├── export_meeting.py
│       └── reprocess_stage.py
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── enums.py
│   ├── errors.py
│   └── schemas.py
├── ports/
│   ├── vad.py
│   ├── diarization.py
│   ├── asr.py
│   ├── alignment.py
│   ├── summarization.py
│   ├── storage.py
│   ├── repository.py
│   └── queue.py
├── backends/
│   ├── vad/
│   │   ├── base.py
│   │   ├── silero.py
│   │   └── webrtc.py
│   ├── diarization/
│   │   ├── base.py
│   │   └── pyannote.py
│   ├── asr/
│   │   ├── base.py
│   │   ├── qwen.py
│   │   ├── whisper.py
│   │   └── mock.py
│   ├── alignment/
│   │   ├── base.py
│   │   └── qwen_aligner.py
│   ├── summarization/
│   │   ├── base.py
│   │   ├── local_llm.py
│   │   └── mock.py
│   └── registry.py
├── infrastructure/
│   ├── config/
│   │   └── settings.py
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── repositories.py
│   ├── storage/
│   │   ├── local_fs.py
│   │   └── artifact_paths.py
│   ├── queue/
│   │   ├── task_queue.py
│   │   └── workers.py
│   └── logging/
│       └── logger.py
├── workers/
│   ├── transcription_worker.py
│   ├── summarization_worker.py
│   └── export_worker.py
├── scripts/
│   ├── dev_run_pipeline.py
│   ├── benchmark_backends.py
│   └── migrate_artifacts.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── work/
```

---

## Domain Model

The domain layer defines the stable internal contracts.

### Core entities

#### `Meeting`

Represents a transcription job target.

Fields:

* `meeting_id`
* `title`
* `status`
* `created_at`
* `updated_at`
* `language_hint`
* `metadata`

#### `AudioAsset`

Represents original and canonical audio.

Fields:

* `asset_id`
* `meeting_id`
* `source_path`
* `canonical_path`
* `duration_sec`
* `sample_rate`
* `channels`
* `checksum`

#### `SpeechSpan`

Represents speech-only intervals.

Fields:

* `start`
* `end`
* `score`

#### `SpeakerSpan`

Represents diarization results.

Fields:

* `start`
* `end`
* `speaker`
* `overlap`
* `score`

#### `AudioSegment`

Represents an ASR-ready segment.

Fields:

* `segment_id`
* `meeting_id`
* `audio_path`
* `start`
* `end`
* `speaker`
* `overlap`
* `quality_flags`

#### `TranscriptSegment`

Represents normalized transcription output.

Fields:

* `segment_id`
* `start`
* `end`
* `speaker`
* `text`
* `language`
* `confidence`
* `quality_flags`

#### `TokenTiming`

Represents token/word-level alignment.

Fields:

* `text`
* `start`
* `end`

#### `MeetingNotes`

Represents the final note output.

Fields:

* `summary`
* `decisions`
* `action_items`
* `open_questions`
* `risks`
* `verbatim_transcript`
* `clean_transcript`

---

## Domain Enums

Recommended enums:

* `MeetingStatus`
* `PipelineStage`
* `ArtifactType`
* `JobStatus`
* `QualityFlag`
* `BackendType`

Example pipeline stages:

* `INGESTED`
* `CANONICALIZED`
* `QUALITY_ANALYZED`
* `VAD_DONE`
* `DIARIZATION_DONE`
* `SEGMENTED`
* `ASR_DONE`
* `ALIGNED`
* `NORMALIZED`
* `SUMMARIZED`
* `EXPORTED`

---

## Ports

Ports define the contracts between application logic and pluggable implementations.

### `VADPort`

Responsibilities:

* detect speech spans from canonical audio

Methods:

* `detect_speech(audio_path: str) -> list[SpeechSpan]`
* `capabilities() -> ModelCapabilities`

### `DiarizationPort`

Responsibilities:

* detect speaker-attributed spans

Methods:

* `diarize(audio_path: str, num_speakers: int | None = None, min_speakers: int | None = None, max_speakers: int | None = None) -> list[SpeakerSpan]`
* `capabilities() -> ModelCapabilities`

### `ASRPort`

Responsibilities:

* transcribe audio segments into normalized transcript segments

Methods:

* `transcribe_segments(segments: list[AudioSegment]) -> list[TranscriptSegment]`
* `capabilities() -> ModelCapabilities`

### `AlignmentPort`

Responsibilities:

* refine timings for transcript segments

Methods:

* `align(segment: AudioSegment, text: str) -> list[TokenTiming]`
* `capabilities() -> ModelCapabilities`

### `SummarizationPort`

Responsibilities:

* convert transcript into structured meeting notes

Methods:

* `summarize(transcript: list[TranscriptSegment], context: dict | None = None) -> MeetingNotes`
* `capabilities() -> ModelCapabilities`

### `ArtifactStoragePort`

Responsibilities:

* persist files and JSON artifacts

Methods:

* `save_artifact(...)`
* `load_artifact(...)`
* `list_artifacts(...)`

### `MeetingRepositoryPort`

Responsibilities:

* persist job state and metadata

### `QueuePort`

Responsibilities:

* enqueue jobs
* update status
* emit progress

---

## Backend Adapters

Concrete adapters must do exactly two things:

1. call the provider/model
2. normalize the response into domain types

They must not contain orchestration logic.

### Required adapters for MVP

* `SileroVADBackend`
* `PyannoteDiarizationBackend`
* `QwenASRBackend`
* `QwenAlignerBackend` (optional in MVP)
* `MockSummarizationBackend`

### Rules for adapters

* Never return raw provider responses to the application layer
* Persist raw provider responses as artifacts only if needed for debugging or benchmarking
* Normalize all outputs into domain types before returning
* Raise domain/infrastructure exceptions, not provider-specific exceptions

---

## Backend Registry

The application must use a registry/factory pattern so the selected backend comes from config, not application code.

Example config:

```yaml
models:
  vad:
    provider: silero
  diarization:
    provider: pyannote
  asr:
    provider: qwen3_asr
  alignment:
    provider: qwen_aligner
  summarization:
    provider: local_llm
```

Backend registry responsibilities:

* register backend classes
* instantiate backends from config
* validate required runtime dependencies

---

## Application Use Cases

### `CreateMeetingJobUseCase`

Creates a meeting/job record and stores the source asset.

### `TranscribeMeetingUseCase`

Runs:

* ingest
* canonicalization
* quality analysis
* VAD
* diarization
* segmentation
* ASR
* normalization

### `SummarizeMeetingUseCase`

Consumes normalized transcript and generates structured notes.

### `ExportMeetingUseCase`

Exports transcript and notes to target formats.

### `ReprocessStageUseCase`

Re-runs from a specific stage using saved artifacts.

---

## Pipeline Orchestration

The orchestration layer coordinates stages and persists artifacts after each stage.

### Stage sequence

1. `ingest`
2. `canonicalize`
3. `analyze_quality`
4. `run_vad`
5. `run_diarization`
6. `merge_segments`
7. `run_asr`
8. `run_alignment` (optional)
9. `normalize_transcript`
10. `summarize`
11. `export`

### Key orchestration rules

* Each stage writes a deterministic artifact
* Each stage can be skipped if a valid artifact already exists and reprocessing is not requested
* Each stage records the backend and config used
* Failed stages mark the job state and preserve partial artifacts

---

## Segment Orchestration Rules

This stage is central for quality and maintainability.

Inputs:

* canonical audio
* speech spans
* speaker spans

Outputs:

* ASR-ready segments

Responsibilities:

* intersect speech spans with speaker spans
* split long spans into bounded chunks
* merge extremely short fragments when safe
* label overlap segments
* tag low-quality segments

Recommended defaults:

* target segment length: 10 to 30 seconds
* max segment length: 45 seconds
* min standalone segment length: 0.8 seconds

---

## Data Persistence Strategy

Three classes of artifacts must be persisted.

### 1. Raw artifacts

* original upload
* canonical wav
* cut segments

### 2. Intermediate artifacts

* quality report
* VAD output
* diarization output
* merged segments
* ASR raw output
* normalized transcript
* alignment output

### 3. Final artifacts

* meeting notes
* markdown transcript
* html/docx export
* json export bundle

### Artifact metadata

Each artifact must include:

* `meeting_id`
* `artifact_type`
* `pipeline_stage`
* `created_at`
* `backend_name`
* `model_name`
* `model_version`
* `config_hash`

---

## Database Design

Suggested tables:

* `meetings`
* `audio_assets`
* `processing_jobs`
* `artifacts`
* `model_runs`
* `transcript_segments`
* `speaker_segments`
* `action_items`

### Important entity: `model_runs`

This table makes model comparison and reproducibility possible.

Fields:

* `model_run_id`
* `meeting_id`
* `stage`
* `backend_name`
* `model_name`
* `model_version`
* `config_hash`
* `started_at`
* `completed_at`

---

## API Design

Recommended first API surface:

### `POST /meetings`

Create a meeting record and upload audio.

### `POST /meetings/{meeting_id}/transcribe`

Create a transcription job.

### `POST /meetings/{meeting_id}/summarize`

Create a summarization job.

### `POST /meetings/{meeting_id}/reprocess`

Re-run from a given stage.

### `GET /meetings/{meeting_id}`

Return meeting metadata and status.

### `GET /meetings/{meeting_id}/transcript`

Return transcript data.

### `GET /meetings/{meeting_id}/notes`

Return generated notes.

### `GET /jobs/{job_id}`

Return processing state and progress.

### `GET /exports/{meeting_id}`

List available exports.

---

## Worker Model

Use asynchronous workers for heavy stages.

### CPU-friendly stages

* ingest
* canonicalization
* quality analysis
* VAD
* export

### GPU-preferred stages

* diarization
* ASR
* alignment
* local LLM summarization

### Suggested processing split

* `transcription_worker`
* `summarization_worker`
* `export_worker`

---

## Configuration Design

All runtime choices must come from configuration.

Configuration categories:

* app settings
* file paths
* backend selection
* backend parameters
* segmentation thresholds
* quality thresholds
* export settings
* logging

### Example

```yaml
pipeline:
  segmentation:
    target_length_sec: 20
    max_length_sec: 45
    min_standalone_sec: 0.8
  vad:
    min_speech_duration_ms: 250
    min_silence_duration_ms: 400
  quality:
    enable_loudness_normalization: true
    max_clip_ratio: 0.01
```

---

## Error Handling Strategy

Define domain-level errors and infrastructure-level errors.

### Domain errors

* `InvalidMeetingStateError`
* `MissingArtifactError`
* `UnsupportedPipelineStageError`

### Infrastructure errors

* `BackendInitializationError`
* `ModelInferenceError`
* `ArtifactStorageError`
* `RepositoryError`

Rules:

* do not leak provider-specific exceptions outside backend/infrastructure layers
* preserve stage context in every raised exception
* persist partial state on failure

---

## Logging and Observability

Use structured logging.

Every log should include:

* `meeting_id`
* `job_id`
* `stage`
* `backend`
* `duration_ms`
* `status`

Metrics to track:

* audio duration processed
* segments produced
* average segment length
* ASR throughput
* failure rate by backend
* reprocessing rate

---

## Testing Strategy

### Unit tests

Test:

* domain validators
* segment-merging rules
* transcript normalization
* backend output normalization

### Integration tests

Test:

* end-to-end pipeline with mock/small models
* artifact persistence
* stage restartability
* config-driven backend switching

### Contract tests

Every backend implementation must pass the same contract tests for its port.

Examples:

* any VAD backend returns `list[SpeechSpan]`
* any ASR backend returns `list[TranscriptSegment]`

### Regression tests

Keep a small fixed set of meeting audio fixtures and compare:

* number of segments
* speaker assignment distribution
* normalized transcript snapshots

---

## Security and Privacy

Because audio may contain sensitive content:

* store local artifacts in controlled directories
* separate raw audio from exported notes
* optionally support artifact deletion policies
* redact logs to avoid transcript leakage by default

Future requirements may include:

* encryption at rest
* audit trails
* role-based access

---

## Migration Path

### Phase 1: modular monolith

* local file storage
* synchronous or single-worker async pipeline
* local-only processing

### Phase 2: queued processing

* separate workers
* PostgreSQL-backed job tracking
* resumable jobs

### Phase 3: pluggable deployment modes

* local-only
* local + remote summarization
* remote model serving

### Phase 4: multi-user app

* authentication
* shared storage
* workspace-level artifact management

---

## Implementation Priorities

### MVP priority order

1. domain types
2. port interfaces
3. local storage and repository
4. ingest/canonicalization
5. Silero VAD backend
6. pyannote diarization backend
7. Qwen ASR backend
8. transcript normalization
9. simple export
10. summarization backend

### Nice-to-have after MVP

* alignment backend
* backend benchmarking CLI
* multiple ASR backend support
* UI progress streaming
* speaker name resolution

---

## Design Rules Summary

1. Application code must not import provider/model libraries directly
2. Backends must return only domain types
3. All backend choices must be config-driven
4. Every stage must persist artifacts and metadata
5. Every stage must be restartable
6. Raw provider output is debug-only, not part of the application contract
7. Contract tests are mandatory for all backend implementations

---

## Recommended First Build

Build a modular monolith with:

* FastAPI
* local filesystem artifacts
* PostgreSQL or SQLite for early development
* queue-backed workers or simple background tasks
* Silero VAD backend
* pyannote diarization backend
* Qwen ASR backend
* mock summarizer first, local LLM second

This gives a maintainable base that can evolve into an app without redesigning the core abstractions.
