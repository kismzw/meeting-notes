from __future__ import annotations

from pathlib import Path

from domain.entities import AudioAsset


class IngestService:
    def ingest_local_path(self, source_path: str) -> AudioAsset:
        p = Path(source_path)
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {source_path}")
        return AudioAsset(source_path=str(p.resolve()))
