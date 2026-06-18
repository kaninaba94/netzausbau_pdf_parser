from __future__ import annotations

import json
import os
from typing import Any

import httpx

from netzausbau_extractor.models import ExtractionResult


SYSTEM_PROMPT = """You extract structured data from German Netzausbauplan PDFs.
Return only valid JSON matching the given schema. Preserve evidence page numbers.
Do not invent values. Use null when unknown."""


def normalize_with_llm(result: ExtractionResult) -> ExtractionResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --use-llm")

    payload: dict[str, Any] = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "schema": ExtractionResult.model_json_schema(),
                        "candidate_extraction": result.model_dump(),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]
    return ExtractionResult.model_validate_json(content)
