from __future__ import annotations

import re
from pathlib import Path

from netzausbauplan_processing.heuristics import extract_bottlenecks, extract_forecasts, extract_measures
from netzausbauplan_processing.llm_normalizer import normalize_with_llm
from netzausbauplan_processing.extraction.data.models import DocumentMetadata, ExtractionResult
from netzausbauplan_processing.pdf_reader import PdfPage, read_pdf


def extract_netzausbauplan(pdf_path: Path, use_llm: bool = False) -> tuple[ExtractionResult, list[PdfPage]]:
    pages = read_pdf(pdf_path)
    metadata = _extract_metadata(pdf_path, pages)

    result = ExtractionResult(
        metadata=metadata,
        measures=extract_measures(pages),
        bottlenecks=extract_bottlenecks(pages),
        forecasts=extract_forecasts(pages),
        diagnostics={"pages_with_tables": [page.page for page in pages if page.tables]},
    )

    if use_llm:
        result = normalize_with_llm(result)

    return result, pages


def _extract_metadata(pdf_path: Path, pages: list[PdfPage]) -> DocumentMetadata:
    first_text = "\n".join(page.text for page in pages[:5])
    all_text = "\n".join(page.text for page in pages)

    return DocumentMetadata(
        source_pdf=str(pdf_path),
        page_count=len(pages),
        network_operator=_guess_operator(first_text),
        publication_year=_guess_publication_year(first_text),
        legal_basis=_guess_legal_basis(all_text),
        planning_years=sorted({int(year) for year in re.findall(r"\b20(?:2[4-9]|3\d|4[0-5])\b", all_text)}),
    )


def _guess_operator(text: str) -> str | None:
    patterns = [
        r"enercity\s+Netz\s+GmbH",
        r"Bayernwerk\s+Netz\s+GmbH",
        r"LEW\s+Verteilnetz\s+GmbH",
        r"Netze\s+BW\s+GmbH",
        r"Westnetz\s+GmbH",
        r"Avacon\s+Netz\s+GmbH",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(0)
    return None


def _guess_publication_year(text: str) -> int | None:
    years = [int(year) for year in re.findall(r"\b20(?:2[4-9]|3\d|4[0-5])\b", text)]
    return min(years) if years else None


def _guess_legal_basis(text: str) -> str | None:
    if re.search(r"§\s*14d\s*EnWG", text, re.I):
        return "§ 14d EnWG"
    return None
