from __future__ import annotations

import json
import csv
import tempfile
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
import streamlit as st
from PIL import Image

PageRange = tuple[int, int]


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
        text_settings = {k.split('text_')[1]: v for k, v in table_settings.items() if 'text_' in k} 
        debug_page_image = debug_page_image.outline_words(**text_settings)

        temporary_image_path = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".png").name)
        debug_page_image.save(str(temporary_image_path), format="PNG")
        return Image.open(temporary_image_path)


def extract_tables(
    pdf_path: Path,
    page_ranges: PageRange,
    table_settings: dict[str, Any],
    drop_first_row: bool,
) -> list[list[list[str | None]]]:
    tables: list[list[list]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_range in page_ranges: 
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
            tables.append(rows) 
        return tables


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-path", required=True)
    args = parser.parse_args()
    st.set_page_config(layout="wide")
    st.title("pdfplumber TableFinder UI")

    pdf_path = Path(args.pdf_path)
    numbered_pdf_bytes, page_count = add_page_numbers(pdf_path.read_bytes())

    left_column, right_column = st.columns([1, 2])

    with left_column:
        st.pdf(numbered_pdf_bytes)
        page_ranges = parse_page_ranges(st.text_input('page_ranges', value=f'1-{page_count}', placeholder='e.g. 2-8, 12, 24-34'), page_count=page_count )

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
                    page_ranges=page_ranges,
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
                csv_path = Path(__file__).parent / "output"/ pdf_path.parent.name / f"{pdf_path.name}.csv" 
                with open(csv_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(st.session_state['tables'])
                st.success(f"Saved to {path}")



if __name__ == "__main__":
    main()
