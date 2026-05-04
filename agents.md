# agents.md

## Purpose

This document defines the implementation agents, responsibilities, operating rules, handoff contracts, and delivery order for the meeting transcription and meeting-notes application.

The goal is to make parallel development safe while preserving:

* maintainability
* backend/model swap-ability
* local-first execution
* future app readiness

This file is written for engineers or code-generation agents that will implement the system.

---

## Global Product Goal

Build a local-first application that:

* ingests meeting audio/video
* canonicalizes audio
* detects speech regions
* identifies speaker regions
* transcribes speech
* optionally aligns text timings
* normalizes transcript text
* generates structured meeting notes
* exports results

The system must support future replacement of any model backend without requiring rewrites to application logic.

---

## Core Engineering Rules

All agents must follow these rules.

### Rule 1: Domain contracts are the source of truth

No agent may expose model/provider-specific data structures outside backend code.

### Rule 2: Application layer must depend only on ports and domain models

No application or API code may directly import pyannote, Qwen, Silero, transformers, or similar model libraries.

### Rule 3: Every stage writes artifacts

All meaningful intermediate outputs must be saved in a reproducible form.

### Rule 4: Config over hardcoding

Model selection, thresholds, and backend choices must come from configuration.

### Rule 5: No hidden coupling

If one module requires another module's output, the dependency must be represented explicitly in domain schemas or use-case contracts.

### Rule 6: Tests are part of the deliverable

Each agent must include tests for its own contracts.

### Rule 7: Keep the first version simple

Implement as a modular monolith first. Do not prematurely split into networked microservices.

---

## Shared Definitions

### Canonical audio

All downstream processing assumes canonical audio:

* mono
* 16kHz
* PCM wav

### Domain-normalized objects

Expected shared domain objects include:

* `Meeting`
* `AudioAsset`
* `SpeechSpan`
* `SpeakerSpan`
* `AudioSegment`
* `TranscriptSegment`
* `TokenTiming`
* `MeetingNotes`
* `ArtifactRecord`
* `ModelRun`

### Pipeline stages

* ingest
* canonicalize
* quality_analyze
* vad
* diarize
* segment
* asr
* align
* normalize
* summarize
* export

---

## Agent Overview

Recommended agent split:

1. Domain Agent
2. Ports and Contracts Agent
3. Infrastructure Agent
4. Ingest and Canonicalization Agent
5. VAD Backend Agent
6. Diarization Backend Agent
7. Segmentation Agent
8. ASR Backend Agent
9. Alignment Agent
10. Transcript Normalization Agent
11. Summarization Agent
12. Export Agent
13. API Agent
14. Orchestration Agent
15. QA and Evaluation Agent

Depending on team size, some agents can be combined, but responsibilities should remain separate.

---

## 1. Domain Agent

### Mission

Define stable, provider-agnostic domain models and enums.

### Responsibilities

* implement `domain/entities.py`
* implement `domain/value_objects.py`
* implement `domain/enums.py`
* implement `domain/errors.py`
* implement `domain/schemas.py`

### Deliverables

* typed domain models
* validation logic
* pipeline stage enums
* error classes

### Must not

* import backend/model libraries
* use raw dictionaries where typed models should exist

### Acceptance criteria

* all domain models validate correctly
* domain models are serializable
* no backend/provider-specific naming leaks into the domain layer

---

## 2. Ports and Contracts Agent

### Mission

Define interfaces that backend adapters must implement.

### Responsibilities

* implement `ports/vad.py`
* implement `ports/diarization.py`
* implement `ports/asr.py`
* implement `ports/alignment.py`
* implement `ports/summarization.py`
* implement `ports/storage.py`
* implement `ports/repository.py`
* implement `ports/queue.py`

### Deliverables

* protocol or abstract base interfaces
* capability model definitions
* backend result contracts

### Must not

* implement concrete provider logic

### Acceptance criteria

* every port is typed
* all ports return domain objects
* capability reporting is supported where relevant

---

## 3. Infrastructure Agent

### Mission

