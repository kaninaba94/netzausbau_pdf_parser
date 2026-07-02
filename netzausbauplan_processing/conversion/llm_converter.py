from __future__ import annotations

import re
from pathlib import Path

from netzausbau_extractor.extraction.data.models import (
    DocumentMetadata,
    ExtractionResult,
    LlmExtraction,
    LlmMeasureRow,
    Measure,
    NetworkLevel,
    ProjectCategory,
)

YEAR_PATTERN = re.compile(r"\b20(?:2[4-9]|3\d|4[0-5])\b")


def parse_llm_payload(raw: object) -> LlmExtraction:
    if isinstance(raw, list):
        return LlmExtraction(measures=[LlmMeasureRow.model_validate(item) for item in raw])
    if not isinstance(raw, dict):
        raise TypeError(f"Expected JSON object or array, got {type(raw).__name__}")
    return LlmExtraction.model_validate(raw)


def llm_extraction_to_result(
    extraction: LlmExtraction,
    *,
    pdf_path: Path,
    page_count: int,
) -> ExtractionResult:
    metadata = DocumentMetadata(
        source_pdf=str(pdf_path),
        page_count=page_count,
        network_operator=extraction.metadata.network_operator if extraction.metadata else None,
        publication_year=extraction.metadata.publication_year if extraction.metadata else None,
    )

    return ExtractionResult(
        metadata=metadata,
        measures=[_measure_from_row(row) for row in extraction.measures],
        diagnostics={"extractor": "ollama", "schema": "extraction.schema.json"},
    )


def _measure_from_row(row: LlmMeasureRow) -> Measure:
    combined = f"{row.measure_type} {row.asset_type} {row.timeframe}"
    quantity_unit = row.quantity_unit.strip().lower()

    return Measure(
        title=row.measure_type,
        description=_row_description(row),
        category=_guess_category(combined),
        network_level=_guess_network_level(combined),
        affected_assets=[row.asset_type],
        start_year=_first_year(row.timeframe),
        commissioning_year=_last_year(row.timeframe),
        length_km=row.quantity if _is_length_unit(quantity_unit) else None,
        capacity_change_mva=row.quantity if quantity_unit == "mva" else None,
        estimated_cost_eur=_cost_eur(row),
    )


def _row_description(row: LlmMeasureRow) -> str:
    return f"{row.timeframe}; {row.quantity} {row.quantity_unit}; {row.asset_type}"


def _cost_eur(row: LlmMeasureRow) -> float | None:
    if row.estimated_cost_eur is not None:
        return row.estimated_cost_eur
    unit = row.quantity_unit.strip().lower()
    if unit in {"eur", "€"}:
        return row.quantity
    return None


def _is_length_unit(unit: str) -> bool:
    return unit in {"km", "m"}


def _first_year(text: str) -> int | None:
    match = YEAR_PATTERN.search(text)
    return int(match.group(0)) if match else None


def _last_year(text: str) -> int | None:
    years = [int(year) for year in YEAR_PATTERN.findall(text)]
    return years[-1] if years else None


def _guess_network_level(text: str) -> NetworkLevel:
    lower_text = text.lower()
    if "höchstspannung" in lower_text:
        return NetworkLevel.EHV
    if "hochspannung" in lower_text or re.search(r"\bhs\b", lower_text):
        return NetworkLevel.HV
    if "mittelspannung" in lower_text or re.search(r"\bms\b", lower_text):
        return NetworkLevel.MV
    if "niederspannung" in lower_text or re.search(r"\bns\b", lower_text):
        return NetworkLevel.LV
    return NetworkLevel.UNKNOWN


def _guess_category(text: str) -> ProjectCategory:
    lower_text = text.lower()
    if "ersatzneubau" in lower_text or "ersatz(neubau)" in lower_text:
        return ProjectCategory.REPLACEMENT
    if "neubau" in lower_text:
        return ProjectCategory.NEW_BUILD
    if "verstärkung" in lower_text or "verstarkung" in lower_text:
        return ProjectCategory.REINFORCEMENT
    if "optimierung" in lower_text:
        return ProjectCategory.OPTIMIZATION
    if "umspannwerk" in lower_text or "umspannanlage" in lower_text or re.search(r"\buw\b", lower_text):
        return ProjectCategory.TRANSFORMER_STATION
    return ProjectCategory.UNKNOWN
