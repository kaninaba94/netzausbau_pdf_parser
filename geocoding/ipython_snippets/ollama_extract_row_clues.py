from typing import Any

from pydantic import BaseModel, ConfigDict, Field
import pandas as pd
from ollama import chat

SYSTEM_PROMPT = ""

class LocationClue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    
class RowClues(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clues: list[LocationClue] = Field(default_factory=list)

class OllamaRowClueExtractor:
    def __init__(
        self,
        model_name: str,
        examples: list[dict[str, Any]],
    ) -> None:
        self.model_name = model_name
        self.examples = examples
        self.prompt = (
            "Extrahiere anhand der unten aufgelisteten Beispiele aus der Tabellenzeile Ortsbezeichnungen, die später für fuzzy string matching mit OpenStreetMap-Features benutzt werden können." 
            + "Gib einen json-serializable string zurück: list[list[str]] \n"
            + "Die äußere Liste soll genauso lang sein wie die Anzahl der Maßnahmen, die dir übergeben werden.\n"
            + f"Beispiele:\n{self.examples}\n\n"
            + f"Tabellenzeilen:\n"
        )
    
    def extract(self, chunk: pd.DataFrame) -> list[str]:
        response = chat(
            model = self.model_name,    
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self.prompt + chunk.to_json()},
            ],
            format=RowClues.model_json_schema(),
            options={
                "temperature": 0,
                "num_ctx": int(2**15),
            },
            think=False,
        )
        return response.message.content
