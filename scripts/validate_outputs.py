#!/usr/bin/env python3
from pathlib import Path
import json
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT/'data/processed/role_capability_sfia_triples.csv',
    ROOT/'data/processed/role_level_sfia_level_summary.csv',
    ROOT/'data/processed/graph_nodes.csv',
    ROOT/'data/processed/graph_edges.csv',
    ROOT/'data/processed/role_capability_sfia_graph.json',
]
missing=[str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit('Missing outputs:\n'+'\n'.join(missing))
triples=pd.read_csv(required[0])
summary=pd.read_csv(required[1])
graph=json.loads(required[4].read_text(encoding='utf-8'))
assert len(triples)>0
assert len(summary)>0
assert len(graph['nodes'])>0 and len(graph['edges'])>0
print('Validation passed')
print('Triples rows:', len(triples))
print('Summary rows:', len(summary))
print('Graph nodes:', len(graph['nodes']))
print('Graph edges:', len(graph['edges']))
