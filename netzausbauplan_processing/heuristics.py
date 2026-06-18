from __future__ import annotations

import re
from collections.abc import Iterable

from netzausbauplan_processing.extraction.data.models import Bottleneck, Evidence, Forecast, Measure, NetworkLevel, ProjectCategory
from netzausbauplan_processing.pdf_reader import PdfPage

YEAR_PATTERN = re.compile(r"\b20(?:2[4-9]|3\d|4[0-5])\b")
MONEY_PATTERN = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>Mio\.?\s*€|Millionen\s*Euro|TEUR|T€|€)", re.I)
KM_PATTERN = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*km\b", re.I)
MVA_PATTERN = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*MVA\b", re.I)
MEASURE_ID_PATTERN = re.compile(r"\b(?:HS|MS|NS|UW|UW\s?[A-Z]|M)[\s-]?\d+[a-z]?\b", re.I)
BOTTLENECK_ID_PATTERN = re.compile(r"\b(?:EP|EG|Engpass)[\s-]?\d+[a-z]?\b", re.I)

MEASURE_KEYWORDS = ("maßnahme", "projektbeschreibung", "inbetriebnahme", "genehmigung", "netzausbau", "kosten")
BOTTLENECK_KEYWORDS = ("engpass", "überlastung", "n-1", "verletzung", "spannungsband", "grenzwert")
FORECAST_KEYWORDS = ("prognose", "photovoltaik", "pv", "wind", "wärmepumpe", "ladepunkt", "speicher", "last")


def extract_measures(pages: list[PdfPage]) -> list[Measure]:
    records: list[Measure] = []
    for page in pages:
        for candidate_text in _candidate_texts(page):
            if _keyword_hits(candidate_text, MEASURE_KEYWORDS) < 2:
                continue
            records.append(
                Measure(
                    measure_id=_first_match(MEASURE_ID_PATTERN, candidate_text),
                    title=_guess_title(candidate_text),
                    description=candidate_text,
                    category=_guess_category(candidate_text),
                    network_level=_guess_network_level(candidate_text),
                    start_year=_first_year_near(candidate_text, ("baubeginn", "beginn", "start")),
                    commissioning_year=_first_year_near(candidate_text, ("inbetriebnahme", "ibn", "fertigstellung")),
                    length_km=_first_number(KM_PATTERN, candidate_text),
                    capacity_change_mva=_first_number(MVA_PATTERN, candidate_text),
                    estimated_cost_eur=_money_to_eur(candidate_text),
                    status=_extract_line_after_label(candidate_text, ("status", "projektstatus")),
                    permit_status=_extract_line_after_label(candidate_text, ("genehmigung", "genehmigungsstand")),
                    alternatives=_extract_line_after_label(candidate_text, ("alternative", "alternativen")),
                    evidence=[Evidence(page=page.page, text=candidate_text[:1200])],
                )
            )
    return _deduplicate_measures(records)


def extract_bottlenecks(pages: list[PdfPage]) -> list[Bottleneck]:
    records: list[Bottleneck] = []
    for page in pages:
        for candidate_text in _candidate_texts(page):
            if _keyword_hits(candidate_text, BOTTLENECK_KEYWORDS) < 2:
                continue
            records.append(
                Bottleneck(
                    bottleneck_id=_first_match(BOTTLENECK_ID_PATTERN, candidate_text),
                    description=candidate_text,
                    network_level=_guess_network_level(candidate_text),
                    first_occurrence_year=_first_year(candidate_text),
                    cause=_guess_cause(candidate_text),
                    evidence=[Evidence(page=page.page, text=candidate_text[:1200])],
                )
            )
    return records


