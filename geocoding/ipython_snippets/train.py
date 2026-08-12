import json
from lib.osm import get_all_substations, serialize_substation, search_by_osm_id
from lib.measures import serialize_measure 
import pandas as pd

with open('artefacts/embedding_match_labels.json', 'r') as f:
    embedding_match_labels = json.load(f)

from pathlib import Path
from pyrosm import OSM
if not 'substations_df' in globals(): 
    pbf_path = Path("../data/osm/germany-power.osm.pbf")
    osm_reader = OSM(
        filepath=str(pbf_path),
        bounding_box=None,
    )
    substations_df = get_all_substations(osm_reader, expand_tags=True)
    
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
)
from sentence_transformers.sentence_transformer import losses
from transformers import EarlyStoppingCallback


SUBSTATION_FIELDS = (
    "tag::name",
    "tag::operator",
    "tag::ref",
    "tag::voltage",
    "substation",
    "tag::location",
    "tag::addr:city",
    "tag::addr:street",
    "tag::addr:postcode",
)
HEURISTICS_DIR = Path('../data/auxiliary/')

def remove_keys(d: dict) -> dict:
    d_ = d.copy()
    del d_['osm_id']
    del d_['label']
    return d_

training_rows: list[dict] = []
unique_measures = set([eml['measure_row_hash'] for eml in embedding_match_labels])
for mh in unique_measures: 
    pos_osm_ids = [eml['osm_id'] for eml in embedding_match_labels if eml['measure_row_hash'] == mh and eml['label'] == 'positive']
    neg_osm_ids = [eml['osm_id'] for eml in embedding_match_labels if eml['measure_row_hash'] == mh and eml['label'] == 'negative']
    
    measures = [remove_keys(eml) for eml in embedding_match_labels if eml['measure_row_hash'] == mh]
    meas_strings = [json.dumps(m, sort_keys=True) for m in measures]
    try:
        assert len(set(meas_strings)) == 1
    except AssertionError:
        breakpoint()
    for j in range(len(pos_osm_ids)):
        pos_dict = {'positive': serialize_substation(search_by_osm_id(pos_osm_ids[j], substations_df), SUBSTATION_FIELDS)} 
        for i in range(len(neg_osm_ids)): 
            neg_dict = {'negative': serialize_substation(  search_by_osm_id(neg_osm_ids[i], substations_df), SUBSTATION_FIELDS)}
        
            training_rows.append({
                'anchor': serialize_measure(pd.Series(measures[0]), HEURISTICS_DIR), 
                **pos_dict,
                **neg_dict
            })

dataset = Dataset.from_list(training_rows)
dataset_split = dataset.train_test_split(test_size=0.2, seed=42)

train_dataset = dataset_split['train']
val_dataset = dataset_split['test']
          
model = SentenceTransformer("intfloat/multilingual-e5-small")

loss = losses.MultipleNegativesRankingLoss(
    model,
    directions=("query_to_doc",),
)

training_arguments = SentenceTransformerTrainingArguments(
    output_dir="models/geocoding-e5",
    num_train_epochs=200,
    per_device_train_batch_size=32,
    learning_rate=2e-5,
    eval_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='eval_loss',
    greater_is_better=False
)

trainer = SentenceTransformerTrainer(
    model=model,
    args=training_arguments,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    loss=loss,
    callbacks=[
        EarlyStoppingCallback(
            early_stopping_threshold=0.0,
            early_stopping_patience=10
        )
    ]
)

if __name__ == '__main__':
    trainer.train()
