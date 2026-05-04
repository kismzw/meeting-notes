from abc import ABC, abstractmethod

from domain.schemas import VADResult


class VADBackendPort(ABC):
    @abstractmethod
    def detect(self, audio_path: str) -> VADResult:
        raise NotImplementedError
