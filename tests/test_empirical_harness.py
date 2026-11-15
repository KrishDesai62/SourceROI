"""Offline experiment checks do not assert real-model accuracy."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from tools.run_empirical_experiment import metrics,conventional,execute,check_freeze


def test_metrics_separate_false_abstention_and_unsupported_rejection():
    tasks=[{'id':'supported','expected':'14','scoring':'numeric'},{'id':'unsupported','expected':'INSUFFICIENT_EVIDENCE'}]
    rows=[{'id':'supported','actual':'INSUFFICIENT_EVIDENCE','citations':[]},
          {'id':'unsupported','actual':'INSUFFICIENT_EVIDENCE','citations':[]}]
    result=metrics(rows,tasks)
    assert result['supported_accuracy']==0 and result['supported_false_abstention_rate']==1
    assert result['unsupported_rejection_rate']==1 and result['citation_id_failure_rate'] is None
    assert result['semantic_citation_correctness'] is None


def test_full_experiment_pending_authorization_cannot_import_or_run_model(tmp_path):
    root=tmp_path/'bench';root.mkdir();(root/'freeze-manifest.json').write_text('{}')
    auth=tmp_path/'auth.json';auth.write_text(json.dumps({'scope':'benchmark','status':'pending'}))
    with patch('tools.run_empirical_experiment.Experiment',side_effect=AssertionError('No runtime before authorization')):
        with pytest.raises(ValueError,match='no approved'):execute(root,tmp_path/'never',auth)
    assert not (tmp_path/'never').exists()


def test_freeze_drift_rejected_before_model(tmp_path):
    (tmp_path/'file').write_text('changed')
    (tmp_path/'freeze-manifest.json').write_text(json.dumps({'file':'0'*64}))
    with pytest.raises(ValueError,match='Frozen'):check_freeze(tmp_path)


def test_conventional_baseline_requires_citations_version_and_review(tmp_path):
    from sourceroi.live.config import read_config
    from sourceroi.live.ingest import scan_sources
    from sourceroi.live.data_ci import digest
    (tmp_path/'docs').mkdir();(tmp_path/'docs/a.txt').write_text('Limit is 14.')
    (tmp_path/'benchmark.jsonl').write_text('')
    (tmp_path/'project.json').write_text(json.dumps({'sources':[{'id':'policy','path':'docs','jurisdiction':'US'}],
        'model':{'name':'never-called','base_url':'http://127.0.0.1:1/v1'}}))
    cfg=read_config(tmp_path);docs,chunks=scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs}
    task={'id':'limit','expected':'14','scoring':'numeric','evidence':[{'document_id':'policy::a.txt','quote':'14'}]}
    row={'id':'limit','actual':'14','citations':[chunks[0]['id']],'answer_contract_valid':True,
         'knowledge_manifest':manifest,'knowledge_version':digest(manifest),'response_complete':True}
    assert conventional(cfg,[task],[row],{'limit':chunks})['verdict']=='REVIEW'
    row['citations']=['forged']
    assert conventional(cfg,[task],[row],{'limit':chunks})['verdict']=='BLOCK'
    row['citations']=[chunks[0]['id']];row['knowledge_version']='wrong'
    assert conventional(cfg,[task],[row],{'limit':chunks})['verdict']=='INCONCLUSIVE'


def test_actual_smoke_replay_keeps_baseline_and_candidate_identity(tmp_path):
    from tools.analyze_empirical_smoke import analyze
    root=Path(__file__).resolve().parents[1]
    benchmark=root/'workspace/execution-resolution/benchmark-v1'
    smoke=root/'docs/artifacts/execution-resolution/native-smoke'
    if not (smoke/'accepted-business.json').exists():pytest.skip('Optional immutable real smoke artifacts not present')
    import os
    relative=Path(os.path.relpath(benchmark,Path.cwd()))
    output=tmp_path/'analysis.json'
    result=analyze(relative,smoke,output)
    release=json.loads((tmp_path/'analysis-incomplete-strict-release.json').read_text())
    for version in ('baseline','candidate'):
        original=json.loads((smoke/('accepted-business.json' if version=='baseline' else 'candidate-business.json')).read_text())['row']
        assert release[version]['tasks'][0]['knowledge_manifest']==original['knowledge_manifest']
    assert result['source_roi_incomplete_workflow']=='INCONCLUSIVE' and result['model_calls_in_this_analysis']==0
