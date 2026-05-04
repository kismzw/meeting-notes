import json

from domain.enums import PipelineStage
from domain.schemas import ModelRun
from infrastructure.storage.local_fs import LocalFSArtifactStorage


def test_local_fs_artifact_storage_writes_record(tmp_path):
    storage = LocalFSArtifactStorage(str(tmp_path))
    model_run = ModelRun(backend="b", model_name="m", model_version="1", config_version="v1")

    record = storage.write_json_artifact(
        run_id="run-1",
        stage=PipelineStage.VAD,
        artifact_type="spans",
        payload={"hello": "world"},
        model_run=model_run,
    )

    p = tmp_path / "run-1" / "vad" / "spans"
    files = list(p.glob("*.json"))
    assert len(files) == 1
    assert record.path == str(files[0])
    assert json.loads(files[0].read_text(encoding="utf-8"))["hello"] == "world"
