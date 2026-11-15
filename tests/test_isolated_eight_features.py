"""Eight actual feature paths through cold isolated ingestion; fake HTTP model."""
import hashlib
from pathlib import Path
import pytest
from test_live import workspace,mock_model
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live import parser_boundary as boundary,assurance as a
from sourceroi.live.engine import run,evaluate_variant,optimize_configurations
from sourceroi.live.data_ci import freeze,run_data_ci
from sourceroi.live.evaluation_inputs import maintained_tasks
from sourceroi.live.diagnosis import diagnose,test_source_addition as add_source
from sourceroi.live.validation import Budget

@pytest.mark.parametrize('pillar',['dataset','valuation','optimization','data_ci','intent','maintenance','impact','diagnosis_repair'])
def test_isolated_feature_and_source_version_boundary(workspace,tmp_path,pillar):
    cfg=read_config(workspace);boundary._CACHE.clear();before=boundary._METRICS['executions']
    initial=scan_sources(cfg);source=workspace/'sources/filings/alpha.md';original=source.read_bytes()
    if pillar=='dataset':
        result=run(cfg);assert result['manifest']=={d['id']:d['fingerprint'] for d in initial[0]}
        assert result['variants'][0]['metrics']['task_count']==2
    elif pillar=='valuation':
        result=run(cfg,mode='ablation');assert len(result['impacts'])==2
        doc=run(cfg,mode='document_ablation',document_ids=['filings::alpha.md']);assert doc['impacts']
        part=evaluate_variant(cfg,load_benchmark(cfg),initial[1],[],exclude_passages=[initial[1][0]['id']]);assert initial[1][0]['id'] not in part['tasks'][0]['retrieved_chunk_ids']
    elif pillar=='optimization':
        result=optimize_configurations(cfg,quality_floor=0,min_groundedness=0,max_candidates=2)
        assert result['status'] in ('ok','no_valid_reduction')
        if result['status']=='no_valid_reduction':assert result['recommended']['decision']=='keep' and result['recommended']['accuracy']==1
        else:assert result['recommended']['accuracy']>=0
    elif pillar=='data_ci':
        cfg['model']['local_only']=True
        import json
        (workspace/'project.json').write_text(json.dumps({k:v for k,v in cfg.items() if not k.startswith('_')}));cfg=read_config(workspace)
        freeze(cfg,tmp_path/'baseline');result=run_data_ci(read_config(tmp_path/'baseline'),cfg,max_tasks=2)
        assert result['candidate_manifest']==result['baseline_manifest']
    elif pillar in ('intent','maintenance','impact'):
        freeze(cfg,tmp_path/'baseline');old=read_config(tmp_path/'baseline');source.write_bytes(original.replace(b'42',b'43'))
        spec=a.propose(old,cfg,intent={'expected_tasks':['R1'],'protected_tasks':['C1'],'declared_by':'Authored fixture','rationale':'Development source change'})
        assert spec['baseline_sources']!=spec['candidate_sources']
        if pillar=='intent':assert spec['intent']['protected_tasks']==['C1']
        elif pillar=='impact':assert all('dependency_class' in row for row in spec['impact']) and any(r['potentially_affected'] for r in spec['impact'])
        else:
            decision=a.review(spec,reviewer='Authored fixture, not independent',rationale='Explicit authored update',expected_changes={'R1':'43'},expected_evidence={'R1':[{'document_id':'filings::alpha.md','quote':'43'}]},protected_tasks=['C1'])
            revised=maintained_tasks(load_benchmark(old),spec,decision)
            assert revised[0]['expected']=='43' and load_benchmark(old)[0]['expected']=='42'
    else:
        task=load_benchmark(cfg)[0];task['evidence']=[{'document_id':'filings::alpha.md','quote':'42'}]
        row={'id':task['id'],'actual':'INSUFFICIENT_EVIDENCE','retrieved_chunk_ids':[]}
        assert diagnose(task,row,initial[1],cfg)['full_document_reference_hits']==1
        result=add_source(cfg,load_benchmark(cfg),initial[1],['filings'],'filings',Budget({'max_model_calls_per_run':8}))
        assert result['comparison']['delta_accuracy_points']>0 and not result['automatically_purchased']
        assert source.read_bytes()==original
    assert boundary._METRICS['executions']>before
    source.write_bytes(original.replace(b'42',b'44'))
    changed=scan_sources(cfg)
    assert {d['id']:d['fingerprint'] for d in changed[0]}!={d['id']:d['fingerprint'] for d in initial[0]}
