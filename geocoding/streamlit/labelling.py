from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from lib.measures import (
    ASSET_TYPES,
    collect_raw_measures_dfs_from_csvs,
    default_search_columns,
    filter_by_rapidfuzz,
    filter_by_regex,
    get_random_measure,
    labelled_hashes,
    load_labelled_measures,
    measure_row_hash,
    measure_to_jsonable,
    save_labelled_measures,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GEOCODING_ROOT = Path(__file__).resolve().parents[1]
TABLES_ROOT = REPO_ROOT / "pdfplumber_table_extraction" / "output"
LABELS_PATH = GEOCODING_ROOT / "artefacts" / "01_sampled_measures_labelled.json"

st.set_page_config(page_title="Maßnahmen labelling", page_icon=":material/label:", layout="wide")


@st.cache_data(show_spinner="Loading tables…")
def load_tables(root: str) -> dict[str, pd.DataFrame]:
    dfs = collect_raw_measures_dfs_from_csvs(root)
    return {df["source_file"].iloc[0]: df for df in dfs if not df.empty}


@st.cache_data(show_spinner=False)
def row_hashes_for_table(root: str, source_file: str) -> list[int]:
    df = load_tables(root)[source_file]
    return [measure_row_hash(df.iloc[i]) for i in range(len(df))]


def update_table_index() -> None:
    st.session_state.table_index = st.session_state.table_index_selectbox


def init_state() -> None:
    st.session_state.setdefault("labels", load_labelled_measures(LABELS_PATH))
    st.session_state.setdefault("selected_hash", None)
    st.session_state.setdefault("table_index", 0)


def upsert_label(entry: dict[str, Any]) -> None:
    row_hash = int(entry["measure_row_hash"])
    labels: list[dict[str, Any]] = st.session_state.labels
    for i, existing in enumerate(labels):
        if int(existing.get("measure_row_hash", -1)) == row_hash:
            labels[i] = entry
            break
    else:
        labels.append(entry)
    save_labelled_measures(LABELS_PATH, labels)
    st.session_state.labels = labels


def existing_label(row_hash: int) -> dict[str, Any] | None:
    for entry in st.session_state.labels:
        if int(entry.get("measure_row_hash", -1)) == row_hash:
            return entry
    return None


def parse_nullable_bool(value: str | None) -> bool | None:
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def format_nullable_bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unset"


def format_osm_id(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def pick_random_measure(
    tables: dict[str, pd.DataFrame],
    source_files: list[str],
    *,
    skip_labelled: bool = True,
    max_attempts: int = 200,
) -> bool:
    """Pick a random measure via get_random_measure and select it in the UI.

    Returns True if a measure was selected, False if none could be found.
    """
    dfs = list(tables.values())
    if not dfs:
        return False
    known = labelled_hashes(st.session_state.labels) if skip_labelled else set()
    for _ in range(max_attempts):
        measure = get_random_measure(dfs)
        row_hash = measure_row_hash(measure)
        if row_hash in known:
            continue
        source_file = str(measure["source_file"])
        if source_file not in tables:
            continue
        st.session_state.table_index = source_files.index(source_file)
        st.session_state.selected_hash = row_hash
        return True
    return False


init_state()
tables = load_tables(str(TABLES_ROOT))
source_files = list(tables.keys())
labelled = labelled_hashes(st.session_state.labels)

st.title("Maßnahmen labelling")
st.caption(
    f"{len(source_files)} tables · {sum(len(df) for df in tables.values()):,} rows · {len(labelled)} labelled"
)

with st.sidebar:
    st.subheader("Table")
    st.session_state.table_index_selectbox = st.session_state.table_index
    st.selectbox(
        "Source table",
        options=range(len(source_files)),
        format_func=lambda i: f"[{len(tables[source_files[i]])}] {source_files[i]}",
        key="table_index_selectbox",
        on_change=update_table_index
    )

    st.divider()
    hide_labelled = st.toggle("Hide labelled rows", value=False)
    if st.button("Random measure", icon=":material/casino:", use_container_width=True):
        pick_random_measure(tables, source_files, skip_labelled=True)
    st.caption(f"Labels file: `{LABELS_PATH.relative_to(REPO_ROOT)}`")
    if st.button("Reload labels from disk", icon=":material/refresh:"):
        st.session_state.labels = load_labelled_measures(LABELS_PATH)
        st.rerun()

source_file = source_files[st.session_state.table_index]
base_df = tables[source_file]
df = base_df.copy()
df["_row_idx"] = list(range(len(df)))
df["_row_hash"] = row_hashes_for_table(str(TABLES_ROOT), source_file)
df["_labelled"] = df["_row_hash"].isin(labelled)

searchable_cols = [c for c in base_df.columns if c != "source_file"]

with st.container(border=True):
    st.subheader("Search", anchor=False)
    default_cols = [c for c in default_search_columns(searchable_cols) if c in searchable_cols]
    search_cols = st.multiselect(
        "Columns",
        options=searchable_cols,
        default=default_cols,
        help="Search runs across any of the selected columns.",
    )
    search_mode = st.segmented_control(
        "Mode",
        options=["regex", "rapidfuzz"],
        default="rapidfuzz",
        key="search_mode",
    )
    query = st.text_input(
        "Query",
        placeholder=r"UW|Umspann|Kabel" if search_mode == "regex" else "UW Wildeshausen",
        help="Regex uses Python re.search. Rapidfuzz uses WRatio on the selected columns.",
    )

    threshold = 70
    case_sensitive = False
    if search_mode == "rapidfuzz":
        threshold = st.slider("Score cutoff", min_value=0, max_value=100, value=70)
    else:
        case_sensitive = st.toggle("Case sensitive", value=False)

filtered = df
if hide_labelled:
    filtered = filtered.loc[~filtered["_labelled"]]

if query.strip() and search_cols:
    if search_mode == "regex":
        try:
            filtered = filter_by_regex(filtered, search_cols, query, case=case_sensitive)
        except re.error as exc:
            st.error(f"Invalid regex: {exc}")
            filtered = filtered.iloc[0:0]
    else:
        filtered = filter_by_rapidfuzz(filtered, search_cols, query, score_cutoff=threshold)
elif query.strip() and not search_cols:
    st.warning("Select at least one column to search.")

st.metric("Matching rows", f"{len(filtered):,} / {len(df):,}")

preferred = default_search_columns(searchable_cols)
display_cols = ["_labelled"]
if "_search_score" in filtered.columns:
    display_cols.append("_search_score")
display_cols.extend([c for c in preferred if c in searchable_cols])
display_cols.extend([c for c in searchable_cols if c not in display_cols])

event = st.dataframe(
    filtered[display_cols],
    hide_index=True,
    height=420,
    on_select="rerun",
    selection_mode="single-row",
    key=f"table_{source_file}",
    column_config={
        "_labelled": st.column_config.CheckboxColumn("Labelled", disabled=True),
        "_search_score": st.column_config.NumberColumn("Score", format="%.0f"),
    },
)

selected_rows = event.selection.rows if event and event.selection else []
selected: pd.Series | None = None
if selected_rows:
    selected = filtered.iloc[selected_rows[0]]
    st.session_state.selected_hash = int(selected["_row_hash"])
elif st.session_state.selected_hash is not None:
    match = filtered.loc[filtered["_row_hash"] == st.session_state.selected_hash]
    if not len(match):
        match = df.loc[df["_row_hash"] == st.session_state.selected_hash]
    if len(match):
        selected = match.iloc[0]

st.divider()
st.subheader("Label", anchor=False)

if selected is None:
    st.info("Select a row in the table to label it.")
    st.stop()

raw_row = base_df.iloc[int(selected["_row_idx"])]
row_hash = int(selected["_row_hash"])
prior = existing_label(row_hash)

with st.expander("Selected measure", expanded=True):
    st.dataframe(raw_row.to_frame(name="value"), height=280)

nullable_options = ["unset", "yes", "no"]
asset_options = list(ASSET_TYPES) + ["unset"]
asset_default = prior.get("label:asset_type") if prior else None
asset_default = asset_default if asset_default in ASSET_TYPES else "unset"

with st.form("label_form", border=True):
    asset_type = st.segmented_control(
        "Asset type",
        options=asset_options,
        default=asset_default,
        key=f"asset_{row_hash}",
    )
    existing = st.segmented_control(
        "Asset already exists?",
        options=nullable_options,
        default=format_nullable_bool(prior.get("label:existing") if prior else None),
        key=f"existing_{row_hash}",
    )
    easy = st.segmented_control(
        "Easy to geocode?",
        options=nullable_options,
        default=format_nullable_bool(prior.get("label:easy_to_geocode") if prior else None),
        help="Relevant for existing transformer stations.",
        key=f"easy_{row_hash}",
    )
    clues_default = ""
    if prior and prior.get("label:location_clues"):
        clues_default = "\n".join(str(c) for c in prior["label:location_clues"])
    location_clues = st.text_area(
        "Location clues",
        value=clues_default,
        placeholder="One clue per line, e.g.\nWildeshausen\nNiedersachsen",
        height=100,
        key=f"clues_{row_hash}",
    )
    osm_id_raw = st.text_input(
        "OSM ID",
        value=format_osm_id(prior.get("label:osm_id") if prior else None),
        placeholder="Leave empty for none",
        key=f"osm_{row_hash}",
    )
    submitted = st.form_submit_button("Save label", icon=":material/save:", type="primary")

if submitted:
    entry = measure_to_jsonable(raw_row)
    entry["measure_row_hash"] = row_hash
    entry["label:asset_type"] = None if asset_type == "unset" else asset_type
    entry["label:existing"] = parse_nullable_bool(existing)

    entry["label:easy_to_geocode"] = parse_nullable_bool(easy)
    clues = [c.strip() for c in location_clues.splitlines() if c.strip()]
    if clues:
        entry["label:location_clues"] = clues
    entry["label:osm_id"] = int(osm_id_raw.strip()) if osm_id_raw.strip() else None

    upsert_label(entry)
    st.success(f"Saved label for hash {row_hash}")
    st.rerun()

if prior:
    st.caption("Current labels on this row")
    st.json({k: v for k, v in prior.items() if k.startswith("label:") or k == "measure_row_hash"})
