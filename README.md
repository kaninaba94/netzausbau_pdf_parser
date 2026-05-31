# Netzausbauplan Extractor

Extracts structured data from German Netzausbauplan PDFs.

## Install

```bash
pip install -e .
```

## Run

```bash
netzausbau-extract path/to/netzausbauplan.pdf --out output
```

Outputs:
- `document.json`
- `measures.csv`
- `bottlenecks.csv`
- `forecasts.csv`
- `raw_pages.json`

Optional LLM normalization:

```bash
export OPENAI_API_KEY=...
netzausbau-extract plan.pdf --out output --use-llm
```
