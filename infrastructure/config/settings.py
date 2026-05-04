from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator


class BackendChoice(BaseModel):
    name: str
    model_name: str
    model_version: str = "unknown"
    enabled: bool = True
    options: dict = Field(default_factory=dict)

    @field_validator("model_version", mode="before")
    @classmethod
    def _coerce_model_version_to_string(cls, value):
        return str(value)


class PipelineConfig(BaseModel):
    config_version: str = "v1"
    vad: BackendChoice
    asr: BackendChoice
    diarization: Optional[BackendChoice] = None
    alignment: Optional[BackendChoice] = None
    summarization: BackendChoice


class AppConfig(BaseModel):
    artifacts_dir: str = "./artifacts"


class Settings(BaseModel):
    app: AppConfig
    pipeline: PipelineConfig


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(config_dir: Union[str, Path] = "configs") -> Settings:
    config_dir = Path(config_dir)
    app_data = _read_yaml(config_dir / "app.yaml")
    pipeline_data = _read_yaml(config_dir / "pipeline.yaml")
    return Settings(app=AppConfig.model_validate(app_data), pipeline=PipelineConfig.model_validate(pipeline_data))
