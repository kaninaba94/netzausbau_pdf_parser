#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pdfplumber
from pdfplumber.display import PageImage
import re

def open_file_with_system_viewer(output_path: Path) -> None:
    if sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(output_path)], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(output_path)], check=False)
    elif sys.platform == "win32":
        subprocess.run(["cmd", "/c", "start", "", str(output_path)], check=False)


def save_word_left_boundary_histogram(
    pdf_path: Path,
    page_number: int,
    output_path: Path,
    bin_width: float,
    intralinecharacterdistancetolerance: int, 
    interlinecharacterdistancetolerance: int
) -> None:
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]
        words = page.extract_words(
            keep_blank_chars=True,
            use_text_flow=False,
            x_tolerance=intralinecharacterdistancetolerance,
            y_tolerance=interlinecharacterdistancetolerance,
        )
        page_img = PageImage(page, resolution=300) 
        page_img = page_img.outline_words(
            x_tolerance=intralinecharacterdistancetolerance,
            y_tolerance=interlinecharacterdistancetolerance,
        ) 
        page_img.save('word_boundaries_debug.png')
        
        print(f"{len(words)=}")
    
    import random
   
    pattern = re.compile('.*beding.*')
    for word in words:
        if pattern.match(word['text']):
            print(f"{word=}")
    word_left_boundaries = [float(word["x0"]) for word in words]
    if not word_left_boundaries:
        raise RuntimeError(f"No words found on page {page_number}")

    min_x = min(word_left_boundaries)
    max_x = max(word_left_boundaries)
    bin_count = int((max_x - min_x) / bin_width) + 2
    bins = [min_x + bin_width * bin_index for bin_index in range(bin_count)]
    
    words350 = sorted([w for w in words if 350 <= w['x0'] <= 365], key=lambda w: w['x0'])
    #print(f"{[(w['text'], w['x0']) for w in words350]=}")
    #import ipdb; ipdb.set_trace()

    plt.figure(figsize=(14, 6))
    plt.hist(word_left_boundaries, bins=bins)
    plt.xlabel("word x0 / left boundary")
    plt.xticks(list(range(0, int(max_x), 50)))

    plt.ylabel("count")
    plt.title(f"Word left-boundary histogram, page {page_number}")
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


def main() -> None:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("pdf_path", type=Path)
    argument_parser.add_argument("-p", "--page-number", type=int, required=True)
    argument_parser.add_argument("-o", "--output-path", type=Path, default=Path("word_left_boundaries.png"))
    argument_parser.add_argument("--bin-width", type=float, default=2.0)
    argument_parser.add_argument("--no-open", action="store_true")

    arguments = argument_parser.parse_args()

    table_settings = {
          "vertical_strategy": "lines",
          "horizontal_strategy": "lines",
          "explicit_vertical_lines": [],
          "explicit_horizontal_lines": [],
          "snap_tolerance": 3,
          "snap_x_tolerance": 3,
          "snap_y_tolerance": 3,
          "join_tolerance": 3,
          "join_x_tolerance": 3,
          "join_y_tolerance": 3,
          "edge_min_length": 3,
          "edge_min_length_prefilter": 1,
          "min_words_vertical": 3,
          "min_words_horizontal": 1,
          "intersection_tolerance": 3,
          "intersection_x_tolerance": 3,
          "intersection_y_tolerance": 3,
          "text_x_tolerance": 7,
          "text_y_tolerance": 3,
          "text_keep_blank_chars": True
        }
    
    save_word_left_boundary_histogram(
        pdf_path=arguments.pdf_path,
        page_number=arguments.page_number,
        output_path=arguments.output_path,
        bin_width=arguments.bin_width,
        interlinecharacterdistancetolerance=table_settings['text_y_tolerance'],
        intralinecharacterdistancetolerance=table_settings['text_x_tolerance']
    )

    print(f"Saved: {arguments.output_path}")

    if not arguments.no_open:
        open_file_with_system_viewer(arguments.output_path)


if __name__ == "__main__":
    main()
