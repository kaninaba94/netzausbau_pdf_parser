import pytest
from pydantic import ValidationError

from netzausbauplan_processing.extraction.data.models import (
    AssetType,
    ExtractionOutput,
    Measure,
    measures_from_payload,
)


def test_measure_validates_asset_type_on_instantiation() -> None:
    measure = Measure.model_validate(
        {
            "title": "North field",
            "asset_type": "wind farm",
            "quantity": 120,
            "quantity_unit": "MW",
        }
    )

    assert measure.asset_type is AssetType.WIND_FARM


def test_measure_rejects_unknown_asset_type() -> None:
    with pytest.raises(ValidationError):
        Measure.model_validate({"asset_type": "Mittelspannung"})


def test_extraction_output_validates_each_measure() -> None:
    payload = {
        "Maßnahmen": [
            {"asset_type": "solar park", "quantity": 80, "quantity_unit": "MW"},
            {"asset_type": "high voltage electricity line", "quantity": 12, "quantity_unit": "km"},
        ]
    }

    output = ExtractionOutput.model_validate(payload)

    assert len(output.measures) == 2
    assert output.measures[0].asset_type is AssetType.SOLAR_PARK


def test_measures_from_payload_helper() -> None:
    measures = measures_from_payload({"Maßnahmen": [{"asset_type": "wind farm"}]})

    assert len(measures) == 1
    assert measures[0].asset_type is AssetType.WIND_FARM
