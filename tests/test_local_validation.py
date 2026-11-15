"""Local-only safety and measurement tests; no real model or download required."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark, scan_sources
from sourceroi.live.provider import ProviderError, run_chat
from sourceroi.live.recommendation import build_recommendation, INCONCLUSIVE
from sourceroi.live.study import run_study
from tools.local_llm import install
from tools.validate_study import create_project, simulated_model

ROOT = Path(__file__).resolve().parents[1]


def test_local_only_does_not_read_or_send_commercial_credentials(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'must-not-be-used')
    monkeypatch.setattr('sourceroi.live.provider._key', lambda *args: pytest.fail('Commercial credential lookup attempted'))
    requests = []
    def post(url, body, timeout, api_key=None):
        assert api_key is None
        requests.append((url, body))
        if url.endswith('/tokenize'):
            return {'tokens': [10, 20, 30]}
        return {'model': 'real-local-model-id', 'usage': {'prompt_tokens': 10, 'completion_tokens': 2},
                'choices': [{'finish_reason': 'stop', 'message': {'content': '{"answer":"42","citations":["1"]}'}}]}
    monkeypatch.setattr('sourceroi.live.provider._post', post)
    cfg = {'model': {'name': 'alias', 'base_url': 'http://127.0.0.1:8788/v1', 'local_only': True,
                     'runtime': 'llama_cpp', 'context_tokenizer': 'llama_cpp', 'compact_source_ids': True,
                     'response_format': 'json_object'}}
    context = [{'id': 'source::full-id#chunk0', 'title': 'Original article title', 'text': '42'}]
    result = run_chat('Question', context, cfg)
    assert result['context_tokens'] == 3
    assert result['input_tokens'] == 10 and result['output_tokens'] == 2
    assert result['model_cost_usd'] is None
    assert result['citations'] == ['source::full-id#chunk0']
    assert result['invalid_citations'] == []
    assert requests[1][1]['cache_prompt'] is False
    assert 'source::full-id' not in requests[1][1]['messages'][1]['content']
    assert 'Original article title' in requests[1][1]['messages'][1]['content']


def test_local_only_refuses_remote_before_network(monkeypatch):
    monkeypatch.setattr('sourceroi.live.provider._post', lambda *a, **k: pytest.fail('Network attempted'))
    with pytest.raises(ProviderError, match='non-loopback'):
        run_chat('q', [], {'model': {'name': 'model', 'base_url': 'https://example.com/v1', 'local_only': True}})


def test_model_download_requires_explicit_permission(tmp_path, monkeypatch):
    monkeypatch.setattr('tools.local_llm.download', lambda *args: pytest.fail('Unauthorized download attempted'))
    with pytest.raises(ValueError, match='permission'):
        install(tmp_path/'model', download_approved=False)
    assert not (tmp_path/'model').exists()


def test_expanded_public_benchmark_is_grouped_and_excludes_exposed_articles():
    root = ROOT/'workspace/local-llm-96'
    tasks = load_benchmark(read_config(root))
    assert len(tasks) == 96
    for split in ('development', 'heldout'):
        assert sum(t['split'] == split for t in tasks) == 48
    dev = {t['group_id'] for t in tasks if t['split'] == 'development'}
    held = {t['group_id'] for t in tasks if t['split'] == 'heldout'}
    assert dev.isdisjoint(held)
    current = json.loads((root/'provenance.json').read_text())
    old = json.loads((ROOT/'workspace/public-validation/provenance.json').read_text())
    title = lambda item: item['title'].lower().replace('_', ' ')
    assert {title(d) for d in current['documents']}.isdisjoint({title(d) for d in old['documents']})
    assert current['excluded_prior_provenance_sha256']


def test_public_original_article_titles_are_preserved():
    cfg = read_config(ROOT/'workspace/local-llm-96')
    docs, chunks = scan_sources(cfg)
    provenance = json.loads((Path(cfg['_root'])/'provenance.json').read_text())
    titles = {doc['id']: doc['title'] for doc in provenance['documents']}
    assert all(doc['title'] == titles[doc['id']] for doc in docs)
    assert all(chunk['title'] == titles[chunk['document_id']] for chunk in chunks)


def test_recommendation_requires_benefit_over_simple_baseline(tmp_path, monkeypatch):
    create_project(tmp_path)
    monkeypatch.setattr('sourceroi.live.engine.run_chat', simulated_model)
    cfg = read_config(tmp_path)
    report = run_study(cfg, min_groundedness=None)
    report['measurement_kind'] = 'local_generation'
    report['review_status'] = 'published_dataset_annotations'
    report['heldout_quality_qualified']['sourceroi'] = True
    for entry in report['experiments']:
        if entry['partition'] == 'heldout' and entry['name'] == 'sourceroi':
            entry['runs'][0]['metrics']['groundedness'] = 1
            for row in entry['runs'][0]['tasks']:
                row['usage_source'] = 'provider_reported'
    report['benefits_over_simple_baselines'] = {'top_k': False, 'threshold': False}
    heldout = [{'id': str(i), 'group_id': str(i)} for i in range(12)]
    result = build_recommendation(report, cfg, heldout)
    assert result['deployment_verdict'] == INCONCLUSIVE
    assert result['benefits_over_simple_baselines']['threshold'] is False


def test_infeasible_baseline_fallback_prioritizes_quality_not_cheapest_failure(tmp_path, monkeypatch):
    create_project(tmp_path)
    cfg = read_config(tmp_path)
    def model(question, context, configuration):
        result = simulated_model(question, context, configuration)
        policy = configuration['settings']['retrieval_policy']
        if policy['name'] == 'context_budget':
            if policy['chars'] == 128 or question == 'What is Aster revenue?':
                result['answer'] = 'wrong'
        return result
    monkeypatch.setattr('sourceroi.live.engine.run_chat', model)
    report = run_study(cfg, quality_floor=1, min_groundedness=None)
    assert report['development_selection_status']['context_budget'] == 'no_qualifying_development_configuration'
    assert report['frozen_policies']['context_budget']['chars'] > 128
