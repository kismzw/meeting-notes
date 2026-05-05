from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from application.orchestrators.transcription_pipeline import TranscriptionPipeline
from application.services.polish_web_llm import PolishWebLLMConfig
from backends.registry import build_backend_registry
from infrastructure.config.settings import load_settings
from infrastructure.storage.local_fs import LocalFSArtifactStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run meeting transcription pipeline")
    parser.add_argument("source_audio_path", help="Path to input audio/video file")
    parser.add_argument("--config-dir", default="configs", help="Directory containing app.yaml and pipeline.yaml")
    parser.add_argument("--run-id", default=None, help="Run identifier; default is UTC timestamp")
    parser.add_argument("--align", action="store_true", help="Persist alignment stage status artifact")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = load_settings(args.config_dir)
    registry = build_backend_registry(settings.pipeline)
    storage = LocalFSArtifactStorage(settings.app.artifacts_dir)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")

    glossary_terms = [str(x.get("canonical", "")).strip() for x in settings.polishing.local_glossary_terms if isinstance(x, dict) and str(x.get("canonical", "")).strip()]

    pipeline = TranscriptionPipeline(
        storage=storage,
        artifacts_root_dir=settings.app.artifacts_dir,
        vad=registry.vad,
        diarization=registry.diarization,
        asr=registry.asr,
        summarization=registry.summarization,
        polish_config=PolishWebLLMConfig(
            enable_transcript_polish=settings.polishing.enable_transcript_polish,
            backend=settings.polishing.backend,
            model=settings.polishing.model,
            topic_hint=settings.polishing.topic_hint,
            auto_apply_threshold=settings.polishing.auto_apply_threshold,
            review_threshold=settings.polishing.review_threshold,
            apply_auto_only=settings.polishing.apply_auto_only,
            max_search_queries=settings.polishing.max_search_queries,
            max_search_results_per_query=settings.polishing.max_search_results_per_query,
            ollama_url=settings.polishing.ollama_url,
        ),
        polish_glossary_terms=glossary_terms,
    )
    result = pipeline.run(run_id=run_id, source_audio_path=args.source_audio_path, align_enabled=args.align)

    out = {
        "run_id": run_id,
        "artifacts_dir": settings.app.artifacts_dir,
        "canonical_audio_path": result["canonicalize"].canonical_path,
        "num_vad_spans": len(result["vad"].spans),
        "num_asr_segments": len(result["asr"].segments),
        "transcript_pdf": result["export"]["transcript_pdf"],
        "summary_pdf": result["export"]["summary_pdf"],
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
