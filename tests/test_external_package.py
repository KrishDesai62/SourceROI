"""Handoff integrity tests use explicit synthetic application fixtures."""
import json
from pathlib import Path
import pytest
from examples.knowledge_change.demo import workspace,external_agent
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live import assurance as a
from tools.prepare_external_evaluation import build,verify


def sources(tmp_path):
    source=workspace(tmp_path/'source');freeze(source,tmp_path/'accepted')
    before=read_config(tmp_path/'accepted');after=workspace(tmp_path/'candidate',days=14)
    spec=a.propose(before,after)
    review=a.review(spec,reviewer='synthetic fixture only',rationale='Authored change, no independent human',
        expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
    result=a.execute(before,after,spec,approval=review,callback=external_agent)
    report=tmp_path/'release.json';report.write_text(json.dumps(result))
    return Path(before['_root']),Path(after['_root']),report


def test_package_is_pending_and_contains_no_fake_people_or_runtime(tmp_path):
    before,after,report=sources(tmp_path);output=tmp_path/'bundle'
    result=build(before,after,report,output)
    assert result['new_model_calls']==0 and verify(output)['independent_validation']=='PENDING'
    assert json.loads((output/'independent/authorized-reviewers.json').read_text())==[]
    template=json.loads((output/'independent/annotation-template.json').read_text())
    assert not template['reviewers'] and not template['final']
    score=json.loads((output/'retrospective/pending-score.json').read_text())
    assert score['completed']==0 and score['semantic_correctness_rate'] is None
    assert not any(p.suffix in ('.gguf','.sqlite3') for p in output.rglob('*'))
    with pytest.raises(ValueError,match='destination exists'):build(before,after,report,output)


def test_package_tamper_and_added_file_detected(tmp_path):
    before,after,report=sources(tmp_path);output=tmp_path/'bundle';build(before,after,report,output)
    (output/'extra-review.json').write_text('{}')
    with pytest.raises(ValueError,match='added or missing'):verify(output)
    (output/'extra-review.json').unlink();(output/'README.md').write_text('changed')
    with pytest.raises(ValueError,match='integrity mismatch'):verify(output)


def test_stale_source_versions_cannot_be_packaged_as_original(tmp_path):
    before,after,report=sources(tmp_path)
    (after/'sources/policy/returns.json').write_text('{"returns_days":999}')
    with pytest.raises(ValueError,match='Source version changed'):build(before,after,report,tmp_path/'bundle')
    assert not (tmp_path/'bundle').exists()


@pytest.mark.parametrize('drift',['benchmark','configuration'])
def test_review_handoff_rejects_non_source_version_drift(tmp_path,drift):
    before,after,report=sources(tmp_path)
    if drift=='benchmark':
        path=before/'benchmark.jsonl';tasks=[json.loads(x) for x in path.read_text().splitlines()]
        tasks[0]['expected']='999';path.write_text('\n'.join(json.dumps(t) for t in tasks))
        message='Benchmark version changed'
    else:
        path=after/'project.json';cfg=json.loads(path.read_text());cfg['settings']['max_chunks']=2;path.write_text(json.dumps(cfg))
        message='Configuration changed'
    with pytest.raises(ValueError,match=message):build(before,after,report,tmp_path/'bundle')
