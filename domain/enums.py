from enum import Enum


class PipelineStage(str, Enum):
    INGEST = "ingest"
    CANONICALIZE = "canonicalize"
    QUALITY_ANALYZE = "quality_analyze"
    VAD = "vad"
    DIARIZE = "diarize"
    SEGMENT = "segment"
    ASR = "asr"
    ALIGN = "align"
    NORMALIZE = "normalize"
    SUMMARIZE = "summarize"
    EXPORT = "export"
