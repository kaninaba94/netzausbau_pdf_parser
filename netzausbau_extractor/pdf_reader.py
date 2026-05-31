from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
import pdfplumber
from pydantic import BaseModel


class TextBlock(BaseModel):
    page: int
    bbox: tuple[float, float, float, float]
    text: str


class PdfPage(BaseModel):
    page: int
    text: str
    blocks: list[TextBlock]
    tables: list[list[list[str | None]]]


def read_pdf(pdf_path: Path) -> list[PdfPage]:
    fitz_document = fitz.open(pdf_path)
    table_pages = _extract_tables(pdf_path)
    pages: list[PdfPage] = []

    for page_index, fitz_page in enumerate(fitz_document, start=1):
        blocks = [
            TextBlock(
                page=page_index,
                bbox=(float(block[0]), float(block[1]), float(block[2]), float(block[3])),
                text=str(block[4]).strip(),
            )
            for block in fitz_page.get_text("blocks")
            if len(block) >= 5 and str(block[4]).strip()
        ]

        pages.append(
            PdfPage(
                page=page_index,
                text=fitz_page.get_text("text"),
                blocks=blocks,
                tables=table_pages.get(page_index, []),
            )
        )

    return pages


def _extract_tables(pdf_path: Path) -> dict[int, list[list[list[str | None]]]]:
    tables_by_page: dict[int, list[list[list[str | None]]]] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            raw_tables: list[list[list[str | None]]] = []
            for table in page.extract_tables():
                if table and len(table) >= 2:
                    raw_tables.append(table)
            tables_by_page[page_index] = raw_tables

    return tables_by_page


def pages_to_jsonable(pages: list[PdfPage]) -> list[dict[str, Any]]:
    return [page.model_dump() for page in pages]
