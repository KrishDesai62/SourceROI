"""Safety and evidence tests for development search and final held-out validation."""
import json
import math
from unittest.mock import patch

import pytest

from sourceroi.live.config import read_config
from sourceroi.live.engine import _objective_score, evaluate_variant
from sourceroi.live.ingest import load_benchmark, scan_sources
from sourceroi.live.validation import optimize, split_tasks
from tools.validate_local import local_adapter, make_project


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    make_project(tmp_path)
    monkeypatch.setattr('sourceroi.live.engine.run_chat', local_adapter)
    return read_config(tmp_path)


def test_four_way_validation_and_sealed_holdout(cfg, monkeypatch):
    from sourceroi.live import engine
    original = engine.evaluate_variant
    seen_heldout = False
    def inspect(config, tasks, *args, **kwargs):
        nonlocal seen_heldout
        held = tasks[0]['split'] == 'heldout'
        if seen_heldout:
            assert held, 'Search resumed after held-out feedback'
        seen_heldout |= held
        return original(config, tasks, *args, **kwargs)
    monkeypatch.setattr(engine, 'evaluate_variant', inspect)
    report = optimize(cfg, quality_floor=1)
    assert report['recommended']['excluded_sources'] == ['noise']
    assert report['heldout_improvement_over_baseline_and_heuristic']
    assert report['deployment'] == 'requires_further_testing'
    assert report['measurement_kind'] == 'local_test_adapter'
    assert {e['name'] for e in report['experiments'] if e['partition'] == 'heldout'} == {
        'original', 'sourceroi', 'top_k', 'fixed_source_drop'}
    assert report['recommended']['groundedness'] is None
    assert report['api_calls'] == 20
    json.dumps(report, allow_nan=False)


def test_heldout_failure_rejects_without_reselection(cfg, monkeypatch):
    def model(question, context, config):
        result = local_adapter(question, context, config)
        if question == 'Held-out revenue question' and not any(c['source_id'] == 'noise' for c in context):
            result['answer'] = 'wrong'
        return result
    path = __import__('pathlib').Path(cfg['_root'])/'benchmark.jsonl'
    tasks = load_benchmark(cfg)
    for t in tasks:
        if t['split'] == 'heldout':
            t['question'] = 'Held-out revenue question'
    path.write_text('\n'.join(json.dumps(t) for t in tasks))
    monkeypatch.setattr('sourceroi.live.engine.run_chat', model)
    report = optimize(cfg, quality_floor=1)
    assert report['recommended']['excluded_sources'] == ['noise']
    assert report['deployment'] == 'rejected'
    assert report['heldout_comparisons'][0]['lost_tasks']


def test_unknown_cost_cannot_win(cfg, monkeypatch):
    def model(*args):
        r = local_adapter(*args)
        r['model_cost_usd'] = None
        return r
    cfg['settings'].pop('max_estimated_model_cost_usd')
    monkeypatch.setattr('sourceroi.live.engine.run_chat', model)
    report = optimize(cfg)
    assert report['recommended']['excluded_sources'] == []
    assert report['observed_model_cost_usd'] is None
    assert math.isinf(_objective_score({'passed': 1}, 'cost_per_success'))


def test_call_cap_rejects_before_provider(cfg, monkeypatch):
    cfg['settings']['max_model_calls_per_run'] = 1
    with patch('sourceroi.live.engine.run_chat') as model:
        with pytest.raises(ValueError, match='above cap'):
            optimize(cfg)
        model.assert_not_called()


def test_cost_ceiling_stops_and_persists_partial(cfg):
    from sourceroi.live import db
    cfg['settings']['max_estimated_model_cost_usd'] = .000001
    with pytest.raises(ValueError, match='ceiling exceeded'):
        optimize(cfg)
    row = db.get(cfg, db.list_runs(cfg)[0]['id'])
    assert row['status'] == 'failed'
    assert row['report']['api_calls'] == 1
    assert row['report']['deployment'] == 'inconclusive'


