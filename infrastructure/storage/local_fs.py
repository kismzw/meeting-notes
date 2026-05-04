from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from domain.enums import PipelineStage
from domain.schemas import ArtifactRecord, ModelRun
from infrastructure.storage.artifact_paths import artifact_path
from ports.storage import ArtifactStoragePort


class LocalFSArtifactStorage(ArtifactStoragePort):
    def __init__(self, root_dir: str):
        self.root = Path(root_dir)

    def write_json_artifact(
        self,
        run_id: str,
        stage: PipelineStage,
        artifact_type: str,
        payload: dict,
        model_run: ModelRun,
        metadata: Optional[dict[str, str]] = None,
    ) -> ArtifactRecord:
        ts = datetime.now(timezone.utc)
        filename = f"{ts.strftime('%Y%m%dT%H%M%SZ')}.json"
        path = artifact_path(self.root, run_id, stage, artifact_type, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return ArtifactRecord(
            run_id=run_id,
            stage=stage,
            artifact_type=artifact_type,
            path=str(path),
            model_run=model_run,
            created_at_utc=ts.isoformat(),
            metadata=metadata or {},
        )

    def read_latest_json_artifact(self, run_id: str, stage: PipelineStage, artifact_type: str) -> Optional[dict]:
        directory = self.root / run_id / stage.value / artifact_type
        if not directory.exists():
            return None
        files = sorted(directory.glob("*.json"))
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))
