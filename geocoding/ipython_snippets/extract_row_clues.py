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
        examples: list[dict[str, Any]]
    ) -> None:
        self.model_name = model_name
        self.examples = examples
    
    def extract(self, row: pd.Series) -> list[str]:
        user_prompt = (
            "Extrahiere anhand der unten aufgelisteten Beispiele aus der Tabellenzeile Ortsbezeichnungen, die später für fuzzy string matching mit OpenStreetMap-Features benutzt werden können. \n\n"
            + f"Beispiele:\n{self.examples}\n\n"
            + f"Tabellenzeile\n{row}"
        )
        response = chat(
            model = self.model_name,    
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            format=RowClues.model_json_schema(),
            options={
                "temperature": 0,
                "num_ctx": 8192,
            },
            think=False,
        )
        return response.message.content
