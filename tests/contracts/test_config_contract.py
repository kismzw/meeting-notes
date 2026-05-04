from infrastructure.config.settings import load_settings


def test_load_settings_reads_yaml(tmp_path):
    (tmp_path / "app.yaml").write_text("artifacts_dir: ./x\n", encoding="utf-8")
    (tmp_path / "pipeline.yaml").write_text(
        """
config_version: v2
vad:
  name: silero
  model_name: silero-vad
asr:
  name: whisper
  model_name: tiny
summarization:
  name: mock
  model_name: mock
""",
        encoding="utf-8",
    )
    settings = load_settings(tmp_path)
    assert settings.app.artifacts_dir == "./x"
    assert settings.pipeline.config_version == "v2"
    assert settings.pipeline.alignment is None
