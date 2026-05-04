from __future__ import annotations

from pathlib import Path

from domain.schemas import ASRResult, SummarizationResult


class PDFExportService:
    def export_transcript_pdf(self, asr_result: ASRResult, output_path: str) -> str:
        lines = [
            "Transcript",
            "",
        ]
        for seg in asr_result.segments:
            start = f"{seg.span.start_sec:.2f}"
            end = f"{seg.span.end_sec:.2f}"
            lines.append(f"[{start} - {end}] {seg.text}")
        return self._write_pdf(lines, output_path)

    def export_summary_pdf(self, summary_result: SummarizationResult, output_path: str) -> str:
        notes = summary_result.notes
        lines = [
            "Meeting Summary",
            "",
            "Summary",
            notes.summary or "",
            "",
            "Decisions",
        ]
        lines.extend([f"- {x}" for x in notes.decisions] or ["- (none)"])
        lines.append("")
        lines.append("Action Items")
        lines.extend([f"- {x}" for x in notes.action_items] or ["- (none)"])
        lines.append("")
        lines.append("Open Questions")
        lines.extend([f"- {x}" for x in notes.open_questions] or ["- (none)"])
        lines.append("")
        lines.append("Risks")
        lines.extend([f"- {x}" for x in notes.risks] or ["- (none)"])
        lines.append("")
        lines.append("Clean Transcript")
        lines.append(notes.clean_transcript or "")
        return self._write_pdf(lines, output_path)

    @staticmethod
    def _write_pdf(lines: list[str], output_path: str) -> str:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise RuntimeError("reportlab is required for PDF export. Install with `pip install reportlab`.") from exc

        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        c = canvas.Canvas(str(p), pagesize=A4)
        font_name = "HeiseiMin-W3"
        font_size = 10
        c.setFont(font_name, font_size)

        width, height = A4
        margin = 40
        x = margin
        y = height - margin
        line_height = 14
        max_text_width = width - (margin * 2)

        for raw in lines:
            text = raw if raw is not None else ""
            for paragraph in text.splitlines() or [""]:
                chunks = PDFExportService._wrap_text_by_width(
                    paragraph,
                    font_name=font_name,
                    font_size=font_size,
                    max_width=max_text_width,
                    pdfmetrics=pdfmetrics,
                )
                for chunk in chunks:
                    if y < margin:
                        c.showPage()
                        c.setFont(font_name, font_size)
                        y = height - margin
                    c.drawString(x, y, chunk)
                    y -= line_height
            if text == "":
                if y < margin:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = height - margin
                y -= line_height

        c.save()
        return str(p.resolve())

    @staticmethod
    def _wrap_text_by_width(
        text: str,
        font_name: str,
        font_size: int,
        max_width: float,
        pdfmetrics,
    ) -> list[str]:
        if not text:
            return [""]
        chunks: list[str] = []
        current = ""
        for ch in text:
            candidate = current + ch
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = ch
        if current:
            chunks.append(current)
        return chunks
