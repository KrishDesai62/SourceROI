"""Standalone study tests use a labeled synthetic adapter, never paid models."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from sourceroi.live.config import read_config
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.grounding import evidence_key, score_review, load_reviews
from sourceroi.live.ingest import load_benchmark, scan_sources
from sourceroi.live.policies import select_context, task_kind
from sourceroi.live.study import run_study, export_study
from sourceroi.live.validation import split_tasks
from tools.validate_study import create_project, simulated_model


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    create_project(tmp_path)
    monkeypatch.setattr('sourceroi.live.engine.run_chat', simulated_model)
    return read_config(tmp_path)


def test_multi_document_quality_loss_is_rejected(cfg):
    tasks = [t for t in load_benchmark(cfg) if t['split'] == 'development']
    chunks = scan_sources(cfg)[1]
    cfg['settings']['retrieval_policy'] = {'name': 'top_k', 'k': 1}
    reduced = evaluate_variant(cfg, tasks, chunks, [])
    assert reduced['metrics']['accuracy'] < 1
    cfg['settings'].pop('retrieval_policy')
    report = run_study(cfg, quality_floor=1, min_groundedness=None)
    selected = next(e for e in report['experiments'] if e['name'] == 'sourceroi' and e['partition'] == 'heldout')
    assert selected['runs'][0]['metrics']['accuracy'] == 1
    assert selected['policy']['name'] == 'learned'
    assert report['deployment'] == 'requires_further_testing'
    assert report['review_status'] == 'unreviewed_or_incomplete'


def test_freeze_precedes_all_heldout_calls(cfg, monkeypatch):
    from sourceroi.live import study
    real = study.evaluate_variant
    heldout_started = False
    def spy(configuration, tasks, *args, **kwargs):
        nonlocal heldout_started
        held = all(t['split'] == 'heldout' for t in tasks)
        assert not heldout_started or held
        heldout_started |= held
        return real(configuration, tasks, *args, **kwargs)
    monkeypatch.setattr(study, 'evaluate_variant', spy)
    report = run_study(cfg, min_groundedness=None)
    assert heldout_started
    assert report['frozen_policy_sha256']
    assert set(report['frozen_policies']) == {'original','top_k','context_budget','threshold','cheapest','task_aware','sourceroi'}


def test_no_spend_remote_blocked_before_execution(cfg):
    cfg['model']['base_url'] = 'https://example.com/v1'
    with patch('sourceroi.live.study.evaluate_variant') as model:
        with pytest.raises(ValueError, match='approved spend'):
            run_study(cfg)
        model.assert_not_called()


def test_unknown_usage_cannot_prove_advantage(cfg, monkeypatch):
    cfg['settings'].pop('max_estimated_model_cost_usd')
    def missing(*args):
        result = simulated_model(*args)
        result.update(input_tokens=None, output_tokens=None, model_cost_usd=None)
        return result
    monkeypatch.setattr('sourceroi.live.engine.run_chat', missing)
    report = run_study(cfg, min_groundedness=None)
    assert not report['outperforms_all_qualified_baselines_observed']
    assert all(v is None for v in report['heldout_objective_scores'].values())
    assert report['evaluation_model_cost_usd'] is None


def test_group_leakage_rejected():
    tasks = [{'id': 'a', 'group_id': 'same-filing', 'split': 'development'},
             {'id': 'b', 'group_id': 'same-filing', 'split': 'heldout'}]
    with pytest.raises(ValueError, match='groups overlap'):
        split_tasks(tasks)


def test_auto_split_keeps_groups_together():
    tasks = [{'id': str(i), 'group_id': str(i//2)} for i in range(12)]
    dev, held = split_tasks(tasks)
    assert {t['group_id'] for t in dev}.isdisjoint({t['group_id'] for t in held})


def test_policy_runtime_depends_on_question_and_context_only(cfg):
    chunks = scan_sources(cfg)[1]
    cfg['settings']['retrieval_policy'] = {'name': 'task_aware', 'k': 4}
    lookup, decision = select_context('What is Aster revenue?', chunks, cfg)
    comparison, _ = select_context('Compare Aster revenue and cash.', chunks, cfg)
    assert len(lookup) == 1
    assert len(comparison) > 1
    assert decision['task_kind'] == 'lookup'
    assert task_kind('Combine income and expenses') == 'multi_evidence'


def test_redundant_text_removed_and_source_filters_enforced(cfg):
    chunks = scan_sources(cfg)[1]
    chunk = next(c for c in chunks if c['source_id'] == 'reports')
    duplicate = {**chunk, 'id': 'copy', 'document_id': 'copy'}
    cfg['settings']['retrieval_policy'] = {'name': 'coverage', 'k': 4, 'excluded_sources': ['commentary']}
    selected, _ = select_context('What is Aster revenue?', chunks+[duplicate], cfg)
    assert all(c['source_id'] != 'commentary' for c in selected)
    assert len({' '.join(c['text'].lower().split()) for c in selected}) == len(selected)


def sample_review():
    question, answer = 'What is revenue?', 'Revenue is 42. Profit is 99.'
    context = [{'id': 'report#1', 'text': 'Revenue is 42. Profit is 7.'}]
    key = evidence_key(question, answer, context)
    review = {'status': 'complete', 'reviewer': 'test reviewer', 'claims': [
        {'start': 0, 'end': 14, 'verdict': 'supported', 'evidence': [{'id': 'report#1', 'quote': 'Revenue is 42.'}]},
        {'start': 14, 'end': len(answer), 'verdict': 'contradicted'}]}
    return question, answer, context, key, review


def test_semantic_scoring_uses_review_not_citation_frequency():
    q, answer, context, key, review = sample_review()
    score = score_review(q, answer, context, ['report#1'], {key: review})
    assert score['groundedness'] == .5
    assert score['unsupported_claims'] == 1
    assert score_review(q, answer, context, ['report#1'], {})['groundedness'] is None


@pytest.mark.parametrize('mutation', ['quote', 'coverage', 'reviewer', 'overlap', 'citation'])
def test_invalid_semantic_adjudications_rejected(mutation):
    q, answer, context, key, review = sample_review()
    citations = ['report#1']
    if mutation == 'quote':
        review['claims'][0]['evidence'][0]['quote'] = 'Invented evidence'
    elif mutation == 'coverage':
        review['claims'].pop()
    elif mutation == 'reviewer':
        review['reviewer'] = ''
    elif mutation == 'overlap':
        review['claims'][1]['start'] = 0
    else:
        citations = []
    with pytest.raises(ValueError):
        score_review(q, answer, context, citations, {key: review})


def test_semantic_scores_cannot_be_reused_after_answer_or_evidence_changes():
    q, answer, context, key, review = sample_review()
    assert score_review(q, answer+' Extra.', context, ['report#1'], {key: review})['groundedness'] is None
    assert score_review(q, answer, [{'id': 'report#1', 'text': 'different'}], ['report#1'], {key: review})['groundedness'] is None


def test_unreviewed_grounding_blocks_qualification(cfg):
    report = run_study(cfg, min_groundedness=.9)
    assert not report['heldout_quality_qualified']['sourceroi']
    assert not report['outperforms_all_qualified_baselines_observed']
    assert report['review_items']


def test_partial_study_is_saved_and_never_recommended(cfg):
    from sourceroi.live import db
    cfg['settings']['max_estimated_model_cost_usd'] = .000001
    with pytest.raises(ValueError, match='ceiling'):
        run_study(cfg, min_groundedness=None)
    saved = db.get(cfg, db.list_runs(cfg)[0]['id'])
    assert saved['report']['status'] == 'incomplete'
    assert saved['report']['deployment'] == 'inconclusive'
    assert saved['report']['api_calls'] == 1


def test_study_exports_persisted_results_and_review_packet(cfg, tmp_path):
    report = run_study(cfg, min_groundedness=None)
    output = tmp_path/'export.json'
    export_study(report, output)
    assert json.loads(output.read_text())['run_id'] == report['run_id']
    assert output.with_suffix('.csv').exists()
    assert 'heldout' in output.with_suffix('.csv').read_text()
    assert 'Evidence: local_test_adapter' in output.with_suffix('.md').read_text()
    assert load_reviews(output.with_suffix('.review.json')) == {}


def test_api_study_and_exports(cfg):
    from sourceroi.live.api import create_app
    client = TestClient(create_app(cfg['_root']))
    assert client.post('/api/v2/studies', json={}).status_code == 400
    response = client.post('/api/v2/studies', json={'acknowledge_model_calls': True, 'min_groundedness': None})
    assert response.status_code == 200
    rid = response.json()['id']
    for format in ('json', 'csv', 'markdown', 'review'):
        exported = client.get(f'/api/v2/studies/{rid}/export?format={format}')
        assert exported.status_code == 200
        assert 'attachment' in exported.headers['content-disposition']
    assert client.get(f'/api/v2/studies/{rid}/export?format=invalid').status_code == 400


def test_study_call_cap_is_preflight(cfg):
    cfg['settings']['max_model_calls_per_run'] = 1
    with patch('sourceroi.live.study.evaluate_variant') as model:
        with pytest.raises(ValueError, match='above cap'):
            run_study(cfg)
        model.assert_not_called()


def test_cli_is_local_only_without_explicit_spend(cfg, tmp_path, capsys):
    from sourceroi.live.cli import main
    output = tmp_path/'cli-study.json'
    args = ['--project', cfg['_root'], 'study', '--output', str(output)]
    assert main(args) == 2
    capsys.readouterr()
    assert main(args+['--allow-model-calls']) == 0
    report = json.loads(output.read_text())
    assert report['status'] == 'completed'
    assert report['heldout_quality_qualified']['sourceroi'] is False  # No human review supplied.


def test_heldout_answers_do_not_change_frozen_policy(cfg):
    before = run_study(cfg, min_groundedness=None)
    path = Path(cfg['_root'])/'benchmark.jsonl'
    tasks = load_benchmark(cfg)
    for t in tasks:
        if t['split'] == 'heldout':
            t['expected'] = 'different held-out answer'
    path.write_text('\n'.join(json.dumps(t) for t in tasks))
    after = run_study(cfg, min_groundedness=None)
    assert before['frozen_policy_sha256'] == after['frozen_policy_sha256']


def test_grounding_scores_flow_through_actual_evaluation(cfg):
    tasks = load_benchmark(cfg)[:1]
    chunks = scan_sources(cfg)[1]
    cfg['_review_items'] = []
    first = evaluate_variant(cfg, tasks, chunks, [])
    item = cfg['_review_items'][0]
    row = first['tasks'][0]
    cited = next(c for c in chunks if c['id'] in row['citations'])
    cfg['_grounding_reviews'] = {item['key']: {'status': 'complete', 'reviewer': 'test reviewer', 'claims': [
        {'start': 0, 'end': len(row['actual']), 'verdict': 'supported',
         'evidence': [{'id': cited['id'], 'quote': cited['text']}]}]}}
    reviewed = evaluate_variant(cfg, tasks, chunks, [])
    assert reviewed['metrics']['groundedness'] == 1
    assert reviewed['metrics']['unsupported_claims'] == 0


def test_bootstrap_repeats_are_not_independent_observations(cfg):
    from sourceroi.live.uncertainty import objective_interval
    report = run_study(cfg, min_groundedness=None)
    entries = {e['name']: e for e in report['experiments'] if e['partition'] == 'heldout'}
    heldout = [t for t in load_benchmark(cfg) if t['split'] == 'heldout']
    once = objective_interval(entries['original'], entries['sourceroi'], heldout, 'token_budget')
    double = deepcopy(entries)
    for entry in double.values():
        entry['runs'] *= 2
    assert objective_interval(double['original'], double['sourceroi'], heldout, 'token_budget') == once
    for t in heldout:
        t['group_id'] = 'one-group'
    assert objective_interval(entries['original'], entries['sourceroi'], heldout, 'token_budget') is None


def test_unknown_source_prices_do_not_become_free_cost_estimates(cfg):
    from sourceroi.live.study import policies
    cfg['sources'][0]['per_call_price_usd'] = None
    assert not any(family == 'cheapest' for family, _ in policies(cfg))
    assert all(p.get('cost_weight', 0) == 0 for family, p in policies(cfg) if family == 'coverage')
