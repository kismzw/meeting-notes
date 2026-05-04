import pytest

from backends.alignment.qwen_aligner import QwenAlignerBackend
from backends.asr.qwen import QwenASRBackend


def test_qwen_asr_stub_raises():
    with pytest.raises(NotImplementedError):
        QwenASRBackend().transcribe("a.wav")


def test_qwen_aligner_stub_raises():
    with pytest.raises(NotImplementedError):
        QwenAlignerBackend().align("a.wav", "text")
