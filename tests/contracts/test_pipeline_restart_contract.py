from domain.entities import SpeechSpan, TranscriptSegment
from domain.schemas import ASRResult, ModelRun, SummarizationResult, VADResult
from domain.value_objects import TimeRange
from infrastructure.storage.local_fs import LocalFSArtifactStorage


def test_pipeline_restart_uses_artifacts(tmp_path, monkeypatch):
    from application.orchestrators.transcription_pipeline import TranscriptionPipeline
    from backends.summarization.mock import MockSummarizationBackend

    calls = {"vad": 0, "asr": 0}

    class FakeVAD:
        def detect(self, audio_path):
            calls["vad"] += 1
            return VADResult(
                spans=[SpeechSpan(span=TimeRange(start_sec=0, end_sec=1), confidence=0.9)],
                model_run=ModelRun(backend="vad", model_name="m", model_version="1", config_version="v1"),
            )

    class FakeASR:
        def transcribe(self, audio_path, language=None):
            calls["asr"] += 1
            return ASRResult(
                segments=[TranscriptSegment(segment_id="s1", span=TimeRange(start_sec=0, end_sec=1), text="hello")],
                language="en",
                model_run=ModelRun(backend="asr", model_name="m", model_version="1", config_version="v1"),
            )

    class FakeIngest:
        def ingest_local_path(self, source_path):
            from domain.entities import AudioAsset
            return AudioAsset(source_path=source_path)

    class FakeCanonical:
        def to_canonical_wav(self, asset, output_path):
            from domain.entities import AudioAsset
            return AudioAsset(source_path=asset.source_path, canonical_path="/tmp/canonical.wav")

    storage = LocalFSArtifactStorage(str(tmp_path))
    pipeline = TranscriptionPipeline(
        storage=storage,
        artifacts_root_dir=str(tmp_path),
        vad=FakeVAD(),
        asr=FakeASR(),
        summarization=MockSummarizationBackend("mock", "1", "v1"),
        ingest=FakeIngest(),
        canonicalize=FakeCanonical(),
    )

    pipeline.run("run-1", "/tmp/in.wav")
    pipeline.run("run-1", "/tmp/in.wav")

    assert calls["vad"] == 1
    assert calls["asr"] == 1
