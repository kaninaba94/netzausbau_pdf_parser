from __future__ import annotations

import json
import base64
import pandas as pd
import tempfile
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
import streamlit as st
from PIL import Image

PageRange = tuple[int, int]

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

def parse_page_ranges(raw_value: str, *, page_count: int) -> list[PageRange]:
    if not raw_value.strip():
        raise ValueError("Enter at least one page range")

    page_ranges: list[PageRange] = []

    for raw_part in raw_value.split(","):
        part = raw_part.strip()

        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start_page = int(start_text.strip())
            end_page = int(end_text.strip())
        else:
            start_page = int(part)
            end_page = start_page

        if start_page < 1:
            raise ValueError("Page numbers must be at least 1")
        if start_page > end_page:
            raise ValueError(f"Invalid page range: {part}")
        if end_page > page_count:
            raise ValueError(f"Page range {part} exceeds page count {page_count}")

        page_ranges.append((start_page, end_page))

    return page_ranges


def selected_page_numbers(page_ranges: list[PageRange]) -> list[int]:
    return list(
        dict.fromkeys(
            page_number
            for start_page, end_page in page_ranges
            for page_number in range(start_page, end_page + 1)
        )
    )

@st.cache_data
def add_page_numbers(pdf_bytes: bytes) -> bytes:
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_index, page in enumerate(pdf_document):
        page_number = str(page_index + 1)
        page_rectangle = page.rect

        page.insert_text(
            point=fitz.Point(
                page_rectangle.x0 + 20,
                page_rectangle.y1 - 20,
            ),
            text=page_number,
            fontsize=24,
            fontname="helv",
            color=(1, 0, 0),
            overlay=True,
        )

    numbered_pdf_bytes = pdf_document.tobytes()
    pdf_document.close()

    return numbered_pdf_bytes, int(page_number)

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
        text_settings = {k[5:]: v for k, v in table_settings.items() if k.startswith('text_')} 
        debug_page_image = debug_page_image.outline_words(**text_settings)   # TODO: Bump (poetry add) pdfplumber version once https://github.com/jsvine/pdfplumber/pull/1384 is released 

        temporary_image_path = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".png").name)
        debug_page_image.save(str(temporary_image_path), format="PNG")
        return Image.open(temporary_image_path)


def extract_tables(
    pdf_path: Path,
    page_ranges: PageRange,
    table_settings: dict[str, Any],
) -> list[pd.DataFrame]:
    tables: list[list[list]] = []
    delimiter = '__________'
    none_string = 'None'
    with pdfplumber.open(pdf_path) as pdf:
        for page_range in page_ranges: 
            pages = pdf.pages[page_range[0] - 1: page_range[1]]
            rows: list = []
            rows_hashable: list[str] = []
            for page in pages:
                page_rows = page.extract_tables(table_settings, )[0]

                page_rows_hashable = [delimiter.join(value or none_string for value in pr) for pr in page_rows]
                rows_hashable += page_rows_hashable
            
            unique_rows_hashable = list(dict.fromkeys(rows_hashable))
            rows = [[None if value == none_string else value for value in row_hashable.split(delimiter)] for row_hashable in unique_rows_hashable]
            tables.append(rows) 
    return [pd.DataFrame(t) for t in tables]

ANNOTATOR_COMPONENT_DIRECTORY = Path(__file__).parent / "custom_component"

pdf_annotator_component = st.components.v2.component(
    name="pdf_page_viewer",
    html=(ANNOTATOR_COMPONENT_DIRECTORY / "annotator.html").read_text(encoding="utf-8"),
    css=(ANNOTATOR_COMPONENT_DIRECTORY / "annotator.css").read_text(encoding="utf-8"),
    js=(ANNOTATOR_COMPONENT_DIRECTORY / "annotator.js").read_text(encoding="utf-8"),
)

