from __future__ import annotations

from netzausbau_extractor.heuristics import extract_measures
from netzausbau_extractor.pdf_reader import PdfPage, TextBlock


def test_extracts_measure_from_block() -> None:
    page = PdfPage(
        page=1,
        text="",
        blocks=[
            TextBlock(
                page=1,
                bbox=(0.0, 0.0, 1.0, 1.0),
                text=(
                    "Maßnahme MS 10 Projektbeschreibung Verstärkung Mittelspannung "
                    "Leitungslänge 3,5 km Kapazitätsänderung 20 MVA "
                    "Inbetriebnahme 2030 Kosten 1,2 Mio. €"
                ),
            )
        ],
        tables=[],
    )

    measures = extract_measures([page])

    assert len(measures) == 1
    assert measures[0].measure_id == "MS 10"
    assert measures[0].length_km == 3.5
    assert measures[0].capacity_change_mva == 20.0
    assert measures[0].estimated_cost_eur == 1_200_000.0
