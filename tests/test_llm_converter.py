from pathlib import Path

from netzausbau_extractor.llm_converter import llm_extraction_to_result, parse_llm_payload
from netzausbau_extractor.models import LlmExtraction, NetworkLevel, ProjectCategory


def test_parse_legacy_array_payload() -> None:
    payload = [
        {
            "measure_type": "Leitungen",
            "timeframe": "2023 bis 2028 (T+5)",
            "asset_type": "Mittelspannung",
            "quantity": 102,
            "quantity_unit": "km",
            "estimated_cost_eur": 24843844,
        }
    ]

    extraction = parse_llm_payload(payload)

    assert len(extraction.measures) == 1
    assert extraction.measures[0].measure_type == "Leitungen"


def test_llm_extraction_to_result_maps_fields() -> None:
    extraction = LlmExtraction.model_validate(
        {
            "metadata": {"network_operator": "WSW Netz GmbH", "publication_year": 2024},
            "measures": [
                {
                    "measure_type": "Erneuerung UA Bottrop",
                    "timeframe": "01/2022 - 12/2024",
                    "asset_type": "Umspannanlage",
                    "quantity": 1,
                    "quantity_unit": "Stk.",
                    "estimated_cost_eur": 5524000,
                },
                {
                    "measure_type": "Maßnahmen Mittelspannung",
                    "timeframe": "2029 bis 2033",
                    "asset_type": "Mittelspannung",
                    "quantity": 66200000,
                    "quantity_unit": "EUR",
                    "estimated_cost_eur": None,
                },
            ],
        }
    )

    result = llm_extraction_to_result(
        extraction,
        pdf_path=Path("plan.pdf"),
        page_count=42,
    )

    assert result.metadata.page_count == 42
    assert result.metadata.network_operator == "WSW Netz GmbH"
    assert result.measures[0].estimated_cost_eur == 5524000
    assert result.measures[0].category == ProjectCategory.TRANSFORMER_STATION
    assert result.measures[1].estimated_cost_eur == 66200000
    assert result.measures[1].network_level == NetworkLevel.MV
