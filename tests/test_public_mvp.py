"""Public-data loading, contract enforcement, and protocol reliability (no paid calls)."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from sourceroi.live.adapter import attach_contract, check_acknowledgment
from sourceroi.live.config import read_config
from sourceroi.live.datasets import build_public_workspace
from sourceroi.live.grade import grade
from sourceroi.live.ingest import load_benchmark, scan_sources
from sourceroi.live.provider import ProviderError, run_chat, run_external
from sourceroi.live.public_audit import audit_retrieval
from sourceroi.live.study import run_study
from tools.validate_study import create_project, simulated_model

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def public_inputs(tmp_path):
    squad = {'data': [{'title': f'Article {i}', 'paragraphs': [{'context': f'Value {i}.', 'qas': [
        {'id': f'q{i}', 'question': f'What value does article {i} report?', 'answers': [{'text': str(i), 'answer_start': 6}]}]}]}
        for i in range(4)]}
    hotpot = [{'_id': f'h{i}', 'question': f'What does collection {i} state?', 'answer': 'yes', 'type': 'bridge',
               'context': [[f'First {i}', [f'First fact {i}.']], [f'Second {i}', [f'Second fact {i}.']]],
               'supporting_facts': [[f'First {i}', 0], [f'Second {i}', 0]]} for i in range(4)]
    a, b = tmp_path/'squad.json', tmp_path/'hotpot.json'
    a.write_text(json.dumps(squad)); b.write_text(json.dumps(hotpot))
    return a, b


def test_published_schema_import_preserves_answers_evidence_and_license(public_inputs, tmp_path):
    a, b = public_inputs
    out = tmp_path/'public'
    result = build_public_workspace(a, b, out, per_dataset=4)
    assert result['tasks'] == 8
    cfg = read_config(out)
    tasks = load_benchmark(cfg)
    assert {t['dataset'] for t in tasks} == {'squad', 'hotpot'}
    assert {t['split'] for t in tasks} == {'development', 'heldout'}
    assert all(t['evidence'] and t['scoring'] == 'qa_exact' for t in tasks)
    assert all(t['review_status'] == 'published_dataset_annotations' for t in tasks)
    assert 'by-sa/4.0' in json.loads((out/'provenance.json').read_text())['license']
    assert grade('The YES!', next(t for t in tasks if t['dataset'] == 'hotpot'))
    before = (out/'benchmark.jsonl').read_bytes()
    with pytest.raises(ValueError, match='never overwritten'):
        build_public_workspace(a, b, out, per_dataset=4)
    assert (out/'benchmark.jsonl').read_bytes() == before


def test_invalid_answer_span_never_publishes_workspace(public_inputs, tmp_path):
    a, b = public_inputs
    data = json.loads(a.read_text())
    data['data'][0]['paragraphs'][0]['qas'][0]['answers'][0]['answer_start'] = 0
    a.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='answer span'):
        build_public_workspace(a, b, tmp_path/'bad', per_dataset=2)
    assert not (tmp_path/'bad/project.json').exists()


def test_actual_downloaded_public_documents_ingest_and_audit():
    root = ROOT/'workspace/public-validation'
    cfg = read_config(root)
    docs, _ = scan_sources(cfg)
    tasks = load_benchmark(cfg)
    assert len(docs) == 44 and len(tasks) == 8
    report = audit_retrieval(cfg)
    assert report['model_calls'] == 0
    assert report['answer_accuracy'] is None and report['input_tokens'] is None
    assert set(report['comparisons']) >= {'original', 'top_k', 'context_budget', 'threshold', 'task_aware'}
    assert report['provenance_sha256']


def test_qa_exact_preserves_all_published_alternatives():
    task = {'expected': 'American football', 'accepted_answers': ['American football', 'football'], 'scoring': 'qa_exact'}
    assert grade('The football.', task)
    assert not grade('basketball', task)


def payload():
    return {'task_id': 'q', 'question': 'Which value?', 'allowed_source_ids': ['a'],
            'excluded_source_ids': ['b'], 'excluded_document_ids': ['a::old'], 'request_filter_ack': True}


def acknowledgment(request):
    return {'request_id': request['request_id'], 'enforced_restrictions': {k: request[k] for k in
        ('allowed_source_ids', 'excluded_source_ids', 'excluded_document_ids')},
        'retrieval_controls_applied': request['retrieval_controls']}


def test_v2_exact_acknowledgment_and_unsupported_controls():
    request = attach_contract(payload(), {'protocol_version': 2, 'capabilities': ['max_chunks']}, {'max_chunks': 1})
    response = acknowledgment(request)
    check_acknowledgment(request, response)
    response['retrieval_controls_applied'] = {'max_chunks': True}
    with pytest.raises(ValueError, match='exact requested retrieval'):
        check_acknowledgment(request, response)
    with pytest.raises(ValueError, match='v1'):
        attach_contract(payload(), {}, {'max_chunks': 1})
    with pytest.raises(ValueError, match='capabilities'):
        attach_contract(payload(), {'protocol_version': 2}, {'max_chunks': 1})


@pytest.mark.parametrize('field', ['allowed_source_ids', 'excluded_source_ids', 'excluded_document_ids', 'request_id'])
def test_v2_wrong_filter_ack_invalidates_experiment(field):
    request = attach_contract(payload(), {'protocol_version': 2}, {})
    response = deepcopy(acknowledgment(request))
    if field == 'request_id':
        response[field] = 'wrong'
    else:
        response['enforced_restrictions'][field] = []
    with pytest.raises(ValueError, match='acknowledge|acknowledgment'):
        check_acknowledgment(request, response)


def test_external_v2_checks_request_and_rejects_lying_ack(monkeypatch):
    cfg = {'agent': {'url': 'http://localhost:1/evaluate', 'protocol_version': 2, 'capabilities': ['max_chunks']}}
    def post(url, request, *args):
        return {'answer': 'answer', 'filter_applied': True, 'usage': {}, **acknowledgment(request)}
    monkeypatch.setattr('sourceroi.live.provider._post', post)
    result = run_external('q', ['a'], [], [], cfg, 'id', retrieval_controls={'max_chunks': 1})
    assert result['input_tokens'] is None and result['model_cost_usd'] is None
    monkeypatch.setattr('sourceroi.live.provider._post', lambda *args: {'answer': 'answer', 'filter_applied': True})
    with pytest.raises(ProviderError, match='acknowledgment'):
        run_external('q', ['a'], [], [], cfg, 'id')


def test_reference_generic_agent_enforces_controls(tmp_path):
    create_project(tmp_path)
    cfg = read_config(tmp_path)
    spec = importlib.util.spec_from_file_location('reference_agent', ROOT/'examples/agent/server.py')
    agent = importlib.util.module_from_spec(spec); spec.loader.exec_module(agent)
    request = attach_contract({'task_id': 'q', 'question': 'Aster revenue', 'allowed_source_ids': ['reports'],
        'excluded_source_ids': ['cash', 'commentary'], 'excluded_document_ids': [], 'request_filter_ack': True},
        {'protocol_version': 2, 'capabilities': ['max_chunks']}, {'max_chunks': 1})
    response = agent.evaluate(request, cfg)
    check_acknowledgment(request, response)
    assert response['usage'] == {}
    assert len(response['citations']) == 1 and response['citations'][0].startswith('reports::')
    request = attach_contract({**request, 'excluded_document_ids': [response['citations'][0].split('#chunk')[0]]},
        {'protocol_version': 2, 'capabilities': ['max_chunks']}, {'max_chunks': 1})
    filtered = agent.evaluate(request, cfg)
    assert all(c.split('#chunk')[0] not in request['excluded_document_ids'] for c in filtered['citations'])


def test_provider_actual_model_id_and_truncated_completion(monkeypatch):
    monkeypatch.setattr('sourceroi.live.provider._post', lambda *args: {'model': 'resolved-model-revision',
        'choices': [{'finish_reason': 'length', 'message': {'content': '{"answer":"42","citations":[]}'}}],
        'usage': {'prompt_tokens': 123, 'completion_tokens': 7}})
    cfg = {'model': {'name': 'alias', 'base_url': 'http://localhost:1/v1',
                     'input_price_per_million_usd': 2, 'output_price_per_million_usd': 4}}
    response = run_chat('q', [], cfg)
    assert response['model_name'] == 'resolved-model-revision'
    assert response['input_tokens'] == 123 and response['output_tokens'] == 7
    assert response['model_cost_usd'] == pytest.approx(.000274)
    assert response['response_complete'] is False


def test_malformed_usage_is_explicit_provider_error(monkeypatch):
    monkeypatch.setattr('sourceroi.live.provider._post', lambda *args: {'choices': [{'message': {'content': 'x'}}], 'usage': ['bad']})
    with pytest.raises(ProviderError, match='usage must be an object'):
        run_chat('q', [], {'model': {'name': 'mock', 'base_url': 'http://localhost:1'}})


def test_single_heldout_pass_and_actionable_inconclusive_report(tmp_path, monkeypatch):
    create_project(tmp_path)
    monkeypatch.setattr('sourceroi.live.engine.run_chat', simulated_model)
    progress = []
    report = run_study(read_config(tmp_path), repeats=2, min_groundedness=None, notify=progress.append)
    assert all(len(e['runs']) == (2 if e['partition'] == 'development' else 1) for e in report['experiments'])
    assert report['recommendation']['deployment_verdict'] == 'Inconclusive / insufficient evidence'
    assert report['recommendation']['automatically_applied'] is False
    assert report['recommendation']['per_task_kind']
    assert report['recommendation']['passage_changes']
    assert progress[-1]['event'] == 'completed'
    assert all(not any(key in event for key in ('question', 'answer', 'context', 'api_key')) for event in progress)


def test_reference_agent_v2_over_actual_local_http(tmp_path):
    import queue
    import re
    import subprocess
    import sys
    import threading
    create_project(tmp_path)
    process = subprocess.Popen([sys.executable, '-u', str(ROOT/'examples/agent/server.py'),
                                '--project', str(tmp_path), '--port', '0'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = queue.Queue()
    threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
    try:
        line = output.get(timeout=10)
        endpoint = re.search(r'http://127\.0\.0\.1:\d+/evaluate', line)
        assert endpoint, 'Reference agent did not announce its localhost endpoint'
        cfg = {'agent': {'url': endpoint.group(), 'protocol_version': 2,
                         'capabilities': ['max_chunks'], 'timeout_seconds': 5}}
        result = run_external('Aster revenue', ['reports'], ['cash', 'commentary'], [], cfg, 'case',
                              retrieval_controls={'max_chunks': 1})
        assert len(result['citations']) == 1
        assert result['citations'][0].startswith('reports::')
        assert result['input_tokens'] is None and result['model_cost_usd'] is None
        excluded = run_external('Aster revenue', [], ['reports', 'cash', 'commentary'], [], cfg, 'case')
        assert excluded['answer'] == 'INSUFFICIENT_EVIDENCE' and not excluded['citations']
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)
        process.stdout.close(); process.stderr.close()


def test_public_import_cli_and_frozen_partition_isolation(public_inputs, tmp_path, capsys):
    from sourceroi.live.cli import main
    a, b = public_inputs
    out = tmp_path/'cli-public'
    assert main(['public-benchmark', '--squad', str(a), '--hotpot', str(b), '--per-dataset', '4', '--output', str(out)]) == 0
    assert json.loads(capsys.readouterr().out)['tasks'] == 8
    cfg = read_config(out)
    tasks = load_benchmark(cfg)
    dev_docs = {e['document_id'] for t in tasks if t['split'] == 'development' for e in t['evidence']}
    held_docs = {e['document_id'] for t in tasks if t['split'] == 'heldout' for e in t['evidence']}
    assert dev_docs.isdisjoint(held_docs)


def test_partial_tasks_survive_failure_without_exposing_content_in_logs(tmp_path, monkeypatch, caplog):
    import logging
    from sourceroi.live import db
    create_project(tmp_path)
    cfg = read_config(tmp_path)
    attempts = []
    def failing(question, context, config):
        attempts.append(question)
        if len(attempts) == 2:
            raise ProviderError('simulated timeout')
        return simulated_model(question, context, config)
    monkeypatch.setattr('sourceroi.live.engine.run_chat', failing)
    caplog.set_level(logging.INFO, logger='sourceroi.experiments')
    with pytest.raises(ProviderError):
        run_study(cfg, min_groundedness=None)
    report = db.get(cfg, db.list_runs(cfg)[0]['id'])['report']
    assert report['status'] == 'incomplete'
    entry = report['experiments'][-1]
    assert len(entry['incomplete_tasks']) == 1
    assert entry['active_request']['status'] == 'unvalidated'
    assert all(question not in caplog.text for question in attempts)


def test_truncated_answers_do_not_pass_accuracy(tmp_path, monkeypatch):
    from sourceroi.live.engine import evaluate_variant
    create_project(tmp_path)
    cfg = read_config(tmp_path)
    def truncated(*args):
        result = simulated_model(*args)
        result.update(response_complete=False, finish_reason='length')
        return result
    monkeypatch.setattr('sourceroi.live.engine.run_chat', truncated)
    tasks = load_benchmark(cfg)[:1]
    variant = evaluate_variant(cfg, tasks, scan_sources(cfg)[1], [])
    assert variant['tasks'][0]['actual'] == tasks[0]['expected']
    assert variant['metrics']['accuracy'] == 0


def test_frozen_public_snapshot_tampering_is_detected(public_inputs, tmp_path):
    a, b = public_inputs
    out = tmp_path/'frozen'
    build_public_workspace(a, b, out, per_dataset=4)
    cfg = read_config(out)
    doc = next((out/'sources/squad').glob('*.txt'))
    doc.write_text(doc.read_text()+' Unrecorded modification.')
    with pytest.raises(ValueError, match='snapshot changed'):
        audit_retrieval(cfg)


def test_model_identity_changes_invalidate_policy_comparison(tmp_path, monkeypatch):
    create_project(tmp_path)
    calls = []
    def drifting(*args):
        calls.append(1)
        result = simulated_model(*args)
        result['model_name'] = 'revision-a' if len(calls) == 1 else 'revision-b'
        return result
    monkeypatch.setattr('sourceroi.live.engine.run_chat', drifting)
    report = run_study(read_config(tmp_path), min_groundedness=None)
    assert report['execution_comparable'] is False
    assert report['observed_verdict'] == 'inconclusive_model_changed'
    assert report['recommendation']['deployment_verdict'] == 'Inconclusive / insufficient evidence'
