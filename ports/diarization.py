from abc import ABC, abstractmethod

from domain.schemas import DiarizationResult


class DiarizationBackendPort(ABC):
    @abstractmethod
    def diarize(self, audio_path: str) -> DiarizationResult:
        raise NotImplementedError
