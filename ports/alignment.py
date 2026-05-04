from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from domain.schemas import AlignmentResult


class AlignmentBackendPort(ABC):
    @abstractmethod
    def align(self, audio_path: str, text: str, language: Optional[str] = None) -> AlignmentResult:
        raise NotImplementedError
