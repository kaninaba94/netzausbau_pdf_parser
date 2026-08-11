from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import streamlit as st
from pyrosm import OSM
from sentence_transformers import SentenceTransformer

from lib.measures import (
    collect_raw_measures_dfs_from_csvs,
    get_random_measure,
    measure_row_hash,
    measure_to_jsonable,
)
from lib.osm import get_all_substations

APP_DIR = Path(__file__).resolve().parent
GEOCODING_ROOT = APP_DIR.parents[2]
REPO_ROOT = APP_DIR.parents[3]
HEURISTICS_DIR = REPO_ROOT / 'data' / 'auxiliary'
TABLES_ROOT = REPO_ROOT / "table_extraction" / "output"
PBF_PATH = REPO_ROOT / "data" / "osm" / "germany-power.osm.pbf"
LABELS_PATH = GEOCODING_ROOT / "artefacts" / "embedding_match_labels.json"
MODEL_NAME = "intfloat/multilingual-e5-small"
TOP_K = 5

SUBSTATION_FIELDS = (
    "tag::name",
    "tag::operator",
    "tag::ref",
    "tag::voltage",
    "substation",
    "tag::location",
    "tag::addr:city",
    "tag::addr:street",
    "tag::addr:postcode",
)

MatchLabel = Literal["positive", "negative", "skip"]

st.set_page_config(
    page_title="Embedding match labelling",
    page_icon=":material/electric_bolt:",
    layout="wide",
)


def serialize_substation(substation: pd.Series) -> str:
    serialized_fields: list[str] = []

    for field_name in SUBSTATION_FIELDS:
        value = substation.get(field_name)
        if value is None or pd.isna(value):
            continue
        serialized_fields.append(f"{field_name}: {value}")
     
    return "passage: " + "; ".join(serialized_fields)


def lookup_heuristics(measure: pd.Series) -> pd.Series:
    pattern = re.compile(r'.*Netze.*BW.*')
    
    if pattern.match(measure['source_file']):
        with open(Path(HEURISTICS_DIR) / 'netze_bw_substation_lookup.json') as f:
            lookup_table = json.load(f)
        for k, v in lookup_table['entries'].items():
            if v['canonical_name'] is not None:
                measure['Maßnahme'] = measure['Maßnahme'].replace(k, v['canonical_name'])
    return measure


def serialize_measure(measure: pd.Series) -> str:
    columns = measure.index
    field_names = [c for c in columns if not any([k in c.lower() for k in ['netztechnische', 'begründung', 'verzögerung', 'kosten', 'unnamed', 'zeitpunkt']])]
    serialized_fields: list[str] = []
    preprocessed_measure = measure.copy()
    for field_name in field_names:
        preprocessed_measure = lookup_heuristics(measure)
    for field_name in field_names:
        value = preprocessed_measure.get(field_name)
        if value is None or pd.isna(value):
            continue
        serialized_fields.append(f"{field_name}: {value}")
    return "query: " + "; ".join(serialized_fields)


