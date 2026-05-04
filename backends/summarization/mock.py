from domain.entities import MeetingNotes
from domain.schemas import ModelRun, SummarizationResult
from ports.summarization import SummarizationBackendPort


class MockSummarizationBackend(SummarizationBackendPort):
    def __init__(self, model_name: str, model_version: str, config_version: str):
        self.model_run = ModelRun(
            backend="mock",
            model_name=model_name,
            model_version=model_version,
            config_version=config_version,
        )

    def summarize(self, transcript: str) -> SummarizationResult:
        preview = transcript.strip().replace("\n", " ")[:200]
        notes = MeetingNotes(
            summary=f"[MOCK] Summary: {preview}" if preview else "[MOCK] Empty transcript",
            decisions=[],
            action_items=[],
            open_questions=[],
            risks=[],
            clean_transcript=transcript.strip(),
        )
        return SummarizationResult(notes=notes, model_run=self.model_run)
