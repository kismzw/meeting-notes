from __future__ import annotations

import json
from typing import Any
from urllib import request

from domain.entities import MeetingNotes
from domain.schemas import ModelRun, SummarizationResult
from ports.summarization import SummarizationBackendPort


class LocalLLMSummarizationBackend(SummarizationBackendPort):
    def __init__(
        self,
        model_name: str,
        model_version: str,
        config_version: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout_sec: int = 120,
    ):
        self.model_run = ModelRun(
            backend="local_llm",
            model_name=model_name,
            model_version=model_version,
            config_version=config_version,
        )
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def summarize(self, transcript: str) -> SummarizationResult:
        transcript = transcript.strip()
        if not transcript:
            notes = MeetingNotes(
                summary="",
                decisions=[],
                action_items=[],
                open_questions=[],
                risks=[],
                clean_transcript="",
            )
            return SummarizationResult(notes=notes, model_run=self.model_run)

        prompt = (
            "You are a meeting-notes assistant. Summarize the transcript in Japanese. "
            "Return strict JSON only with keys: summary (string), decisions (array of strings), "
            "action_items (array of strings), open_questions (array of strings), "
            "risks (array of strings), clean_transcript (string). No markdown. "
            "Do not invent decisions or action items. "
            "Include a decision or action item only when it is explicitly stated in the transcript. "
            "If none are explicitly stated, return an empty list for that field. "
            "If open questions are not explicitly stated, return an empty list. "
            "If risks are not explicitly stated, return an empty list. "
            "clean_transcript must be a cleaned but faithful transcript with no added facts.\n\n"
            f"Transcript:\n{transcript}"
        )
        raw = self._generate(prompt)
        notes = self._parse_notes(raw, transcript)
        return SummarizationResult(notes=notes, model_run=self.model_run)

    def _generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_run.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        req = request.Request(
            url=f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_sec) as resp:
                body = resp.read().decode("utf-8")
        except Exception as exc:
            raise RuntimeError(f"Local LLM call failed: {exc}") from exc

        try:
            parsed = json.loads(body)
            return str(parsed.get("response", ""))
        except Exception as exc:
            raise RuntimeError(f"Invalid response from local LLM endpoint: {exc}") from exc

    @staticmethod
    def _parse_notes(raw: str, transcript: str) -> MeetingNotes:
        try:
            data: dict[str, Any] = json.loads(raw)
            summary = str(data.get("summary", "")).strip()
            decisions_raw = data.get("decisions", [])
            actions_raw = data.get("action_items", [])
            open_questions_raw = data.get("open_questions", [])
            risks_raw = data.get("risks", [])
            clean_transcript = str(data.get("clean_transcript", transcript)).strip()
            decisions = [
                str(x).strip()
                for x in decisions_raw
                if str(x).strip() and str(x).strip() in transcript
            ]
            action_items = [
                str(x).strip()
                for x in actions_raw
                if str(x).strip() and str(x).strip() in transcript
            ]
            open_questions = [
                str(x).strip()
                for x in open_questions_raw
                if str(x).strip() and str(x).strip() in transcript
            ]
            risks = [
                str(x).strip()
                for x in risks_raw
                if str(x).strip() and str(x).strip() in transcript
            ]
            return MeetingNotes(
                summary=summary,
                decisions=decisions,
                action_items=action_items,
                open_questions=open_questions,
                risks=risks,
                clean_transcript=clean_transcript if clean_transcript else transcript,
            )
        except Exception:
            # Fallback when model doesn't strictly follow the JSON contract.
            cleaned = raw.strip()
            return MeetingNotes(
                summary=cleaned,
                decisions=[],
                action_items=[],
                open_questions=[],
                risks=[],
                clean_transcript=transcript,
            )
