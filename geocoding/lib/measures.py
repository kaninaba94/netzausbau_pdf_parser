from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Hashable

import numpy as np
import pandas as pd
from rapidfuzz import fuzz


ASSET_TYPES = ("transformer_station", "power_line")
LABEL_KEYS = (
    "label:asset_type",
    "label:existing",
    "label:easy_to_geocode",
    "label:location_clues",
    "label:osm_id",
)


def collect_raw_measures_dfs_from_csvs(root_path: Path | str) -> list[pd.DataFrame]:
    root_path = Path(root_path)
    measures_dfs: list[pd.DataFrame] = []
    for csv_path in sorted(root_path.rglob("*.csv")):
        measures_df = pd.read_csv(csv_path)
        measures_df["source_file"] = str(csv_path).split("output/")[-1]
        measures_dfs.append(measures_df)
    return measures_dfs


def get_random_measure(measures_dfs: list[pd.DataFrame]) -> pd.Series:
    import random

    df = random.choice(measures_dfs)
    row_idx = random.choice(range(df.shape[0]))
    return df.iloc[row_idx]


def measure_row_hash(row: pd.Series) -> int:
    return int(pd.util.hash_pandas_object(row).sum())


def measure_to_jsonable(measure: pd.Series) -> dict[Hashable, Any]:
    return {k: int(v) if isinstance(v, np.integer) else v for k, v in measure.items()}


def load_labelled_measures(path: Path | str) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


def save_labelled_measures(path: Path | str, measures: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(measures, f, ensure_ascii=False, indent=2)


def labelled_hashes(measures: list[dict[str, Any]]) -> set[int]:
    return {int(m["measure_row_hash"]) for m in measures if "measure_row_hash" in m}


def default_search_columns(columns: list[str]) -> list[str]:
    keywords = ("maßnahme", "projektbeschreibung", "betriebsmittel", "uw", "objekt")
    picked = [c for c in columns if any(k in c.lower().replace("\n", " ") for k in keywords)]
    return picked or list(columns)[: min(3, len(columns))]


def filter_by_regex(
    df: pd.DataFrame,
    columns: list[str],
    pattern: str,
    *,
    case: bool = False,
) -> pd.DataFrame:
    if not pattern or not columns:
        return df
    re.compile(pattern)  # validate early
    mask = pd.Series(False, index=df.index)
    for col in columns:
        if col not in df.columns:
            continue
        series = df[col].fillna("").astype(str).str.replace(r"\s+", " ", regex=True)
        mask |= series.str.contains(pattern, case=case, regex=True, na=False)
    return df.loc[mask]


def filter_by_rapidfuzz(
    df: pd.DataFrame,
    columns: list[str],
    query: str,
    *,
    score_cutoff: int = 70,
) -> pd.DataFrame:
    if not query.strip() or not columns:
        return df
    present = [c for c in columns if c in df.columns]
    if not present:
        return df.iloc[0:0]

    haystacks = (
        df[present]
        .fillna("")
        .astype(str)
        .agg(" | ".join, axis=1)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    scores = [float(fuzz.WRatio(query, text)) if text else 0.0 for text in haystacks]
    scored = df.copy()
    scored["_search_score"] = scores
    return scored.loc[scored["_search_score"] >= score_cutoff].sort_values(
        "_search_score", ascending=False
    )