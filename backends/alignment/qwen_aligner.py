from __future__ import annotations

from typing import Optional

from ports.alignment import AlignmentBackendPort


class QwenAlignerBackend(AlignmentBackendPort):
    def align(self, audio_path: str, text: str, language: Optional[str] = None):
        raise NotImplementedError("Qwen aligner backend is intentionally not implemented in MVP")
