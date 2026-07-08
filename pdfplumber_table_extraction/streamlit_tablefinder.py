from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pdfplumber
import streamlit as st
from PIL import Image


def parse_explicit_vertical_lines(raw_value: str) -> list[float]:
    if not raw_value.strip():
        return []
    return [float(value.strip()) for value in raw_value.split(",") if value.strip()]


def render_debug_image(
    pdf_path: Path,
    page_number: int,
    table_settings: dict[str, Any],
    resolution: int,
) -> Image.Image:
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]
        debug_page_image = page.to_image(resolution=resolution)
        debug_page_image = debug_page_image.debug_tablefinder(table_settings)
        text_settings = {k.split('text_')[1]: v for k, v in table_settings.items() if 'text_' in k} 
        debug_page_image = debug_page_image.outline_words(**text_settings)

        temporary_image_path = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".png").name)
        debug_page_image.save(str(temporary_image_path), format="PNG")
        return Image.open(temporary_image_path)


def extract_tables(
    pdf_path: Path,
    page_range: int,
    table_settings: dict[str, Any],
    drop_first_row: bool,
) -> list[list[list[str | None]]]:
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[page_range[0] - 1: page_range[1]]
        rows: list = []
        first_page = True
        for page in pages:
            page_rows = page.extract_tables(table_settings, )[0]
            if drop_first_row and not first_page:
                rows += page_rows[1:]
            else:
                rows += page_rows
            first_page = False
        return rows


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-path", required=True)
    args = parser.parse_args()
    st.set_page_config(layout="wide")
    st.title("pdfplumber TableFinder UI")

    pdf_path = Path(args.pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

    left_column, right_column = st.columns([1, 2])

    with left_column:
        start_page = int(st.number_input('start_page', value=1))
        end_page = int(st.number_input('end_page', value=1))
        page_range = [start_page, end_page]

        resolution = st.slider("preview resolution", 72, 300, 150, 10)

        st.subheader("table_settings")
        default_table_settings = {
            "vertical_strategy": "lines", 
            "horizontal_strategy": "lines",
            "explicit_vertical_lines": [],
            "explicit_horizontal_lines": [],
            "snap_tolerance": 3,
            "snap_x_tolerance": 3,
            "snap_y_tolerance": 3,
            "join_tolerance": 3,
            "join_x_tolerance": 3,
            "join_y_tolerance": 3,
            "edge_min_length": 3,
            "edge_min_length_prefilter": 1,
            "min_words_vertical": 3,
            "min_words_horizontal": 1,
            "intersection_tolerance": 3,
            "intersection_x_tolerance": 3,
            "intersection_y_tolerance": 3,
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,
            "text_keep_blank_chars": True # See below
        }
        text_input = st.text_area(
            label='table_settings',
            value=json.dumps(default_table_settings, indent=2),
            height=240
        )
        try:
            table_settings: dict[str, Any] = json.loads(text_input)
        except json.JSONDecodeError as json_decode_error:
            st.error(f"Invalid JSON: {json_decode_error}")
        else:
            st.success("Valid JSON")
        
        drop_first_row = st.checkbox('Check this when columns are named on each page', value=True)


        preview_clicked = st.button("Preview", type="primary")
    
    with right_column:
        if preview_clicked:
            try:
                debug_image = render_debug_image(
                    pdf_path=pdf_path,
                    page_number=int(page_range[0]),
                    table_settings=table_settings,
                    resolution=resolution,
                )
                st.image(debug_image, caption="debug_tablefinder preview", use_container_width=True)

                st.session_state['tables'] = extract_tables(
                    pdf_path=pdf_path,
                    page_range=page_range,
                    table_settings=table_settings,
                    drop_first_row=drop_first_row
                )

            except Exception as error:
                st.exception(error)

        if 'tables' in st.session_state:
            st.subheader("extract_tables result")
            st.json(st.session_state["tables"])
    
            if st.button("Save to disk"):
                path = Path(__file__).parent / "output"/ pdf_path.parent.name / f"{pdf_path.name}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                  json.dumps(st.session_state["tables"], indent=2, ensure_ascii=False),
                  encoding="utf-8",
                )
                st.success(f"Saved to {path}")



if __name__ == "__main__":
    main()
