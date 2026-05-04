# meeting-notes

A local-first audio transcription and summarization pipeline.

- Layered architecture (`domain` / `ports` / `backends` / `application` / `infrastructure`)
- Backend selection is config-driven
- Every stage persists artifacts to `artifacts/`
- Restartable pipeline (reuses saved artifacts)

## 1. Requirements

- macOS (Apple Silicon recommended)
- Python 3.10+
- Homebrew
- `ffmpeg`
- Ollama (for local summarization with `qwen3:8b`)

## 2. Installation

### 2.1 Install system tools

```bash
brew install ffmpeg ollama
```

### 2.2 Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2.3 Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

## 3. Start Ollama and pull model

### 3.1 Start server

```bash
ollama serve
```

This is a foreground server process and will keep running.

### 3.2 In another terminal, pull model

```bash
ollama pull qwen3:8b
ollama list
```

## 4. Configuration

Main config: `configs/pipeline.yaml`

Typical local setup:
- `vad.name: silero`
- `asr.name: mlx_whisper`
- `summarization.name: local_llm`
- `summarization.model_name: qwen3:8b`
- `diarization.enabled: false`
- `alignment.enabled: false`

## 5. Run the pipeline

```bash
source .venv/bin/activate
python -m application "/absolute/path/to/input.wav"
```

Optional flags:

```bash
python -m application "/path/to/input.wav" --run-id run-001 --config-dir configs --align
```

## 6. Artifacts and outputs

All outputs are saved under `artifacts/<run_id>/`.

Common outputs:
- `ingest/audio_asset/*.json`
- `canonicalize/audio_asset/*.json`
- `canonical/audio.wav`
- `vad/spans/*.json`
- `asr/transcript/*.json`
- `summarize/meeting_notes/*.json`
- `export/transcript.pdf`
- `export/summary.pdf`

## 7. Meeting notes schema

`notes` always includes:
- `summary: string`
- `decisions: string[]`
- `action_items: string[]`
- `open_questions: string[]`
- `risks: string[]`
- `clean_transcript: string`

Rule:
- `decisions`, `action_items`, `open_questions`, and `risks` are included only if explicitly present in the transcript.
- Otherwise they are empty lists.

## 8. Check stage completion

```bash
find artifacts/<run_id> -maxdepth 4 -type f | sort
```

Quick status by stage:

```bash
for s in ingest canonicalize vad diarize asr summarize export align; do
  if [ -d "artifacts/<run_id>/$s" ]; then
    echo "$s: done"
  else
    echo "$s: pending"
  fi
done
```

## 9. Verify GPU usage (Apple Silicon)

### 9.1 Verify MLX device

```bash
source .venv/bin/activate
python - <<'PY'
import mlx.core as mx
print(mx.default_device())
PY
```

If this prints `Device(gpu, 0)`, MLX can use GPU.

### 9.2 Monitor GPU activity during run

```bash
sudo powermetrics --samplers gpu_power -i 1000
```

## 10. Run tests

```bash
source .venv/bin/activate
python -m pytest -q
```

## 11. Troubleshooting

### `ffmpeg` not found

```bash
brew install ffmpeg
```

### `reportlab is required for PDF export`

```bash
source .venv/bin/activate
python -m pip install reportlab
```

### Hugging Face `403 Forbidden` (pyannote)

Occurs when `diarization.enabled: true` without proper access/token.

To continue locally without HF gating, keep:
- `diarization.enabled: false`

### `ollama serve` appears to hang

Expected behavior. It is a long-running server.
Use another terminal for `ollama pull` and pipeline execution.

## 12. Local-only execution notes

Inference runs locally.
Network access may still occur for first-time model downloads.
After model caching, runs are typically local-only.
