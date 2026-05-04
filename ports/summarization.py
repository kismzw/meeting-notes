from abc import ABC, abstractmethod

from domain.schemas import SummarizationResult


class SummarizationBackendPort(ABC):
    @abstractmethod
    def summarize(self, transcript: str) -> SummarizationResult:
        raise NotImplementedError
