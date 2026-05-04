from __future__ import annotations

import subprocess
from shutil import which
from pathlib import Path

from domain.entities import AudioAsset


class CanonicalizeService:
    def to_canonical_wav(self, asset: AudioAsset, output_path: str) -> AudioAsset:
        ffmpeg_bin = which("ffmpeg")
        if ffmpeg_bin is None:
            raise RuntimeError(
                "ffmpeg is required for canonicalization but was not found on PATH. "
                "Install ffmpeg (e.g. `brew install ffmpeg`) and retry."
            )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            asset.source_path,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"ffmpeg canonicalization failed: {stderr}") from exc
        return AudioAsset(
            source_path=asset.source_path,
            canonical_path=str(out.resolve()),
            sample_rate_hz=16000,
            channels=1,
            format="wav",
        )