def load_match_labels(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


def save_match_labels(path: Path, labels: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)


def label_key(measure_hash: int, substation_id: int) -> tuple[int, int]:
    return measure_hash, substation_id


def existing_label(
    labels: list[dict[str, Any]], measure_hash: int, substation_id: Optional[int]
) -> list[dict[str, Any]] | dict[str, Any] | None:
    if substation_id is None:
        return [e for e in labels if int(e.get("measure_row_hash", -1)) == measure_hash] 
    for entry in labels:
        if (
            int(entry.get("measure_row_hash", -1)) == measure_hash
            and int(entry.get("osm_id", -1)) == substation_id
        ):
            return entry
    return None


def upsert_match_label(labels: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    measure_hash = int(entry["measure_row_hash"])
    substation_id = int(entry["osm_id"])
    for i, existing in enumerate(labels):
        if label_key(int(existing.get("measure_row_hash", -1)), int(existing.get("osm_id", -1))) == (
            measure_hash,
            substation_id,
        ):
            labels[i] = entry
            return
    labels.append(entry)


@st.cache_data(show_spinner="Loading measures…")
def load_measures(root: str) -> list[pd.DataFrame]:
    return collect_raw_measures_dfs_from_csvs(root)


@st.cache_resource(show_spinner="Loading embedding model…")
def load_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@st.cache_resource(show_spinner="Loading substations from OSM…")
def load_substations(pbf_path: str) -> pd.DataFrame:
    osm_reader = OSM(filepath=pbf_path, bounding_box=None)
    substations_gdf = get_all_substations(osm_reader)
    if substations_gdf is None or substations_gdf.empty:
        msg = f"No substations found in {pbf_path}"
        raise RuntimeError(msg)
    substations_df = pd.DataFrame(substations_gdf.drop(columns="geometry", errors="ignore"))
    substations_df["serialized"] = substations_df.apply(serialize_substation, axis=1)
    return substations_df


@st.cache_resource(show_spinner="Embedding substations…")
def load_substation_embeddings(_model: SentenceTransformer, pbf_path: str) -> np.ndarray:
    substations_df = load_substations(pbf_path)
    return _model.encode(
        substations_df["serialized"].tolist(),
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def top_substation_matches(
    measure: pd.Series,
    substations_df: pd.DataFrame,
    substation_embeddings: np.ndarray,
    model: SentenceTransformer,
    *,
    top_k: int = TOP_K,
) -> pd.DataFrame:
    serialized_measure = serialize_measure(measure)
    measure_embedding = model.encode(
        [serialized_measure],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    similarities = measure_embedding @ substation_embeddings.T
    row = similarities[0]
    top_indices = np.argpartition(-row, kth=min(top_k, len(row)) - 1)[:top_k]
    top_indices = top_indices[np.argsort(-row[top_indices])]

    rows: list[dict[str, Any]] = []
    for _, idx in enumerate(top_indices, start=1):
        substation = substations_df.iloc[int(idx)]
        rows.append(
            {
                "osm_id": int(substation["id"]),
                **{field: substation.get(field) for field in SUBSTATION_FIELDS},
                "serialized": substation["serialized"],
            }
        )
    return pd.DataFrame(rows)


def pick_new_measure(measures_dfs: list[pd.DataFrame]) -> pd.Series:
    return get_random_measure(measures_dfs)


def init_state() -> None:
    st.session_state.setdefault("labels", load_match_labels(LABELS_PATH))
    st.session_state.setdefault("current_measure", None)
    st.session_state.setdefault("current_measure_hash", None)
    st.session_state.setdefault("top_matches", None)
    st.session_state.setdefault("candidate_index", 0)
    st.session_state.setdefault("substation_manual", None)

def search_by_osm_id(osm_id: int, substations_df: pd.DataFrame) -> pd.Series:
    return substations_df.loc[substations_df['id'] == int(osm_id)]

def start_new_measure(measures_dfs: list[pd.DataFrame]) -> None:
    measure = pick_new_measure(measures_dfs)
    st.session_state.current_measure = measure
    st.session_state.current_measure_hash = measure_row_hash(measure)
    st.session_state.top_matches = None
    st.session_state.candidate_index = 0
    st.session_state.substation_manual = None


def advance_candidate() -> None:
    st.session_state.candidate_index += 1


def save_label(
    *,
    measure: pd.Series,
    match_row: pd.Series,
    label: MatchLabel,
) -> None:
    entry = measure_to_jsonable(measure)
    entry["measure_row_hash"] = measure_row_hash(measure)
    entry["osm_id"] = int(match_row["osm_id"])
    entry["label"] = label
    labels: list[dict[str, Any]] = st.session_state.labels
    upsert_match_label(labels, entry)
    save_match_labels(LABELS_PATH, labels)
    st.session_state.labels = labels


def format_osm_url(osm_id: int) -> str:
    return f"https://www.openstreetmap.org/way/{osm_id}"


init_state()
measures_dfs = load_measures(str(TABLES_ROOT))
model = load_model()
substations_df = load_substations(str(PBF_PATH))
substation_embeddings = load_substation_embeddings(model, str(PBF_PATH))

if st.session_state.current_measure is None:
    start_new_measure(measures_dfs)

measure: pd.Series = st.session_state.current_measure
measure_hash: int = st.session_state.current_measure_hash

if st.session_state.top_matches is None:
    st.session_state.top_matches = top_substation_matches(
        measure,
        substations_df,
        substation_embeddings,
        model,
        top_k=TOP_K,
    )

top_matches: pd.DataFrame = st.session_state.top_matches
candidate_index: int = st.session_state.candidate_index

if candidate_index >= len(top_matches):
    start_new_measure(measures_dfs)
    st.session_state.top_matches = top_substation_matches(
        st.session_state.current_measure,
        substations_df,
        substation_embeddings,
        model,
        top_k=TOP_K,
    )
    st.rerun()

labels: list[dict[str, Any]] = st.session_state.labels
labelled_pairs = {
    label_key(int(entry["measure_row_hash"]), int(entry["osm_id"]))
    for entry in labels
    if "measure_row_hash" in entry and "osm_id" in entry
}

st.title("Embedding match labelling")
st.caption(
    f"{len(substations_df):,} substations · {sum(len(df) for df in measures_dfs):,} measures · "
    f"{len(labelled_pairs):,} labelled pairs"
)

with st.sidebar:
    st.subheader("Session")
    st.metric("Labelled pairs", len(labelled_pairs))
    if st.button("Next random measure", icon=":material/casino:", width="stretch"):
        start_new_measure(measures_dfs)
        st.session_state.top_matches = top_substation_matches(
            st.session_state.current_measure,
            substations_df,
            substation_embeddings,
            model,
            top_k=TOP_K,
        )
        st.rerun()
    st.caption(f"Labels file: `{LABELS_PATH.relative_to(REPO_ROOT)}`")
    if st.button("Reload labels from disk", icon=":material/refresh:", width="stretch"):
        st.session_state.labels = load_match_labels(LABELS_PATH)
        st.rerun()

current_match = top_matches.iloc[candidate_index]
substation_id = int(current_match["osm_id"])
prior_pairs = existing_label(labels, measure_hash, None)
if len(prior_pairs) > 0:
    st.info(f"Measure has previously been labelled")

prior_pair = existing_label(labels, measure_hash, substation_id)

st.subheader("Current measure")
st.dataframe(measure.drop(labels=["source_file"], errors="ignore").to_frame(name="value"), height='content')
st.caption(f"Source: `{measure.get('source_file', '')}` · hash `{measure_hash}`")

st.write(f"Serialized (model input):")
st.code(serialize_measure(measure))

st.divider()
if st.button("Recompute candidates"):
    st.session_state.top_matches = top_substation_matches(
        st.session_state.current_measure,
        substations_df,
        substation_embeddings,
        model,
        top_k=TOP_K,
    )
    st.rerun()

st.subheader(f"Candidate {candidate_index + 1} of {len(top_matches)}")
st.link_button(
    "Open in OpenStreetMap",
    format_osm_url(substation_id),
    icon=":material/map:",
)

display_fields = ["osm_id", *SUBSTATION_FIELDS]
st.dataframe(
    current_match[display_fields].to_frame(name="value"),
    height='content',
)
st.write(f"Serialized (what model sees):")
st.code(current_match['serialized'])

if prior_pair:
    st.info(f"Previously labelled as **{prior_pair['label']}**.")

with st.container(horizontal=True):
    if st.button("Positive match", icon=":material/check_circle:", type="primary"):
        save_label(measure=measure, match_row=current_match, label="positive")
        advance_candidate()
        st.rerun()
    if st.button("Negative match", icon=":material/cancel:"):
        save_label(measure=measure, match_row=current_match, label="negative")
        advance_candidate()
        st.rerun()
    if st.button("I'm not sure", icon=":material/help:"):
        save_label(measure=measure, match_row=current_match, label="skip")
        advance_candidate()
        st.rerun()

st.divider()
st.subheader(f"Manual labelling")
osm_id = st.text_input("OSM ID")

if st.button("Search"):
    st.session_state.substation_manual = search_by_osm_id(osm_id, substations_df)[['id'] + list(SUBSTATION_FIELDS) + ['serialized']] 
    assert st.session_state.substation_manual.shape[0] == 1
    st.session_state.substation_manual = st.session_state.substation_manual.iloc[0]
    st.dataframe(
        st.session_state.substation_manual,
        height='content'
    )
    st.write(f"Serialized (what model sees):")
    st.code(st.session_state.substation_manual['serialized'])

if 'substation_manual' in st.session_state and st.session_state.substation_manual is not None:
    substation = st.session_state.substation_manual
    substation['osm_id'] = substation['id']

    with st.container(horizontal=True):
        if st.button("Positive match", icon=":material/check_circle:", type="primary", key="manual_pos_btn"):
            save_label(measure=measure, match_row=substation, label="positive")
            st.rerun()
        if st.button("Negative match", icon=":material/cancel:", key="manual_neg_btn"):
            save_label(measure=measure, match_row=substation, label="negative")
            st.rerun()
        if st.button("I'm not sure", icon=":material/help:", key="manual_skip_btn"):
            save_label(measure=measure, match_row=substation, label="skip")
            st.rerun()

