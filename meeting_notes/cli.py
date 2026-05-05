from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.services.polish_web_llm import PolishWebLLMConfig, PolishWebLLMService


def _load_json(path: str | None):
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_transcript(input_path: str | None, transcript_file: str | None) -> str:
    if transcript_file:
        return Path(transcript_file).read_text(encoding="utf-8").strip()
    if not input_path:
        raise RuntimeError("Either --input or --transcript-file is required")
    data = _load_json(input_path)
    if isinstance(data, dict) and "text" in data:
        return str(data["text"]).strip()
    if isinstance(data, dict) and "segments" in data:
        return "\n".join(str(s.get("text", "")).strip() for s in data["segments"] if s.get("text")).strip()
    raise RuntimeError("Unsupported transcript input schema")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="meeting_notes CLI")
    sub = p.add_subparsers(dest="command", required=True)

    x = sub.add_parser("polish-web-llm", help="Run web-search + local-llm span correction")
    x.add_argument("--input", default=None, help="normalized transcript JSON")
    x.add_argument("--transcript-file", default=None, help="plain text transcript")
    x.add_argument("--output-dir", required=True)
    x.add_argument("--backend", default="ollama")
    x.add_argument("--model", required=True)
    x.add_argument("--topic-hint", default="general")
    x.add_argument("--apply-auto-only", action="store_true")
    x.add_argument("--auto-apply-threshold", type=float, default=0.90)
    x.add_argument("--review-threshold", type=float, default=0.70)
    x.add_argument("--candidate-terms", default=None, help="optional JSON file")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.command != "polish-web-llm":
        raise RuntimeError(f"Unknown command: {args.command}")

    transcript = _load_transcript(args.input, args.transcript_file)
    candidate_terms_raw = _load_json(args.candidate_terms) if args.candidate_terms else None
    glossary_terms: list[str] = []
    if isinstance(candidate_terms_raw, list):
        glossary_terms = [str(x) for x in candidate_terms_raw]
    elif isinstance(candidate_terms_raw, dict):
        glossary_terms = [str(x) for x in candidate_terms_raw.get("terms", [])]

    config = PolishWebLLMConfig(
        backend=args.backend,
        model=args.model,
        topic_hint=args.topic_hint,
        auto_apply_threshold=args.auto_apply_threshold,
        review_threshold=args.review_threshold,
        apply_auto_only=args.apply_auto_only,
    )
    service = PolishWebLLMService()
    result = service.run(
        transcript=transcript,
        output_dir=args.output_dir,
        config=config,
        glossary_terms=glossary_terms,
    )
    print(json.dumps({"topic": result["topic"], "num_corrections": len(result["corrections"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
