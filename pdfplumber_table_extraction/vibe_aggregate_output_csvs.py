"""Aggregate recursively extracted output CSVs into a single normalized CSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import pandas as pd

CANONICAL_COLUMNS: dict[str, str] = {
    "lfd_nr": "lfd. Nr.",
    "massnahme": "Maßnahme",
    "kurze_projektbeschreibung": "kurze Projektbeschreibung",
    "projektkategorie": "Projektkategorie",
    "betriebsmittel": "Betriebsmittel",
    "leitungslaenge_km": (
        "Länge des zugebauten, optimierten, oder ersetzten Leitungsabschnitts [km]"
    ),
    "kapazitaetsaenderung_mva": "Änderung der Übertragungskapazität [+/- MVA]",
    "netzbegruendung_1": (
        "netztechnische Begründung für den Netzausbau 1. kurze Beschreibung"
    ),
    "netzbegruendung_2": (
        "netztechnische Begründung für den Netzausbau "
        "2. Aus welchem Grund erfolgt die Netzausbaumaßnahme überwiegend?"
    ),
    "engpass_bestehend_beheben": (
        "Erfolgt diese Netzausbaumaßnahme, um einen bereits bestehenden Engpass zu beheben?"
    ),
    "engpass_prognose_vorbeugen": (
        "Erfolgt diese Netzausbaumaßnahme, um einen prognostizierten Engpass vorzubeugen?"
    ),
    "optimaler_zeitpunkt": (
        "optimaler Zeitpunkt der Fertigstellung aus Sicht der Netzplanung [JJJJ]"
    ),
    "baubeginn": "voraussichtlicher Zeitpunkt des Baubeginns [MM/JJJJ]",
    "inbetriebnahme": "voraussichtlicher Zeitpunkt der Inbetriebnahme [MM/JJJJ]",
    "verzoegerungsgrund": (
        "Angabe des Verzögerungsgrundes a) bis g). Mehrfachnennung möglich"
    ),
    "verzoegerungsgrund_beschreibung": "Beschreibung angegebener Verzögerungsgrund",
    "kosten": "Kosten (geschätzt) in Euro",
    "projektstatus": "Projektstatus",
    "genehmigungsverfahren": "Stand Genehmigungsverfahren",
    "alternativen": "Geprüfte Alternativen zum Netzausbau",
    "netzebene": "Vorrangig betroffene Netz oder Umspannebene",
    "teilnetzgebiet": "Hauptsächlich betroffenes Teilnetzgebiet",
    "netzknoten_hoes": (
        "von der Netzausbaumaßnahme betroffene(r) Netzknoten im überlagerten HöS-Netz"
    ),
}


def normalize_col(name: str) -> str:
    s = str(name).replace("\u00ad", "")
    s = s.replace("\n", " ")
    s = re.sub(r"-\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def classify_column(name: str) -> str | None:
    n = normalize_col(name)
    if not n:
        return None

    if re.fullmatch(r"(lfd\.?\s*nr\.?|lfd nr\.?|index)", n):
        return "lfd_nr"
    if n in {"maßnahme", "objekt/maßnahme"}:
        return "massnahme"
    if n == "maßnahmenart":
        return "projektkategorie"
    if "kurze projektbeschreibung" in n:
        return "kurze_projektbeschreibung"
    if n == "projektbeschreibung":
        return "kurze_projektbeschreibung"
    if "projektkategorie" in n:
        return "projektkategorie"
    if "betriebsmittel" in n:
        return "betriebsmittel"
    if (
        "leitungs" in n
        or "zubau" in n
        or n.startswith("länge des")
        or n == "leitungslänge [km]"
    ):
        return "leitungslaenge_km"
    if "kapazität" in n or "kapazitätsänderung" in n or "übertragungs" in n:
        return "kapazitaetsaenderung_mva"
    if "netztechnische" in n and ("begründung" in n or "begründ ung" in n):
        if (
            "2." in n
            or "welchem grund" in n
            or "überwiegend" in n
            or "(grund)" in n
            or "hauptgrund" in n
        ):
            return "netzbegruendung_2"
        return "netzbegruendung_1"
    if "engpass" in n:
        if "bereits" in n or "bestehend" in n:
            return "engpass_bestehend_beheben"
        return "engpass_prognose_vorbeugen"
    if "optimaler zeitpunkt" in n or n == "benötigt bis":
        return "optimaler_zeitpunkt"
    if "inbetriebnahme" in n or "inbtrieb" in n or n == "voraussichtliches bauende":
        return "inbetriebnahme"
    if "baubeginn" in n or n == "voraussichtlicher baubeginn":
        return "baubeginn"
    if "verzögerungsgrund" in n:
        if "beschreibung" in n:
            return "verzoegerungsgrund_beschreibung"
        return "verzoegerungsgrund"
    if "kosten" in n:
        return "kosten"
    if "projektstatus" in n:
        return "projektstatus"
    if "genehmigung" in n:
        return "genehmigungsverfahren"
    if "alternativ" in n:
        return "alternativen"
    if "umspann" in n or ("netz" in n and "vorrangig" in n):
        return "netzebene"
    if "teilnetzgebiet" in n or n == "betroffenes teilnetzgebiet":
        return "teilnetzgebiet"
    if "netzknoten" in n or "hös-netz" in n or n == "uw":
        return "netzknoten_hoes"
    return None


def build_column_rename_map(columns: list[str]) -> dict[str, str]:
    rename: dict[str, str] = {}
    for col in columns:
        key = classify_column(col)
        if key is None:
            norm = normalize_col(col)
            if norm:
                rename[col] = f"_extra_{norm}"
            continue
        rename[col] = CANONICAL_COLUMNS[key]
    return rename


def looks_like_data_cell(value: str) -> bool:
    s = value.strip()
    if not s:
        return False
    if re.match(r"^\d+([.,]\d+)?$", s):
        return True
    if re.match(r"^\d{1,2}/\d{4}$", s):
        return True
    if s.startswith("UW ") or " MVA" in s:
        return True
    return False


def score_header_row(row: list[str]) -> int:
    header_hits = sum(1 for cell in row if classify_column(cell))
    data_hits = sum(1 for cell in row if looks_like_data_cell(cell))
    return header_hits * 3 - data_hits


def merge_header_rows(rows: list[list[str]]) -> list[str]:
    width = max(len(row) for row in rows)
    merged: list[str] = []
    for idx in range(width):
        parts: list[str] = []
        for row in rows:
            if idx < len(row):
                part = str(row[idx]).strip()
                if part:
                    parts.append(part)
        merged.append(" ".join(parts))
    return merged


def detect_header_rows(path: Path, max_scan: int = 4) -> tuple[int, int]:
    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        preview = []
        reader = csv.reader(handle)
        for _ in range(max_scan):
            try:
                preview.append(next(reader))
            except StopIteration:
                break

    if not preview:
        return 0, 0

    scores = [score_header_row(row) for row in preview]
    best_idx = max(range(len(scores)), key=lambda idx: scores[idx])
    if scores[best_idx] <= 0:
        return 0, 0

    header_end = best_idx
    while header_end + 1 < len(preview):
        next_score = scores[header_end + 1]
        if next_score <= 0:
            break
        if next_score < scores[header_end]:
            break
        header_end += 1

    return best_idx, header_end


def read_csv_with_detected_header(path: Path) -> pd.DataFrame:
    header_start, header_end = detect_header_rows(path)
    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        preview = []
        reader = csv.reader(handle)
        for row_idx in range(header_end + 1):
            try:
                preview.append(next(reader))
            except StopIteration:
                break

    if not preview:
        return pd.DataFrame(dtype=str)

    header = merge_header_rows(preview[header_start : header_end + 1])
    df = pd.read_csv(path, dtype=str, header=None, skiprows=header_end + 1)
    if df.empty and not header:
        return df

    if len(df.columns) != len(header):
        width = max(len(header), len(df.columns))
        header.extend([""] * (width - len(header)))
        if len(df.columns) < width:
            for _ in range(width - len(df.columns)):
                df[len(df.columns)] = pd.NA
        elif len(df.columns) > width:
            df = df.iloc[:, :width]

    df.columns = header[: len(df.columns)]
    return df


def coalesce_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not df.columns.duplicated().any():
        return df

    result: dict[str, pd.Series] = {}
    for col in dict.fromkeys(df.columns):
        series = df.loc[:, col]
        if isinstance(series, pd.DataFrame):
            combined = series.bfill(axis=1).iloc[:, 0]
        else:
            combined = series
        result[col] = combined
    return pd.DataFrame(result)


def read_and_normalize_csv(path: Path, output_root: Path) -> pd.DataFrame:
    df = read_csv_with_detected_header(path)
    df = df.loc[
        :,
        [
            col
            for col in df.columns
            if str(col).strip() and not str(col).lower().startswith("unnamed")
        ],
    ]
    rename_map = build_column_rename_map(list(df.columns))
    df = df.rename(columns=rename_map)
    df = coalesce_duplicate_columns(df)

    rel = path.relative_to(output_root)
    operator_dir = rel.parts[0] if rel.parts else ""
    operator_id = operator_dir.split("_", 1)[0] if operator_dir else ""
    operator_name = operator_dir.split("_", 1)[1] if "_" in operator_dir else operator_dir

    df.insert(0, "source_file", str(rel))
    df.insert(1, "operator_id", operator_id)
    df.insert(2, "operator_name", operator_name)
    return df


def aggregate_csvs(input_dir: Path, output_path: Path) -> pd.DataFrame:
    csv_files = sorted(
        p for p in input_dir.rglob("*.csv") if p.resolve() != output_path.resolve()
    )
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found under {input_dir}")

    frames = [read_and_normalize_csv(path, input_dir) for path in csv_files]
    combined = pd.concat(frames, ignore_index=True, sort=False)

    canonical_headers = list(CANONICAL_COLUMNS.values())
    meta_headers = ["source_file", "operator_id", "operator_name"]
    extra_headers = sorted(
        col for col in combined.columns if col not in meta_headers and col not in canonical_headers
    )
    ordered_columns = meta_headers + canonical_headers + extra_headers
    combined = combined.reindex(columns=ordered_columns)
    combined.to_csv(output_path, index=False)
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="Directory containing extracted CSV files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "aggregated.csv",
        help="Path for the combined CSV",
    )
    args = parser.parse_args()

    combined = aggregate_csvs(args.input_dir, args.output)
    source_count = len(
        [p for p in args.input_dir.rglob("*.csv") if p.resolve() != args.output.resolve()]
    )
    print(f"Wrote {len(combined)} rows from {source_count} files")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
