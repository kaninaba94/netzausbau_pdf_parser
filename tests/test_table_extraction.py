import sys
import pytest
from pathlib import Path

from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).parents[1]

def test_streamlit_app_starts_without_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    app_path = REPO_ROOT / "table_extraction" / "streamlit_tableparser.py"

    pdf_path = list(Path(REPO_ROOT / "data" / "pdfs").rglob("**/*pdf"))[0]
    

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(app_path),
            
            "--pdf-path",
            str(pdf_path)
        ],
    )
    app = AppTest.from_file(app_path)
    app.run(timeout=6)

    assert not app.exception


