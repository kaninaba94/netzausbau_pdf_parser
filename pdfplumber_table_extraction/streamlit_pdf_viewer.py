from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit as st

COMPONENT_DIRECTORY = Path(__file__).parent / "pdf_viewer"

pdf_viewer_component = st.components.v2.component(
    name="pdf_page_viewer",
    html=(COMPONENT_DIRECTORY / "viewer.html").read_text(encoding="utf-8"),
    css=(COMPONENT_DIRECTORY / "viewer.css").read_text(encoding="utf-8"),
    js=(COMPONENT_DIRECTORY / "viewer.js").read_text(encoding="utf-8"),
)


def display_pdf(pdf_bytes: bytes, *, key: str) -> Any:
    encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")

    return pdf_viewer_component(
        data={
            "pdf_base64": encoded_pdf,
            "initial_page": 1,
            "scale": 1.5,
        },
        default={
            "page_number": 1,
            "page_count": None,
        },
        key=key,
        on_page_number_change=lambda: None,
        on_page_count_change=lambda: None
    )


uploaded_pdf = st.file_uploader("Upload PDF", type="pdf")

if uploaded_pdf is not None:
    viewer_result = display_pdf(
        uploaded_pdf.getvalue(),
        key="pdf-viewer",
    )

    st.write(
        f"Current page: {viewer_result.page_number} "
        f"of {viewer_result.page_count}"
    )
