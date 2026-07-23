import re
import time
import json
import requests
import time
import gspread
from pprint import pprint
from gspread_dataframe import get_as_dataframe, set_with_dataframe

gsheets_client = gspread.service_account('../goal100-13ad64178c57.json')
worksheet = gsheets_client.open('aggregated_measures').worksheet('manually_sampled_Umspannwerke')
df = get_as_dataframe(worksheet, evaluate_formulas=True).dropna(how='all')
umspannwerke = list(df['Name'])
synonyms = (("UW", "Umspannwerk", "UA", "Station", "substation"))
literal_matches: dict[str, dict[str, list]] = {}
pattern = "|".join(re.escape(v) for v in synonyms)
for uw in umspannwerke:
    literal_matches[uw]: dict[str, list] = {}
    for syn in synonyms:
        uw_variant = re.sub(pattern, syn, uw)
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": uw_variant,
                "format": "jsonv2",
                "countrycodes": "de",
                "addressdetails": 0,
                "limit": 10,
            },
            headers={
                "User-Agent": f"netzausbauplan-geocoder/0.1 (contact: {email_id})",
            },
            timeout=30,
        )
        pprint(uw_variant)
        pprint(response.json())
