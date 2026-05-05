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


class PolishConfigModel(BaseModel):
    enable_transcript_polish: bool = True
    backend: str = "ollama"
    model: str = "qwen2.5:14b-instruct"
    topic_hint: str = "horse_racing"
    ollama_url: str = "http://localhost:11434/api/generate"
    apply_auto_only: bool = False
    max_search_queries: int = 12
    max_search_results_per_query: int = 5
    auto_apply_threshold: float = 0.90
    review_threshold: float = 0.70
    reject_threshold: float = 0.70
    local_glossary_terms: list[dict] = Field(default_factory=list)


class Settings(BaseModel):
    app: AppConfig
    pipeline: PipelineConfig
    polishing: PolishConfigModel = Field(default_factory=PolishConfigModel)


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(config_dir: Union[str, Path] = "configs") -> Settings:
    config_dir = Path(config_dir)
    app_data = _read_yaml(config_dir / "app.yaml")
    pipeline_data = _read_yaml(config_dir / "pipeline.yaml")
    polishing_data = _read_yaml(config_dir / "polishing.yaml")
    return Settings(
        app=AppConfig.model_validate(app_data),
        pipeline=PipelineConfig.model_validate(pipeline_data),
        polishing=PolishConfigModel.model_validate(polishing_data),
    )
