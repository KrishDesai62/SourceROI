"""Data-only overlap audit, independent of model scores; never removes test cases."""
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.datasets import squad_records,hotpot_records,digest
from sourceroi.live.ingest import load_benchmark,scan_sources


def shingles(text):
    words=re.findall(r'\w+',text.lower())
    if len(words)<40:return set()
    return {tuple(words[i:i+5]) for i in range(len(words)-4)}


def main():
    cfg=read_config('workspace/reliability-24');tasks={t['id']:t for t in load_benchmark(cfg)}
    docs,_=scan_sources(cfg);by_id={d['id']:d for d in docs}; ownership={}
    for iterator in (squad_records('workspace/.cache/public-qa/squad.json'),hotpot_records('workspace/.cache/public-qa/hotpot.json')):
        for record in iterator:
            if record['id'] not in tasks:continue
            for title,text in record['documents']:
                did=record['dataset']+'::'+digest(title+'\n'+text)+'.txt'
                ownership.setdefault(did,set()).add(tasks[record['id']]['split'])
    shared=[did for did,splits in ownership.items() if len(splits)>1]
    current=[]
    for did,doc in by_id.items():
        text=(Path(cfg['_root'])/doc['path']).read_text();current.append((did,ownership[did],shingles(text)))
    prior=[];prior_titles=set()
    for root in ('workspace/public-validation','workspace/local-llm-96'):
        p=read_config(root)
        for d in scan_sources(p)[0]:
            prior_titles.add(' '.join(d['title'].lower().replace('_',' ').split()))
            prior.append((d['id'],shingles((Path(p['_root'])/d['path']).read_text())))
    near=[]
    for i,(did,splits,a) in enumerate(current):
        if not a:continue
        candidates=[(other,b) for other,osplits,b in current[i+1:] if osplits!=splits]+prior
        for other,b in candidates:
            if not b or min(len(a),len(b))/max(len(a),len(b))<.9:continue
            score=len(a&b)/len(a|b)
            if score>=.9:near.append({'document':did,'other':other,'fivegram_jaccard':round(score,4)})
    titles={' '.join(d['title'].lower().replace('_',' ').split()) for d in docs}
    result={'kind':'post_evaluation_data_only_overlap_audit','tasks':len(tasks),
            'shared_document_ids_across_splits':shared,'prior_exposed_title_overlap':sorted(titles&prior_titles),
            'near_duplicate_threshold':.9,'fivegram_near_duplicates':near,'test_cases_changed':False,
            'limitations':'Lexical shingle checks cannot prove absence of semantic, entity, or pretraining leakage.'}
    Path('docs/artifacts/reliability-split-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='limitations'})

if __name__=='__main__':main()