def display_pdf(pdf_bytes: bytes, page: int, *, key: str) -> Any:
    encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")

    return pdf_annotator_component(
        data={
            "pdf_base64": encoded_pdf,
            "page": page,
            "scale": 1.5,
        },
        default={'points': None},
        on_points_change=lambda: None,
        key=key,
    )

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-path", required=True)
    args = parser.parse_args()
    st.set_page_config(layout="wide")
    st.title("pdfplumber TableFinder UI")
    st.write(f"file name: {Path(args.pdf_path)}")

    pdf_path = Path(args.pdf_path)
    numbered_pdf_bytes, page_count = add_page_numbers(pdf_path.read_bytes())

    st.pdf(numbered_pdf_bytes, height=1200)
    page_ranges = parse_page_ranges(st.text_input('page_ranges', value=f'1-{page_count}', placeholder='e.g. 2-8, 12, 24-34'), page_count=page_count )


    st.subheader("table_settings")
    st.info('See https://github.com/jsvine/pdfplumber#table-extraction-settings for reference')
    
    if 'table_settings' not in st.session_state:
        st.session_state['table_settings'] = default_table_settings

    if "table_settings_json" not in st.session_state:
        st.session_state.table_settings_json = json.dumps(
            st.session_state.table_settings,
            indent=2,
        )
    
    st.session_state['table_settings'] = st.text_area(
        label='table_settings',
        value=st.session_state.table_settings_json,
        height=240
    )
    try:
        st.session_state['table_settings']: dict[str, Any] = json.loads(st.session_state['table_settings'])
    except json.JSONDecodeError as json_decode_error:
        st.error(f"Invalid JSON: {json_decode_error}")
    else:
        st.success("Valid JSON")
    
    st.info("If you find it hard to find table_settings that correctly find the column postitions, you can annotate them interactively. This will change `vertical_strategy` to `explicit_lines` and populate `explicit_vertical_lines`.")
    explicit_vertical_lines = st.checkbox("Annotate explicit vertical lines?")
    if explicit_vertical_lines:
        st.info("Right-click to annotate vertical lines, left-click to remove the last one.")
        
        annotation_page = st.number_input("page to annotate lines on", value=page_ranges[0][0])
        annotator_result = display_pdf(
                pdf_bytes=pdf_path.read_bytes(),
                page=annotation_page,
            key="pdf-annotator",
        )
        if st.button('Update table_settings'):
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[annotation_page - 1] 
                explicit_vertical_lines = [int(p['x'] * page.width) for p in annotator_result.points]
                st.session_state['table_settings']['vertical_strategy'] = 'explicit'
                st.session_state['table_settings']['explicit_vertical_lines'] = explicit_vertical_lines           
                st.session_state['table_settings_json'] = json.dumps(st.session_state.table_settings, indent=2)           
                st.rerun()

    
    resolution = st.slider("debug tablefinder preview resolution", 72, 300, 150, 10)
    debug_page_number = st.number_input('page to render for debugging', value=page_ranges[0][0])
    preview_clicked = st.button("Preview", type="primary")
    
    if preview_clicked:
        try:
            debug_image = render_debug_image(
                pdf_path=pdf_path,
                page_number=int(debug_page_number),
                table_settings=st.session_state['table_settings'],
                resolution=resolution,
            )
            st.image(debug_image, caption="debug_tablefinder preview", use_container_width=True)

            st.session_state['tables'] = extract_tables(
                pdf_path=pdf_path,
                page_ranges=page_ranges,
                table_settings=st.session_state['table_settings'],
            )

        except Exception as error:
            st.exception(error)

    if 'tables' in st.session_state:
        st.subheader("extract_tables result")
        for t in st.session_state['tables']:
            st.dataframe(t)
    
        if st.button("Save to disk"):
            csv_paths: list = []
            for i, table in enumerate(st.session_state['tables']):
                 
                csv_path = Path(__file__).parent / "output"/ pdf_path.parent.name / f"{pdf_path.name}.{i}.csv" 
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                csv_paths.append(csv_path)
                table.to_csv(csv_path, index=False, header=False)
            st.success(f"Saved to paths \n{'\n'.join(str(p) for p in csv_paths)}")



if __name__ == "__main__":
    main()
