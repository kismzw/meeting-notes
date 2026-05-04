from domain.entities import MeetingNotes, TranscriptSegment
from domain.schemas import ASRResult, ModelRun, SummarizationResult
from domain.value_objects import TimeRange


def test_pdf_export_service_creates_pdf_files(tmp_path):
    from application.services.export_pdf import PDFExportService

    exporter = PDFExportService()
    asr = ASRResult(
        segments=[TranscriptSegment(segment_id="s1", span=TimeRange(start_sec=0, end_sec=1), text="こんにちは")],
        language="ja",
        model_run=ModelRun(backend="asr", model_name="m", model_version="1", config_version="v1"),
    )
    summary = SummarizationResult(
        notes=MeetingNotes(
            summary="要約",
            decisions=[],
            action_items=[],
            open_questions=[],
            risks=[],
            clean_transcript="こんにちは",
        ),
        model_run=ModelRun(backend="sum", model_name="m", model_version="1", config_version="v1"),
    )

    transcript_pdf = exporter.export_transcript_pdf(asr, str(tmp_path / "t.pdf"))
    summary_pdf = exporter.export_summary_pdf(summary, str(tmp_path / "s.pdf"))

    assert (tmp_path / "t.pdf").exists()
    assert (tmp_path / "s.pdf").exists()
    assert transcript_pdf.endswith("t.pdf")
    assert summary_pdf.endswith("s.pdf")


def test_wrap_text_by_width_does_not_exceed_limit():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    from application.services.export_pdf import PDFExportService

    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
    chunks = PDFExportService._wrap_text_by_width(
        "これはとても長い文章です。" * 20,
        font_name="HeiseiMin-W3",
        font_size=10,
        max_width=200,
        pdfmetrics=pdfmetrics,
    )
    assert chunks
    assert all(pdfmetrics.stringWidth(c, "HeiseiMin-W3", 10) <= 200 for c in chunks)