Implement supporting infrastructure without leaking infrastructure concerns into business logic.

### Responsibilities

* configuration loading
* structured logging
* database setup
* repository implementations
* artifact filesystem storage
* queue abstraction

### Files

* `infrastructure/config/settings.py`
* `infrastructure/db/*`
* `infrastructure/storage/*`
* `infrastructure/logging/*`
* `infrastructure/queue/*`

### Deliverables

* filesystem artifact store
* repository implementation
* job state persistence
* settings loader

### Acceptance criteria

* can create and retrieve meeting/job/artifact records
* file paths are deterministic and testable
* infrastructure code is replaceable without touching domain code

---

## 4. Ingest and Canonicalization Agent

### Mission

Implement input ingestion and audio standardization.

### Responsibilities

* accept uploaded/local files
* convert to canonical wav
* collect media metadata
* compute checksums
* record source/canonical asset paths

### Files

* `application/services/ingest.py`
* `application/services/canonicalize.py`

### Output contract

Must produce a valid `AudioAsset`.

### Acceptance criteria

* supported media types are converted successfully
* invalid inputs fail with domain/infrastructure errors
* canonical file is reproducible and stored as an artifact

---

## 5. VAD Backend Agent

### Mission

Implement pluggable speech activity detection backends.

### MVP backend

* Silero VAD

### Files

* `backends/vad/base.py`
* `backends/vad/silero.py`
* optional: `backends/vad/webrtc.py`

### Responsibilities

* call the backend model
* normalize results to `list[SpeechSpan]`
* expose capabilities
* persist raw artifacts when requested

### Must not

* decide segmentation policy
* perform orchestration

### Acceptance criteria

* returns only normalized `SpeechSpan`
* no Silero-specific output leaks above backend layer
* passes VAD contract tests

---

## 6. Diarization Backend Agent

### Mission

Implement pluggable speaker diarization backends.

### MVP backend

* pyannote community-1

### Files

* `backends/diarization/base.py`
* `backends/diarization/pyannote.py`

### Responsibilities

* load diarization pipeline
* support optional speaker count hints
* normalize output to `list[SpeakerSpan]`
* preserve overlap information if available

### Acceptance criteria

* returns only normalized `SpeakerSpan`
* provider-specific objects stay inside backend
* passes diarization contract tests

---

## 7. Segmentation Agent

### Mission

Build ASR-ready segments from VAD and diarization outputs.

### Files

* `application/services/segment_merger.py`
* `application/services/segment_policy.py`

### Responsibilities

* intersect speech spans and speaker spans
* split long spans
* merge tiny fragments when safe
* mark overlap regions
* emit `AudioSegment` records
* write segment audio files if configured

### Inputs

* canonical audio
* `list[SpeechSpan]`
* `list[SpeakerSpan]`

### Outputs

* `list[AudioSegment]`

### Acceptance criteria

* deterministic segmentation for same inputs/config
* overlap is preserved as metadata
* edge cases are covered by tests

---

## 8. ASR Backend Agent

### Mission

Implement pluggable ASR backends.

### MVP backend

* Qwen3-ASR

### Optional future backends

* Whisper family
* API-backed ASR
* future local model

### Files

* `backends/asr/base.py`
* `backends/asr/qwen.py`
* `backends/asr/mock.py`
* optional: `backends/asr/whisper.py`

### Responsibilities

* load and invoke ASR model
* transcribe `AudioSegment` batches
* normalize output to `list[TranscriptSegment]`
* expose capabilities

### Must not

* format final notes
* merge transcript policy beyond backend normalization

### Acceptance criteria

* identical interface regardless of underlying model
* no raw model response leaks upward
* batch processing supported where possible
* passes ASR contract tests

---

## 9. Alignment Agent

### Mission

Implement optional text-audio timing refinement.

### MVP backend

* Qwen aligner or no-op aligner

### Files

* `backends/alignment/base.py`
* `backends/alignment/qwen_aligner.py`
* optional: `backends/alignment/noop.py`

### Responsibilities

* align transcript text to audio
* return normalized `TokenTiming` objects

