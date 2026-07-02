from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel

from netzausbauplan_processing.extraction.data.models import ExtractionResult
from netzausbauplan_processing.pdf_reader import PdfPage, pages_to_jsonable


def write_outputs(result: ExtractionResult, pages: list[PdfPage], output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)

    _write_json(output_directory / "document.json", result.model_dump())
    _write_json(output_directory / "raw_pages.json", pages_to_jsonable(pages))

    _write_csv(output_directory / "measures.csv", result.measures)
    _write_csv(output_directory / "bottlenecks.csv", result.bottlenecks)
    _write_csv(output_directory / "forecasts.csv", result.forecasts)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_csv(path: Path, records: list[BaseModel]) -> None:
    rows = [record.model_dump(mode="json") for record in records]
    dataframe = pd.json_normalize(rows)
    dataframe.to_csv(path, index=False)
