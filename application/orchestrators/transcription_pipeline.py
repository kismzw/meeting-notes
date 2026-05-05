from __future__ import annotations

from pathlib import Path
from typing import Optional

from application.services.canonicalize import CanonicalizeService
from application.services.export_pdf import PDFExportService
from application.services.ingest import IngestService
from application.services.polish_web_llm import PolishWebLLMConfig, PolishWebLLMService
from domain.entities import AudioAsset
from domain.enums import PipelineStage
from domain.schemas import ASRResult, DiarizationResult, SummarizationResult, VADResult
from ports.asr import ASRBackendPort
from ports.diarization import DiarizationBackendPort
from ports.storage import ArtifactStoragePort
from ports.summarization import SummarizationBackendPort
from ports.vad import VADBackendPort


class TranscriptionPipeline:
    def __init__(
        self,
        storage: ArtifactStoragePort,
        artifacts_root_dir: str,
        vad: VADBackendPort,
        asr: ASRBackendPort,
        summarization: SummarizationBackendPort,
        ingest: Optional[IngestService] = None,
        canonicalize: Optional[CanonicalizeService] = None,
        diarization: Optional[DiarizationBackendPort] = None,
        exporter: Optional[PDFExportService] = None,
        polish_config: Optional[PolishWebLLMConfig] = None,
        polish_service: Optional[PolishWebLLMService] = None,
        polish_glossary_terms: Optional[list[str]] = None,
    ):
        self.storage = storage
        self.artifacts_root_dir = Path(artifacts_root_dir)
        self.vad = vad
        self.diarization = diarization
        self.asr = asr
        self.summarization = summarization
        self.ingest = ingest or IngestService()
        self.canonicalize = canonicalize or CanonicalizeService()
        self.exporter = exporter or PDFExportService()
        self.polish_config = polish_config or PolishWebLLMConfig(enable_transcript_polish=False)
        self.polish_service = polish_service or PolishWebLLMService()
        self.polish_glossary_terms = polish_glossary_terms or []

    def run(self, run_id: str, source_audio_path: str, align_enabled: bool = False) -> dict:
        asset = self._ingest_stage(run_id, source_audio_path)
        canonical_asset = self._canonicalize_stage(run_id, asset)
        if canonical_asset.canonical_path is None:
            raise RuntimeError("Canonical path missing after canonicalization")
        canonical_audio_path = canonical_asset.canonical_path

        vad_result = self._vad_stage(run_id, canonical_audio_path)
        diar_result = self._diar_stage(run_id, canonical_audio_path)
        asr_result = self._asr_stage(run_id, canonical_audio_path)
        normalized_transcript = self._normalize_stage(run_id, asr_result)
        polished_transcript = self._polish_stage(run_id, normalized_transcript)
        summary_result = self._summarize_stage(run_id, polished_transcript)
        export_result = self._export_stage(run_id, asr_result, summary_result)
        if align_enabled:
            self._align_stage(run_id)

        return {
            "ingest": asset,
            "canonicalize": canonical_asset,
            "vad": vad_result,
            "diarization": diar_result,
            "asr": asr_result,
            "normalized_transcript": normalized_transcript,
            "polished_transcript": polished_transcript,
            "summary": summary_result,
            "export": export_result,
        }

    def _ingest_stage(self, run_id: str, source_audio_path: str) -> AudioAsset:
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.INGEST, "audio_asset")
        if existing:
            return AudioAsset.model_validate(existing)
        asset = self.ingest.ingest_local_path(source_audio_path)
        self.storage.write_json_artifact(run_id, PipelineStage.INGEST, "audio_asset", asset.model_dump(mode="json"), self._system_model_run())
        return asset

    def _canonicalize_stage(self, run_id: str, asset: AudioAsset) -> AudioAsset:
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.CANONICALIZE, "audio_asset")
        if existing:
            return AudioAsset.model_validate(existing)
        output_path = str(self.artifacts_root_dir / run_id / "canonical" / "audio.wav")
        canonical = self.canonicalize.to_canonical_wav(asset, output_path)
        self.storage.write_json_artifact(run_id, PipelineStage.CANONICALIZE, "audio_asset", canonical.model_dump(mode="json"), self._system_model_run())
        return canonical

    def _vad_stage(self, run_id: str, canonical_audio_path: str) -> VADResult:
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.VAD, "spans")
        if existing:
            return VADResult.model_validate(existing)
        result = self.vad.detect(canonical_audio_path)
        self.storage.write_json_artifact(run_id, PipelineStage.VAD, "spans", result.model_dump(mode="json"), result.model_run)
        return result

    def _diar_stage(self, run_id: str, canonical_audio_path: str) -> Optional[DiarizationResult]:
        if self.diarization is None:
            return None
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.DIARIZE, "speaker_spans")
        if existing:
            return DiarizationResult.model_validate(existing)
        result = self.diarization.diarize(canonical_audio_path)
        self.storage.write_json_artifact(run_id, PipelineStage.DIARIZE, "speaker_spans", result.model_dump(mode="json"), result.model_run)
        return result

    def _asr_stage(self, run_id: str, canonical_audio_path: str) -> ASRResult:
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.ASR, "transcript")
        if existing:
            return ASRResult.model_validate(existing)
        result = self.asr.transcribe(canonical_audio_path)
        self.storage.write_json_artifact(run_id, PipelineStage.ASR, "transcript", result.model_dump(mode="json"), result.model_run)
        return result

    def _normalize_stage(self, run_id: str, asr_result: ASRResult) -> str:
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.NORMALIZE, "transcript")
        if existing:
            return str(existing.get("text", ""))
        transcript_text = "\n".join(s.text for s in asr_result.segments).strip()
        self.storage.write_json_artifact(run_id, PipelineStage.NORMALIZE, "transcript", {"text": transcript_text}, self._system_model_run())
        return transcript_text

    def _polish_stage(self, run_id: str, normalized_transcript: str) -> str:
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.POLISH, "polished_transcript")
        if existing:
            return str(existing.get("text", normalized_transcript))

        if not self.polish_config.enable_transcript_polish:
            self.storage.write_json_artifact(run_id, PipelineStage.POLISH, "polished_transcript", {"text": normalized_transcript}, self._system_model_run())
            return normalized_transcript

        out_dir = str(self.artifacts_root_dir / run_id / "polish")
        result = self.polish_service.run(
            transcript=normalized_transcript,
            output_dir=out_dir,
            config=self.polish_config,
            glossary_terms=self.polish_glossary_terms,
        )
        self.storage.write_json_artifact(run_id, PipelineStage.POLISH, "polished_transcript", {"text": result["polished_transcript"]}, self._system_model_run())
        return str(result["polished_transcript"])

    def _summarize_stage(self, run_id: str, transcript_text: str) -> SummarizationResult:
        existing = self.storage.read_latest_json_artifact(run_id, PipelineStage.SUMMARIZE, "meeting_notes")
        if existing:
            return SummarizationResult.model_validate(existing)
        result = self.summarization.summarize(transcript_text)
        self.storage.write_json_artifact(run_id, PipelineStage.SUMMARIZE, "meeting_notes", result.model_dump(mode="json"), result.model_run)
        return result

    def _export_stage(self, run_id: str, asr_result: ASRResult, summary_result: SummarizationResult) -> dict[str, str]:
        transcript_meta = self.storage.read_latest_json_artifact(run_id, PipelineStage.EXPORT, "transcript_pdf")
        summary_meta = self.storage.read_latest_json_artifact(run_id, PipelineStage.EXPORT, "summary_pdf")

        transcript_pdf = str(self.artifacts_root_dir / run_id / "export" / "transcript.pdf")
        summary_pdf = str(self.artifacts_root_dir / run_id / "export" / "summary.pdf")

        if transcript_meta and Path(transcript_meta.get("path", "")).exists():
            transcript_pdf = transcript_meta["path"]
        else:
            transcript_pdf = self.exporter.export_transcript_pdf(asr_result, transcript_pdf)
            self.storage.write_json_artifact(run_id, PipelineStage.EXPORT, "transcript_pdf", {"path": transcript_pdf}, self._system_model_run())

        if summary_meta and Path(summary_meta.get("path", "")).exists():
            summary_pdf = summary_meta["path"]
        else:
            summary_pdf = self.exporter.export_summary_pdf(summary_result, summary_pdf)
            self.storage.write_json_artifact(run_id, PipelineStage.EXPORT, "summary_pdf", {"path": summary_pdf}, self._system_model_run())

        return {"transcript_pdf": transcript_pdf, "summary_pdf": summary_pdf}

    def _align_stage(self, run_id: str) -> None:
        self.storage.write_json_artifact(
            run_id=run_id,
            stage=PipelineStage.ALIGN,
            artifact_type="status",
            payload={"enabled": True, "implemented": False},
            model_run=self._system_model_run(),
        )

    @staticmethod
    def _system_model_run():
        from domain.schemas import ModelRun

        return ModelRun(backend="system", model_name="pipeline", model_version="mvp", config_version="v1")