### Acceptance criteria

* optional stage can be disabled cleanly
* alignment output is independent of provider format

---

## 10. Transcript Normalization Agent

### Mission

Turn raw transcript segments into clean, application-ready transcript artifacts.

### Files

* `application/services/transcript_normalizer.py`
* `application/services/text_cleanup.py`
* `application/services/dictionary_rewriter.py`

### Responsibilities

* clean punctuation
* normalize whitespace
* optionally remove fillers for clean transcript
* preserve verbatim transcript separately
* apply custom dictionary replacements
* generate speaker-attributed readable transcript

### Outputs

* verbatim transcript artifact
* clean transcript artifact
* updated normalized `TranscriptSegment` list if needed

### Acceptance criteria

* deterministic normalization rules
* clear separation between verbatim and clean outputs
* dictionary replacement logic is configurable and tested

---

## 11. Summarization Agent

### Mission

Generate structured meeting notes from normalized transcripts.

### Files

* `backends/summarization/base.py`
* `backends/summarization/local_llm.py`
* `backends/summarization/mock.py`
* `application/services/note_builder.py`

### Responsibilities

* consume normalized transcript
* produce `MeetingNotes`
* separate summary, decisions, actions, open questions

### Acceptance criteria

* returns a typed `MeetingNotes`
* prompt/model-specific logic stays inside backend
* supports a mock backend for tests

---

## 12. Export Agent

### Mission

Export internal data structures into user-facing files.

### Files

* `application/services/exporter.py`
* `application/services/markdown_export.py`
* `application/services/json_export.py`
* optional: `application/services/docx_export.py`

### Responsibilities

* export transcript and notes
* maintain stable output schemas
* include provenance metadata when appropriate

### Acceptance criteria

* exported markdown/json are valid and deterministic
* exports are driven from normalized domain objects, not raw artifacts

---

## 13. API Agent

### Mission

Expose the application safely through an app-facing interface.

### Files

* `api/main.py`
* `api/dependencies.py`
* `api/routes/*.py`
* `api/schemas/*.py`

### Responsibilities

* define HTTP endpoints
* validate requests
* trigger use cases/jobs
* serialize responses

### Must not

* import backend/provider SDKs directly
* contain transcription logic

### Acceptance criteria

* API routes delegate to use cases only
* request/response schemas are typed
* errors are mapped cleanly to HTTP responses

---

## 14. Orchestration Agent

### Mission

Implement stage-aware pipeline orchestration and job control.

### Files

* `application/orchestrators/transcription_pipeline.py`
* `application/orchestrators/note_generation_pipeline.py`
* `application/use_cases/*.py`
* `workers/*.py`

### Responsibilities

* sequence pipeline stages
* write artifacts after each stage
* update job state
* resume/reprocess from stage
* record model runs

### Acceptance criteria

* pipeline can restart from a saved stage
* failed stages preserve useful partial artifacts
* all stage transitions are explicit and logged

---

## 15. QA and Evaluation Agent

### Mission

Create quality gates, contract tests, and regression fixtures.

### Files

* `tests/unit/*`
* `tests/integration/*`
* `tests/fixtures/*`
* `scripts/benchmark_backends.py`

### Responsibilities

* backend contract tests
* stage-level regression tests
* artifact schema validation
* benchmark harness for comparing backends

### Acceptance criteria

* every backend implementation passes the same contract tests
* at least one end-to-end integration fixture exists
* snapshot or structural validation exists for transcript outputs

---

## Backend Contract Rules

All backend agents must obey the following:

### 1. Return domain types only

Bad:

* provider objects
* raw provider dicts as public return values

Good:

* `list[SpeechSpan]`
* `list[SpeakerSpan]`
* `list[TranscriptSegment]`
* `MeetingNotes`

### 2. Surface capabilities explicitly

Example capabilities:

* `supports_word_timestamps`
* `supports_confidence`
* `supports_streaming`
* `supports_overlap_detection`

### 3. Keep raw outputs optional

If debugging or benchmarking requires raw model output, save it as an artifact. Do not expose it as the public backend contract.

