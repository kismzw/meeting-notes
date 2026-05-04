from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from domain.enums import PipelineStage
from domain.schemas import ArtifactRecord, ModelRun


class ArtifactStoragePort(ABC):
    @abstractmethod
    def write_json_artifact(
        self,
        run_id: str,
        stage: PipelineStage,
        artifact_type: str,
        payload: dict,
        model_run: ModelRun,
        metadata: Optional[dict[str, str]] = None,
    ) -> ArtifactRecord:
        raise NotImplementedError

    @abstractmethod
    def read_latest_json_artifact(self, run_id: str, stage: PipelineStage, artifact_type: str) -> Optional[dict]:
        raise NotImplementedError
