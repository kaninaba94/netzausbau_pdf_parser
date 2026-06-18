from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz
import torch
import typer
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizerBase

from netzausbau_extractor.schema import SCHEMA_PATH

app = typer.Typer(no_args_is_help=True)
DEFAULT_MODEL = "numind/NuExtract-1.5"
DEFAULT_WINDOW_SIZE = 4000
DEFAULT_OVERLAP = 128
DEFAULT_MAX_LENGTH = 20_000
DEFAULT_MAX_NEW_TOKENS = 6000


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_input_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        document = fitz.open(path)
        return "\n\n".join(page.get_text("text") for page in document)
    return path.read_text(encoding="utf-8")


def template_to_text(template: dict[str, Any]) -> str:
    return json.dumps(template, ensure_ascii=False, indent=2)


def clean_json_text(text: str) -> str:
    text = text.strip()
    return text.replace("\\#", "#").replace("\\&", "&")


def build_single_pass_prompt(text: str, template_text: str) -> str:
    return f"""<|input|>
### Template:
{template_text}
### Text:
{text}

<|output|>
"""


def build_continuation_prompt(chunk: str, template_text: str, current: str) -> str:
    return f"""<|input|>
### Template:
{template_text}
### Current:
{current}
### Text:
{chunk}

<|output|>{{"""


def split_document(text: str, tokenizer: PreTrainedTokenizerBase, window_size: int, overlap: int) -> list[str]:
    tokens = tokenizer.tokenize(text)
    if len(tokens) <= window_size:
        return [text]

    chunks: list[str] = []
    step = window_size - overlap
    for i in range(0, len(tokens), step):
        chunk_tokens = tokens[i : i + window_size]
        chunks.append(tokenizer.convert_tokens_to_string(chunk_tokens))
        if i + len(chunk_tokens) >= len(tokens):
            break
    return chunks


def handle_broken_output(pred: str, prev: str) -> str:
    pred = clean_json_text(pred)
    try:
        json.loads(pred)
    except json.JSONDecodeError:
        return prev
    return pred


def decode_output(tokenizer: PreTrainedTokenizerBase, output_ids: torch.Tensor) -> str:
    response = tokenizer.decode(output_ids, skip_special_tokens=True)
    if "<|output|>" not in response:
        return clean_json_text(response)
    return clean_json_text(response.rsplit("<|output|>", maxsplit=1)[-1])


def generate_response(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    prompt: str,
    *,
    max_length: int,
    max_new_tokens: int,
) -> str:
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
    ).to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return decode_output(tokenizer, outputs[0])


def extract_with_sliding_window(
    text: str,
    template_text: str,
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    *,
    window_size: int,
    overlap: int,
    max_length: int,
    max_new_tokens: int,
) -> str:
    chunks = split_document(text, tokenizer, window_size, overlap)
    prev = template_text
    for index, chunk in enumerate(chunks, start=1):
        typer.echo(f"Processing chunk {index}/{len(chunks)}...")
        prompt = build_continuation_prompt(chunk, template_text, prev)
        pred = generate_response(
            model,
            tokenizer,
            prompt,
            max_length=max_length,
            max_new_tokens=max_new_tokens,
        )
        prev = handle_broken_output(pred, prev)
    return prev


def extract_with_nuextract(
    text: str,
    template: dict[str, Any],
    *,
    model_name: str = DEFAULT_MODEL,
    window_size: int = DEFAULT_WINDOW_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    max_length: int = DEFAULT_MAX_LENGTH,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
) -> dict[str, Any]:
    # Phi-3 is built into transformers; trust_remote_code=True pulls outdated
    # cached hub code that breaks DynamicCache (seen_tokens removed in 4.48+).
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=False,
    )

    template_text = template_to_text(template)
    token_count = len(tokenizer.tokenize(text))

    if token_count <= window_size:
        prompt = build_single_pass_prompt(text, template_text)
        result = generate_response(
            model,
            tokenizer,
            prompt,
            max_length=max_length,
            max_new_tokens=max_new_tokens,
        )
    else:
        typer.echo(f"Document has {token_count} tokens; using sliding window (window_size={window_size}).")
        result = extract_with_sliding_window(
            text,
            template_text,
            model,
            tokenizer,
            window_size=window_size,
            overlap=overlap,
            max_length=max_length,
            max_new_tokens=max_new_tokens,
        )

    return json.loads(result)


@app.command()
def extract(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    schema: Path = typer.Option(
        SCHEMA_PATH,
        "--schema",
        "-s",
        exists=True,
        dir_okay=False,
        readable=True,
        help="JSON template file for NuExtract.",
    ),
    out: Path = typer.Option(Path("output/extracted"), "--out", "-o"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    window_size: int = typer.Option(
        DEFAULT_WINDOW_SIZE,
        "--window-size",
        help="Token window per chunk; documents longer than this use sliding-window continuation.",
    ),
    overlap: int = typer.Option(
        DEFAULT_OVERLAP,
        "--overlap",
        help="Token overlap between consecutive chunks.",
    ),
    max_length: int = typer.Option(
        DEFAULT_MAX_LENGTH,
        "--max-length",
        help="Maximum tokenizer input length per forward pass.",
    ),
    max_new_tokens: int = typer.Option(
        DEFAULT_MAX_NEW_TOKENS,
        "--max-new-tokens",
        help="Maximum tokens to generate per forward pass.",
    ),
) -> None:
    template = load_schema(schema)
    text = load_input_text(input_path)
    result = extract_with_nuextract(
        text,
        template,
        model_name=model,
        window_size=window_size,
        overlap=overlap,
        max_length=max_length,
        max_new_tokens=max_new_tokens,
    )

    out.mkdir(parents=True, exist_ok=True)
    out_path = out / f"{input_path.stem}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(out_path)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
