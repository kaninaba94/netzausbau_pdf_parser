from __future__ import annotations

from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetType(StrEnum):
    SOLAR_PARK = "solar park"
    WIND_FARM = "wind farm"
    HIGH_VOLTAGE_LINE = "high voltage electricity line"
    TRANSFORMER_STATION = "transformer station"
    UNKNOWN = "Unbekannt"
    
    @property
    def category(self) -> AssetCategory:
        match self:
            case AssetType.SOLAR_PARK | AssetType.WIND_FARM:
                return AssetCategory.POWER_PLANT
            case AssetType.HIGH_VOLTAGE_LINE:
                return AssetCategory.POWER_LINE
            case AssetType.UNKNOWN | AssetType.TRANSFORMER_STATION:
                return AssetCategory.UNKNOWN

class AssetCategory(StrEnum):
    POWER_PLANT = auto() 
    POWER_LINE = auto()
    UNKNOWN = auto()

class ProjectCategory(StrEnum):
    NEW = "Neubau"
    EXTENSION = "Erweiterung"
    REPLACEMENT = "Ersatz"



class TimeFrame(BaseModel):
    commissioning_planned: str | None = None
    commissioning_actual: str | None = None


class GeoReference(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    location_name: str | None = Field(default=None, alias="Ortsbezeichnung")
    longitude: float | None = None
    latitude: float | None = None


class Cost(BaseModel):
    estimated: float | None = None
    actual: float | None = None
    unit: str | None = None


class Measure(BaseModel):
    """Approach-agnostic measure payload validated from extracted JSON."""

    title: str | None = None
    description: str | None = None
    project_category: ProjectCategory | None = None
    announced_date: str | None = None
    time_frame: TimeFrame | None = None
    geo_reference: GeoReference | None = None
    asset_type: AssetType
    @model_validator(mode="after")
    def assets_need_correct_unit(self) -> "Measure":
        if self.quantity_unit is None:
            raise ValueError("quantity_unit is required for assets")
        if self.asset_type.category is AssetCategory.POWER_PLANT:
            if not self.quantity_unit.strip().upper() in ["KW", "MW", "GW"]:
                raise ValueError("quantity_unit must be 'kW', 'MW' or 'GW' when asset_type is 'wind farm'")
        elif self.asset_type.category is AssetCategory.POWER_LINE:
            if not self.quantity_unit.strip().upper() in ["M", "KM"]:
                raise ValueError("quantity_unit must be 'mva' for power lines")

        return self

    quantity: float | None = None
    quantity_unit: str | None = None
    cost: Cost | None = None
    # Legacy / alternate extractor fields
    measure_type: str | None = None
    timeframe: str | None = None
    estimated_cost_eur: float | None = None


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")
    measures: list[Measure] = Field(default_factory=list, alias="Maßnahmen")


class NetworkLevel(StrEnum):
    EHV = "Höchstspannung"
    HV = "Hochspannung"
    MV = "Mittelspannung"
    LV = "Niederspannung"
    UNKNOWN = "Unbekannt"


class ProjectCategory(StrEnum):
    NEW_BUILD = "Neubau"
    REPLACEMENT = "Ersatzneubau"
    REINFORCEMENT = "Verstärkung"
    OPTIMIZATION = "Optimierung"
    TRANSFORMER_STATION = "Umspannwerk/Station"
    UNKNOWN = "Unbekannt"


class Evidence(BaseModel):
    page: int
    text: str


class DocumentMetadata(BaseModel):
    source_pdf: str
    page_count: int
    network_operator: str | None = None
    publication_year: int | None = None
    legal_basis: str | None = None
    planning_years: list[int] = Field(default_factory=list)


