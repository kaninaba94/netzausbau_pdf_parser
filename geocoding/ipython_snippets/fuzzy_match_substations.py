from typing import Tuple
from rapidfuzz import process, fuzz

def fuzzy_match_substations(transformer_station_name: str) -> list[Tuple[str, float, int]]:
    choices_by_index = substations["tag::name"].dropna().to_dict()

    return process.extract(
        query=transformer_station_name,
        choices=choices_by_index,
        scorer=fuzz.WRatio,
        score_cutoff=75,
        limit=10,
    )

if __name__ == '__main__':
    transformer_station_name = input('Type location name of the Umspannwerk   ')
    matches = fuzzy_match_substations(transformer_station_name) 
    matched_substations = substations.loc[[match[2] for match in matches]]
