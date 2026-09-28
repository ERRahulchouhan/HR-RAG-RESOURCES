"""05 · processor — parse raw binary formats to plain text, once.

    raw/<prefix>/file.pdf|docx|pptx  --parse-->  processed/<prefix>/file.json

Called by the ingestion pipeline (09) so PDFs/DOCX/PPTX are parsed a single
time, not on every vector-store rebuild. document_loader.py (04) then reads
the JSON back. .txt needs no parsing and is handled directly in (04).
"""

import io
import json
import logging
from pathlib import Path

from docx import Document as DocxReader
from pptx import Presentation
from pypdf import PdfReader

from hr_assistant import config
from hr_assistant.document_loader import extract_policy_category

logger = logging.getLogger(__name__)

_RAW_TO_PROCESSED = (
    (config.DATA_DIR, config.PROCESSED_DATA_DIR / "hr-policies", "*"),
    (config.DATA_DIR / "noise", config.PROCESSED_DATA_DIR / "other-data", "*"),
)


def _parse_pdf(raw_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_docx(raw_bytes: bytes) -> str:
    doc = DocxReader(io.BytesIO(raw_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def _parse_pptx(raw_bytes: bytes) -> str:
    prs = Presentation(io.BytesIO(raw_bytes))
    lines = []
    for slide in prs.slides:
        if slide.shapes.title is not None:
            lines.append(slide.shapes.title.text)
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                lines.append(shape.text_frame.text)
    return "\n".join(lines)


_PARSERS = {".pdf": _parse_pdf, ".docx": _parse_docx, ".pptx": _parse_pptx}


def parse_file(path: Path) -> str:
    """Read a local file and return its plain text, dispatching on extension.
    .txt decodes directly; other formats go through the matching parser."""
    ext = path.suffix.lower()
    if ext == ".txt":
        return path.read_text(encoding="utf-8")
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(f"No parser registered for file extension {ext!r} ({path})")
    return parser(path.read_bytes())


def process_raw_to_json() -> int:
    """Parse local raw files and write processed JSON records beside the data.
    Returns how many records were written.

    Each record holds source, policy_category, text, and raw_local_path.
    """
    count = 0
    for raw_dir, processed_dir, pattern in _RAW_TO_PROCESSED:
        for path in sorted(raw_dir.glob(pattern)):
            if not path.is_file() or not path.suffix:
                continue
            text = parse_file(path)
            record = {
                "source": path.name,
                "policy_category": extract_policy_category(text),
                "text": text,
                "raw_local_path": str(path),
            }

            processed_dir.mkdir(parents=True, exist_ok=True)
            processed_path = processed_dir / f"{path.stem}.json"
            processed_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            logger.info("  %s  ->  %s", path, processed_path)
            count += 1

    return count
