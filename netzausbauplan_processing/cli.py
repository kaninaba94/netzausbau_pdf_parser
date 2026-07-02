from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from netzausbauplan_processing.extraction.extractor import extract_netzausbauplan
from netzausbauplan_processing.writer import write_outputs

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def extract(
    pdf: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path = typer.Option(Path("netzausbau_output"), "--out", "-o"),
    use_llm: bool = typer.Option(False, "--use-llm"),
) -> None:
    result, pages = extract_netzausbauplan(pdf_path=pdf, use_llm=use_llm)
    write_outputs(result=result, pages=pages, output_directory=out)

    console.print(f"[green]Done[/green] {pdf}")
    console.print(f"Measures: {len(result.measures)}")
    console.print(f"Bottlenecks: {len(result.bottlenecks)}")
    console.print(f"Forecasts: {len(result.forecasts)}")
    console.print(f"Output: {out}")


if __name__ == "__main__":
    app()
