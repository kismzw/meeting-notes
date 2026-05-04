from pathlib import Path

from domain.enums import PipelineStage


def artifact_path(root: Path, run_id: str, stage: PipelineStage, artifact_type: str, filename: str) -> Path:
    return root / run_id / stage.value / artifact_type / filename