### 4. Raise normalized exceptions

Provider/model-specific exceptions must be wrapped.

---

## Configuration Rules

All agents must respect configuration boundaries.

### Hardcoded values are not allowed for:

* selected backend provider
* major thresholds
* model identifiers
* artifact directories
* segmentation lengths
* summarization templates if they may vary by environment

### Config layers

* base config
* environment override
* test override

---

## Artifact Rules

Each stage must persist artifacts with enough metadata to allow:

* restart
* auditing
* model comparison
* debugging

Required metadata:

* meeting id
* stage
* backend name
* model name
* model version
* config hash
* timestamp

Artifact classes:

* raw
* intermediate
* final

---

## Coding Conventions

### Type discipline

* use Pydantic or dataclasses consistently for domain models
* all public functions must be typed
* avoid untyped dicts in application code

### File boundaries

* backend-specific imports belong in backend modules only
* no circular imports between domain and infrastructure

### Function size

* prefer small single-purpose functions
* orchestration functions may be larger but should call stage-specific helpers

### Logging

* structured logs only
* include stage, meeting id, and backend in all stage logs

---

## Development Order

Recommended implementation order:

### Phase 1: foundations

1. Domain Agent
2. Ports and Contracts Agent
3. Infrastructure Agent

### Phase 2: core local pipeline

4. Ingest and Canonicalization Agent
5. VAD Backend Agent
6. Diarization Backend Agent
7. Segmentation Agent
8. ASR Backend Agent

### Phase 3: transcript usability

9. Transcript Normalization Agent
10. Export Agent

### Phase 4: orchestration and app shell

11. Orchestration Agent
12. API Agent

### Phase 5: advanced features

13. Alignment Agent
14. Summarization Agent
15. QA and Evaluation Agent

---

## Handoff Contracts Between Agents

### Domain -> Ports

Ports must consume and return domain objects.

### Ports -> Backends

Backends must implement ports exactly.

### Backends -> Application

Application receives only normalized domain types.

### Application -> API

API receives use-case results, not backend-specific data.

### Application -> Export

Exports consume normalized transcript and note objects only.

---

## Definition of Done

A module is done only if all of the following are true:

* implementation exists
* public interfaces are typed
* tests exist
* logging exists for key actions
* artifacts are written where required
* no forbidden dependency violations exist

---

## Forbidden Patterns

The following are not allowed:

### 1. Provider logic in application layer

Example of forbidden pattern:

* `if backend == "pyannote": ...`

### 2. Raw dict propagation

Example of forbidden pattern:

* returning `raw_response["segments"]` from backend to application

### 3. Hidden filesystem assumptions

Do not hardcode paths in stage code.

### 4. Pipeline stage skipping without persisted proof

A stage may only be skipped if a valid artifact for that stage exists and matches required config/version policy.

### 5. Summary generation from unnormalized raw output

Summarization must run on normalized transcript artifacts.

---

## Minimal End-to-End MVP Scenario

The MVP is considered functional when the following scenario works:

1. User uploads a meeting audio file
2. System canonicalizes audio
3. System runs VAD
4. System runs diarization
5. System merges segments
6. System runs ASR
7. System normalizes transcript
8. System exports markdown transcript and json transcript
9. System stores all intermediate artifacts
10. System can re-run ASR from segmented artifacts without repeating ingest/VAD/diarization

---

## Future Extension Rules

When adding a new backend:

1. implement the correct port
2. normalize outputs to domain types
3. register the backend in registry
4. add contract tests
5. add config entry
6. avoid touching application logic unless a truly new capability is introduced

When adding a new stage:

1. define domain outputs
2. define persistence requirements
3. define restart behavior
4. update orchestration explicitly

---

## Final Guidance

This project should be built so that model names are implementation details.

The application should feel like it is built around:

* meetings
* transcripts
* speaker spans
* notes
* artifacts
* jobs

and not around:

* pyannote
* Qwen
* Silero
* any specific provider

If this rule is preserved, the system will stay maintainable even as the model landscape changes.
