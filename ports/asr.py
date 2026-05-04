from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from domain.schemas import ASRResult


class ASRBackendPort(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> ASRResult:
        raise NotImplementedError
