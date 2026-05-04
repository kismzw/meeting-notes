from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backends.registry import build_backend_registry
from domain.enums import PipelineStage
from infrastructure.config.settings import load_settings
from infrastructure.storage.local_fs import LocalFSArtifactStorage

router = APIRouter(tags=["meetings"])


class RunMeetingRequest(BaseModel):
    source_audio_path: str
    run_id: str | None = None
    config_dir: str = "configs"
    align: bool = False


_JOB_LOCK = Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _artifacts_root(config_dir: str = "configs") -> Path:
    settings = load_settings(config_dir)
    return Path(settings.app.artifacts_dir)


def _run_dir(run_id: str, config_dir: str = "configs") -> Path:
    return _artifacts_root(config_dir) / run_id


def _latest_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    files = sorted(path.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _list_stage_files(run_path: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for stage in ["ingest", "canonicalize", "vad", "diarize", "asr", "summarize", "export", "align"]:
        stage_path = run_path / stage
        if stage_path.exists():
            out[stage] = sorted([str(p.relative_to(run_path)) for p in stage_path.rglob("*") if p.is_file()])
    return out


def _job_status_payload(job_id: str) -> dict[str, Any]:
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

    process: subprocess.Popen | None = job.get("process")
    status = job["status"]
    return_code = job.get("return_code")

    if process is not None and status == "running":
        rc = process.poll()
        if rc is not None:
            status = "completed" if rc == 0 else "failed"
            with _JOB_LOCK:
                job["status"] = status
                job["return_code"] = rc
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
                return_code = rc

    return {
        "job_id": job_id,
        "status": status,
        "run_id": job["run_id"],
        "source_audio_path": job["source_audio_path"],
        "created_at": job["created_at"],
        "completed_at": job.get("completed_at"),
        "return_code": return_code,
    }


@router.post("/jobs")
def create_job(req: RunMeetingRequest) -> dict[str, Any]:
    run_id = req.run_id or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    cmd = [
        sys.executable,
        "-m",
        "application",
        req.source_audio_path,
        "--run-id",
        run_id,
        "--config-dir",
        req.config_dir,
    ]
    if req.align:
        cmd.append("--align")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parents[2]),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"failed to start job: {exc}") from exc

    job_id = str(uuid.uuid4())
    with _JOB_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "run_id": run_id,
            "source_audio_path": req.source_audio_path,
            "status": "running",
            "process": proc,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "return_code": None,
        }
    return {"job_id": job_id, "run_id": run_id, "status": "running"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    return _job_status_payload(job_id)


@router.get("/meetings")
def list_meetings(config_dir: str = "configs") -> list[dict[str, Any]]:
    root = _artifacts_root(config_dir)
    if not root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for p in sorted([x for x in root.iterdir() if x.is_dir() and x.name.startswith("run-")], reverse=True):
        stages = [d.name for d in p.iterdir() if d.is_dir()]
        runs.append(
            {
                "run_id": p.name,
                "stages": sorted(stages),
                "updated_at": p.stat().st_mtime,
            }
        )
    return runs


@router.get("/meetings/{run_id}")
def get_meeting(run_id: str, config_dir: str = "configs") -> dict[str, Any]:
    p = _run_dir(run_id, config_dir)
    if not p.exists():
        raise HTTPException(status_code=404, detail="meeting run not found")
    return {
        "run_id": run_id,
        "artifacts": _list_stage_files(p),
        "canonical_audio": str((p / "canonical" / "audio.wav")) if (p / "canonical" / "audio.wav").exists() else None,
    }


@router.get("/meetings/{run_id}/transcript")
def get_transcript(run_id: str, config_dir: str = "configs") -> dict[str, Any]:
    data = _latest_json(_run_dir(run_id, config_dir) / "asr" / "transcript")
    if data is None:
        raise HTTPException(status_code=404, detail="transcript not found")
    return data


@router.get("/meetings/{run_id}/notes")
def get_notes(run_id: str, config_dir: str = "configs") -> dict[str, Any]:
    data = _latest_json(_run_dir(run_id, config_dir) / "summarize" / "meeting_notes")
    if data is None:
        raise HTTPException(status_code=404, detail="notes not found")
    return data


@router.post("/meetings/{run_id}/actions/rerun-summary")
def rerun_summary(run_id: str, config_dir: str = "configs") -> dict[str, str]:
    transcript_data = _latest_json(_run_dir(run_id, config_dir) / "asr" / "transcript")
    if transcript_data is None:
        raise HTTPException(status_code=404, detail="transcript not found")

    transcript_text = "\n".join(seg.get("text", "") for seg in transcript_data.get("segments", []))
    settings = load_settings(config_dir)
    registry = build_backend_registry(settings.pipeline)
    summary = registry.summarization.summarize(transcript_text)

    storage = LocalFSArtifactStorage(settings.app.artifacts_dir)
    storage.write_json_artifact(
        run_id=run_id,
        stage=PipelineStage.SUMMARIZE,
        artifact_type="meeting_notes",
        payload=summary.model_dump(mode="json"),
        model_run=summary.model_run,
    )
    return {"status": "ok"}


@router.get("/meetings/{run_id}/export")
def export_meeting(run_id: str, format: str = Query("markdown", pattern="^(markdown|json)$"), config_dir: str = "configs"):
    transcript = _latest_json(_run_dir(run_id, config_dir) / "asr" / "transcript")
    notes = _latest_json(_run_dir(run_id, config_dir) / "summarize" / "meeting_notes")
    if transcript is None or notes is None:
        raise HTTPException(status_code=404, detail="required artifacts not found")

    if format == "json":
        return {"transcript": transcript, "notes": notes}

    n = notes.get("notes", {})
    md = []
    md.append("# Meeting Notes")
    md.append("")
    md.append("## Summary")
    md.append(n.get("summary", ""))
    md.append("")
    md.append("## Decisions")
    for item in n.get("decisions", []) or ["(none)"]:
        md.append(f"- {item}")
    md.append("")
    md.append("## Action Items")
    for item in n.get("action_items", []) or ["(none)"]:
        md.append(f"- {item}")
    md.append("")
    md.append("## Open Questions")
    for item in n.get("open_questions", []) or ["(none)"]:
        md.append(f"- {item}")
    md.append("")
    md.append("## Risks")
    for item in n.get("risks", []) or ["(none)"]:
        md.append(f"- {item}")
    md.append("")
    md.append("## Transcript")
    for seg in transcript.get("segments", []):
        md.append(f"- [{seg['span']['start_sec']:.2f}-{seg['span']['end_sec']:.2f}] {seg.get('text', '')}")

    return PlainTextResponse("\n".join(md), media_type="text/markdown")