def test_deterministic_split_independent_of_answers():
    tasks = [{'id': str(i), 'expected': 'a'} for i in range(10)]
    first = split_tasks(tasks)
    second = split_tasks([{**t, 'expected': 'different'} for t in reversed(tasks)])
    assert [[t['id'] for t in group] for group in first] == [[t['id'] for t in group] for group in second]
    with pytest.raises(ValueError, match='Every task'):
        split_tasks([{'id': 'a', 'split': 'heldout'}, {'id': 'b'}])


@pytest.mark.parametrize('kwargs', [{'quality_floor': float('nan')}, {'max_tasks': 0},
                                   {'repeats': 0}, {'max_candidates': 0}, {'objective': 'bogus'}])
def test_invalid_controls_make_no_calls(cfg, kwargs):
    with patch('sourceroi.live.engine.run_chat') as model:
        with pytest.raises(ValueError):
            optimize(cfg, **kwargs)
        model.assert_not_called()


def test_passage_filter_and_context_budget(cfg):
    tasks = load_benchmark(cfg)[:1]
    _, chunks = scan_sources(cfg)
    truth_id = next(c['id'] for c in chunks if c['source_id'] == 'truth')
    variant = evaluate_variant(cfg, tasks, chunks, [], exclude_passages=[truth_id])
    assert variant['metrics']['passed'] == 0
    assert truth_id not in variant['tasks'][0]['retrieved_chunk_ids']
    cfg['settings']['max_context_chars'] = 1
    variant = evaluate_variant(cfg, tasks, chunks, [])
    assert variant['metrics']['passed'] == 0
    assert variant['metrics']['total_tokens'] == 85


def test_api_does_not_charge_on_get_and_requires_ack(cfg):
    from fastapi.testclient import TestClient
    from sourceroi.live.api import create_app
    client = TestClient(create_app(cfg['_root']))
    with patch('sourceroi.live.engine.run_chat') as model:
        assert client.get('/api/v2/optimize').status_code == 200
        assert client.post('/api/v2/optimize', json={}).status_code == 400
        assert client.post('/api/v2/optimize', json={'quality_floor': 2}).status_code == 422
        model.assert_not_called()


def test_aggregate_quality_floor_cannot_hide_task_regression(cfg, monkeypatch):
    from pathlib import Path
    tasks = load_benchmark(cfg)
    tasks[0]['question'] = 'Special revenue?'
    (Path(cfg['_root'])/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks))
    def model(question, context, config):
        result = local_adapter(question, context, config)
        if question == 'Special revenue?' and not any(c['source_id'] == 'noise' for c in context):
            result['answer'] = 'wrong'
        return result
    monkeypatch.setattr('sourceroi.live.engine.run_chat', model)
    report = optimize(cfg, quality_floor=.5)
    assert report['recommended']['excluded_sources'] == []


def test_api_optimization_persists_result(cfg):
    from fastapi.testclient import TestClient
    from sourceroi.live.api import create_app
    client = TestClient(create_app(cfg['_root']))
    response = client.post('/api/v2/optimize', json={'acknowledge_model_calls': True})
    assert response.status_code == 200
    result = response.json()
    saved = client.get('/api/v2/runs/'+result['id']).json()
    assert saved['status'] == 'completed'
    assert saved['report']['split']['heldout_ids']


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), True])
def test_invalid_pricing_rejected(cfg, value):
    from pathlib import Path
    path = Path(cfg['_root'])/'project.json'
    data = json.loads(path.read_text())
    data['model']['input_price_per_million_usd'] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='input_price'):
        read_config(cfg['_root'])


def test_cli_requires_ack_and_persists_validation(cfg, capsys):
    from sourceroi.live.cli import main
    from sourceroi.live import db
    prefix = ['--project', cfg['_root'], 'optimize']
    with patch('sourceroi.live.engine.run_chat') as model:
        assert main(prefix) == 2
        model.assert_not_called()
    capsys.readouterr()
    assert main(prefix+['--allow-model-calls', '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['recommended']['deployment'] == 'requires_further_testing'
    assert db.list_runs(cfg)[0]['status'] == 'completed'
