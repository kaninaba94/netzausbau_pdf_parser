from vnbdigital_client import VNBDigitalClient
import argparse
import requests
from pathlib import Path

client = VNBDigitalClient()

counter = 0
for op_id in range(771,10000):
    details = client.get_operator_details(str(op_id))
    if details is None:
        continue
    print(f'operator\t{details.name}')
    if len(details.raw['documents']) != 0:
        counter += 1
    else:
        continue

    out_dir = (Path(__file__).parent.parent / 'input' / f'{str(details.raw["_id"]).zfill(5)}_{details.raw["name"]}'.replace('/', '_'))
    out_dir.mkdir(exist_ok=True)

    for doc in details.raw['documents']:
        print(f'\t{doc["name"]}')
        response = requests.get(f'https://www.vnbdigital.de/gateway/files?serviceName=vnb&fileId={doc["_id"]}', timeout=120)
        response.raise_for_status()

        out_path = out_dir / doc["name"] 
        if out_path.exists():
            out_path = out_dir / f'{out_path.stem}_1{out_path.suffix}'
        out_path.write_bytes(response.content)


print(f"{counter} VNB haben Dokumente")

