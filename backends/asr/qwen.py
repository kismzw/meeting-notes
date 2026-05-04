from __future__ import annotations

from typing import Optional

from ports.asr import ASRBackendPort


class QwenASRBackend(ASRBackendPort):
    def transcribe(self, audio_path: str, language: Optional[str] = None):
        raise NotImplementedError("Qwen ASR backend is intentionally not implemented in MVP")