def extract_forecasts(pages: list[PdfPage]) -> list[Forecast]:
    records: list[Forecast] = []
    technology_patterns = {
        "Photovoltaik": re.compile(r"\b(?:photovoltaik|pv)\b", re.I),
        "Wind": re.compile(r"\bwind(?:energie|kraft)?\b", re.I),
        "Speicher": re.compile(r"\bspeicher\b", re.I),
        "Wärmepumpen": re.compile(r"\bwärmepump", re.I),
        "Ladeinfrastruktur": re.compile(r"\b(?:ladepunkt|ladeinfrastruktur|wallbox)\b", re.I),
    }

    value_pattern = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>MW|GW|MVA|GWh|MWh|Stück|Anzahl)\b", re.I)

    for page in pages:
        for candidate_text in _candidate_texts(page):
            if _keyword_hits(candidate_text, FORECAST_KEYWORDS) < 1:
                continue
            for technology, technology_pattern in technology_patterns.items():
                if not technology_pattern.search(candidate_text):
                    continue
                value_match = value_pattern.search(candidate_text)
                records.append(
                    Forecast(
                        technology=technology,
                        year=_first_year(candidate_text),
                        value=_to_float(value_match.group("value")) if value_match else None,
                        unit=value_match.group("unit") if value_match else None,
                        evidence=[Evidence(page=page.page, text=candidate_text[:1200])],
                    )
                )
    return records


def _candidate_texts(page: PdfPage) -> Iterable[str]:
    for block in page.blocks:
        yield _normalize_space(block.text)

    for table in page.tables:
        rows = [" | ".join("" if cell is None else _normalize_space(cell) for cell in row) for row in table]
        yield "\n".join(rows)


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    lower_text = text.lower()
    return sum(keyword in lower_text for keyword in keywords)


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def _first_year(text: str) -> int | None:
    match = YEAR_PATTERN.search(text)
    return int(match.group(0)) if match else None


def _first_year_near(text: str, labels: tuple[str, ...]) -> int | None:
    lower_text = text.lower()
    for label in labels:
        label_index = lower_text.find(label)
        if label_index >= 0:
            window = text[label_index : label_index + 120]
            year = _first_year(window)
            if year is not None:
                return year
    return None


def _first_number(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    return _to_float(match.group("value")) if match else None


def _to_float(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def _money_to_eur(text: str) -> float | None:
    match = MONEY_PATTERN.search(text)
    if not match:
        return None

    value = _to_float(match.group("value"))
    unit = match.group("unit").lower()
    if "mio" in unit or "million" in unit:
        return value * 1_000_000
    if "teur" in unit or "t€" in unit:
        return value * 1_000
    return value


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
    if "ersatzneubau" in lower_text:
        return ProjectCategory.REPLACEMENT
    if "neubau" in lower_text:
        return ProjectCategory.NEW_BUILD
    if "verstärkung" in lower_text or "verstarkung" in lower_text:
        return ProjectCategory.REINFORCEMENT
    if "optimierung" in lower_text:
        return ProjectCategory.OPTIMIZATION
    if "umspannwerk" in lower_text or re.search(r"\buw\b", lower_text):
        return ProjectCategory.TRANSFORMER_STATION
    return ProjectCategory.UNKNOWN


def _guess_title(text: str) -> str | None:
    parts = [part.strip(" |:-") for part in re.split(r"[\n|]", text) if part.strip()]
    return parts[0][:180] if parts else None


def _extract_line_after_label(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        match = re.search(rf"{label}\s*[:|-]?\s*(.{{1,240}})", text, re.I)
        if match:
            return match.group(1).strip()
    return None


def _guess_cause(text: str) -> str | None:
    lower_text = text.lower()
    if "einspeis" in lower_text:
        return "Einspeisung"
    if "last" in lower_text:
        return "Lastzuwachs"
    if "spannung" in lower_text:
        return "Spannungshaltung"
    if "n-1" in lower_text:
        return "N-1-Sicherheit"
    return None


def _deduplicate_measures(measures: list[Measure]) -> list[Measure]:
    seen: set[tuple[str | None, str]] = set()
    deduplicated: list[Measure] = []

    for measure in measures:
        key = (measure.measure_id, measure.description[:200])
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(measure)

    return deduplicated
