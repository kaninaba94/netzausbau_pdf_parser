from __future__ import annotations

from enum import StrEnum, auto
from typing import Any
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetType(StrEnum):
    HIGH_VOLTAGE_LINE = "high voltage electricity line"
    TRANSFORMER_STATION = "transformer station"
    UNKNOWN = "Unbekannt"


class ProjectCategory(StrEnum):
    NEW = "Neubau"
    EXTENSION = "Erweiterung"
    REPLACEMENT = "Ersatz"



class TimeFrame(BaseModel):
    needed_until: str | None = None
    projected_start_of_construction: str | None = None
    projected_commissioning_date: str | None = None
    reason_for_delay: str | None = None


class GeoReference(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    location_name: str | None = Field(default=None, alias="Ortsbezeichnung")
    network_subregion: str | None = None
    superior_network_node: str | None = None 
    longitude: float | None = None
    latitude: float | None = None


class Measure(BaseModel):
    """Approach-agnostic measure payload validated from extracted JSON."""
    
    # Maßnahme
    title: str | None = None
    # kurze Projektbeschreibung
    description: str | None = None
    # Projektkategorie
    project_category: ProjectCategory | None = None
    
    # Betriebsmittel
    asset_type: AssetType
    
    # Länge Leitungsabschnitt
    length_of_power_line_km: float | None = None

    # Änderung der Übertragungskapazität
    change_in_transmission_capacity_mva: float | None = None
        
    # netztechnische Begründung für den Netzausbau 1. kurze Beschreibung
    reason_for_extension_short: str | None = None

    # netztechnische Begründung für den Netzausbau 2. Aus welchem Grund erfolgt die Netzausbaumaßnahme überwiegend?
    reason_for_extension_main_reason: str | None = None

    # Erfolgt diese Netzausbaumaßnahme, um einen prognostizierten Engpass zu beheben?
    fix_bottlebeck: bool | None = None

    # Erfolgt diese Netzausbaumaßnahme, um einen prognostizierten Engpass vorzubeugen?
    prevent_bottleneck: bool | None = None

    # optimaler Zeitpunkt der Fertigstellung aus Sicht der Netzplanung [JJJJ]
    # voraussichtlicher Zeitpunkt des Baubeginns [MM/JJJJ]
    # voraussichtlicher Zeitpunkt der Inbetriebnahme [MM/JJJJ]
    time_frame: TimeFrame | None = None

    # Kosten (geschätzt) in Euro
    cost_estimate_eur: int | None = None
    
    # Projektstatus
    project_status: str | None = None

    # Stand Genehmigungsverfahren
    approval_procedure_status: str | None = None

    # Geprüfte Alternativen zum Netzausbau
    assessed_alternatives: list[str] | None = None

    # Vorrangig betroffene Netz oder Umspannebene
    network_level: NetworkLevel 
    
    # Hauptsächlich betroffenes Teilnetzgebiet
    # von der Netzausbaumaßnahme betroffene(r) Netzknoten im überlagerten HöS-Netz
    geo_reference: GeoReference | None = None


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")
    measures: list[Measure] = Field(default_factory=list, alias="Maßnahmen")


class NetworkLevel(StrEnum):
    EHV = "Höchstspannung"
    HV = "Hochspannung"
    MV = "Mittelspannung"
    LV = "Niederspannung"
    UNKNOWN = "Unbekannt"
#    NE1
#    NE2
#    NE3
#    NE4
#    NE5
#    NE6
#    NE7


json_schema = Measure.model_json_schema()
Path("measure.schema.json").write_text(
        json.dumps(json_schema, indent=2, ensure_ascii=False),
        encoding="utf-8"
        )
