from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional

from backends.alignment.qwen_aligner import QwenAlignerBackend
from backends.asr.mlx_whisper import MLXWhisperASRBackend
from backends.asr.qwen import QwenASRBackend
from backends.asr.whisper import WhisperASRBackend
from backends.diarization.pyannote import PyannoteDiarizationBackend
from backends.summarization.local_llm import LocalLLMSummarizationBackend
from backends.summarization.mock import MockSummarizationBackend
from backends.vad.silero import SileroVADBackend
from domain.errors import BackendConfigError, BackendNotFoundError
from infrastructure.config.settings import PipelineConfig
from ports.alignment import AlignmentBackendPort
from ports.asr import ASRBackendPort
from ports.diarization import DiarizationBackendPort
from ports.summarization import SummarizationBackendPort
from ports.vad import VADBackendPort


@dataclass
class BackendRegistry:
    vad: VADBackendPort
    asr: ASRBackendPort
    summarization: SummarizationBackendPort
    diarization: Optional[DiarizationBackendPort] = None
    alignment: Optional[AlignmentBackendPort] = None


def build_backend_registry(config: PipelineConfig) -> BackendRegistry:
    vad_cfg = config.vad
    if vad_cfg.name != "silero" or not vad_cfg.enabled:
        raise BackendConfigError("Only silero VAD is implemented and must be enabled")
    vad = SileroVADBackend(
        model_name=vad_cfg.model_name,
        model_version=vad_cfg.model_version,
        config_version=config.config_version,
        threshold=float(vad_cfg.options.get("threshold", 0.5)),
    )

    asr_cfg = config.asr
    if asr_cfg.name == "whisper" and asr_cfg.enabled:
        asr: ASRBackendPort = WhisperASRBackend(
            model_name=asr_cfg.model_name,
            model_version=asr_cfg.model_version,
            config_version=config.config_version,
            device=str(asr_cfg.options.get("device", "auto")),
            compute_type=str(asr_cfg.options.get("compute_type", "auto")),
        )
    elif asr_cfg.name == "mlx_whisper" and asr_cfg.enabled:
        asr = MLXWhisperASRBackend(
            model_name=asr_cfg.model_name,
            model_version=asr_cfg.model_version,
            config_version=config.config_version,
        )
    elif asr_cfg.name == "qwen" and asr_cfg.enabled:
        asr = QwenASRBackend()
    else:
        raise BackendNotFoundError(f"Unsupported ASR backend: {asr_cfg.name}")

    sum_cfg = config.summarization
    if not sum_cfg.enabled:
        raise BackendConfigError("Summarization backend must be enabled")
    if sum_cfg.name == "mock":
        summarization = MockSummarizationBackend(
            model_name=sum_cfg.model_name,
            model_version=sum_cfg.model_version,
            config_version=config.config_version,
        )
    elif sum_cfg.name == "local_llm":
        summarization = LocalLLMSummarizationBackend(
            model_name=sum_cfg.model_name,
            model_version=sum_cfg.model_version,
            config_version=config.config_version,
            base_url=str(sum_cfg.options.get("base_url", "http://127.0.0.1:11434")),
            timeout_sec=int(sum_cfg.options.get("timeout_sec", 120)),
        )
    else:
        raise BackendNotFoundError(f"Unsupported summarization backend: {sum_cfg.name}")

    diarization = None
    if config.diarization and config.diarization.enabled:
        dcfg = config.diarization
        if dcfg.name != "pyannote":
            raise BackendNotFoundError(f"Unsupported diarization backend: {dcfg.name}")
        diarization = PyannoteDiarizationBackend(
            model_name=dcfg.model_name,
            model_version=dcfg.model_version,
            config_version=config.config_version,
            hf_token=dcfg.options.get("hf_token") or os.getenv("HF_TOKEN"),
        )

    alignment = None
    if config.alignment and config.alignment.enabled:
        acfg = config.alignment
        if acfg.name == "qwen_aligner":
            alignment = QwenAlignerBackend()
        else:
            raise BackendNotFoundError(f"Unsupported alignment backend: {acfg.name}")

    return BackendRegistry(vad=vad, asr=asr, diarization=diarization, alignment=alignment, summarization=summarization)
