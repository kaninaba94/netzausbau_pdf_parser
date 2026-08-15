from pathlib import Path

from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).parents[2]

def test_streamlit_app_starts_without_errors() -> None:
    app_path = REPO_ROOT / "geocoding" / "pipelines" / "single_step" / "streamlit" / "labelling.py"

    app = AppTest.from_file(app_path)
    app.run(timeout=60)

    assert not app.exception
