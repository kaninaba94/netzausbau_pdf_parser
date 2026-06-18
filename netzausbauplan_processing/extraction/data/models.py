from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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


class Measure(BaseModel):
    measure_id: str | None = None
    title: str | None = None
    description: str
    category: ProjectCategory = ProjectCategory.UNKNOWN
    network_level: NetworkLevel = NetworkLevel.UNKNOWN
    affected_assets: list[str] = Field(default_factory=list)
    start_year: int | None = None
    commissioning_year: int | None = None
    length_km: float | None = None
    capacity_change_mva: float | None = None
    estimated_cost_eur: float | None = None
    status: str | None = None
    permit_status: str | None = None
    alternatives: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    metadata: DocumentMetadata
    measures: list[Measure] = Field(default_factory=list)
