from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import fitz
from ollama import chat

from netzausbau_extractor.llm_converter import llm_extraction_to_result, parse_llm_payload
from netzausbau_extractor.models import ExtractionResult, LlmExtraction
from netzausbau_extractor.pdf_reader import PdfPage, read_pdf
from netzausbau_extractor.schema import load_extraction_schema
from netzausbau_extractor.writer import write_outputs

SYSTEM_PROMPT = """Extract planning measure rows from this German Netzausbauplan PDF text.
Return JSON matching the schema. Include metadata when visible (network operator, publication year).
Extract summary tables and Maßnahmenplan rows. Do not invent values. Use null when unknown."""


def extract_pdf_text(pdf_path: Path) -> str:
    document = fitz.open(pdf_path)
    return "\n\n".join(page.get_text("text") for page in document)


def extract_with_ollama(
    pdf_path: Path,
    *,
    model: str = "qwen3.6",
) -> tuple[ExtractionResult, list[PdfPage], LlmExtraction]:
    pages = read_pdf(pdf_path)
    pdf_text = extract_pdf_text(pdf_path)
    schema = load_extraction_schema()

    response = chat(
        model=model,
        think=False,
        format=schema,
        messages=[
            {
                "role": "user",
                "content": f"{SYSTEM_PROMPT}\n\nTEXT:\n\n{pdf_text}",
            }
        ],
        options={"temperature": 0, "num_predict": 2**16, "num_ctx": 2**16},
    )

    llm_extraction = parse_llm_payload(json.loads(response["message"]["content"]))
    result = llm_extraction_to_result(
        llm_extraction,
        pdf_path=pdf_path,
        page_count=len(pages),
    )
    return result, pages, llm_extraction


def write_ollama_outputs(
    result: ExtractionResult,
    pages: list[PdfPage],
    llm_extraction: LlmExtraction,
    output_directory: Path,
) -> None:
    write_outputs(result=result, pages=pages, output_directory=output_directory)
    _write_json(output_directory / "llm_extraction.json", llm_extraction.model_dump())


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m netzausbau_extractor.ollama_extractor path/to/plan.pdf")

    pdf_path = Path(sys.argv[1])
    output_directory = Path("output")
    result, pages, llm_extraction = extract_with_ollama(pdf_path)
    write_ollama_outputs(result, pages, llm_extraction, output_directory)


if __name__ == "__main__":
    main()
