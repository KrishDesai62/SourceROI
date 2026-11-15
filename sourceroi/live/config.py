"""Config loading, validation and safe, bounded workspace operations."""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SUPPORTED_EXTENSIONS = {'.md', '.txt', '.pdf', '.csv', '.json', '.jsonl', '.html', '.htm', '.docx'}
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[2] / 'workspace'
IDENTIFIER = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')


def secure_path(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError('Paths must be nonempty and relative to the workspace')
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes workspace: {relative}')
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f'Path not found: {relative}')
    return resolved


def read_config(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or DEFAULT_WORKSPACE).expanduser().resolve()
    cfg = json.loads((root / 'project.json').read_text(encoding='utf-8'))
    sources = cfg.get('sources') or []
    ids = [s['id'] for s in sources]
    if not all(IDENTIFIER.fullmatch(i) for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Sources must have distinct simple IDs (letters/numbers/_/-)')
    for s in sources:
        path = secure_path(root, s['path'])
        if not path.is_dir():
            raise ValueError(f"Source {s['id']} must point to a folder")
        reliability = s.get('reliability', .5)
        if type(reliability) not in (int,float) or not math.isfinite(reliability) or not 0 <= reliability <= 1:
            raise ValueError('Source reliability must be explicitly finite in [0,1]')
        fee = s.get('per_call_price_usd')
        if fee is not None and (type(fee) not in (int, float) or not math.isfinite(fee) or fee < 0):
            raise ValueError('per_call_price_usd must be nonnegative or null')
    benchmark = secure_path(root, cfg.get('benchmark', 'benchmark.jsonl'))
    if not benchmark.is_file():
        raise ValueError('benchmark must be a file')
    model = cfg.get('model') or {}
    runner = cfg.get('runner', 'rag_chat')
    if runner not in ('rag_chat', 'http_agent'):
        raise ValueError('runner must be rag_chat or http_agent')
    url = model.get('base_url', 'https://api.openai.com/v1') if runner == 'rag_chat' else cfg.get('agent', {}).get('url', '')
    if not isinstance(url, str) or not url:
        raise ValueError('Model/agent URL is required')
    parsed = urlparse(url)
    local = parsed.hostname in ('localhost', '127.0.0.1', '::1')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and local):
        raise ValueError('Remote endpoints must use HTTPS (HTTP only permitted on localhost)')
    if parsed.query or parsed.fragment:
        raise ValueError('Endpoint URLs must not contain query credentials or fragments; use credential environment variables')
    if parsed.username or parsed.password:
        raise ValueError('Credentials must not appear inside endpoint URLs')
    if runner == 'rag_chat' and (not isinstance(model.get('name'), str) or not model['name'].strip()):
        raise ValueError('model.name is required')
    if model.get('local_only') is not None and type(model['local_only']) is not bool:
        raise ValueError('model.local_only must be boolean')
    if model.get('local_only') and not local:
        raise ValueError('Local-only model must use a loopback endpoint')
    if model.get('context_tokenizer') not in (None, 'llama_cpp'):
        raise ValueError('Unsupported context tokenizer')
    if model.get('context_tokenizer') and not local:
        raise ValueError('Context tokenizer must use a loopback endpoint')
    if model.get('response_format') not in (None, 'json_object'):
        raise ValueError('Unsupported response format')
    cost_ceiling = cfg.get('settings',{}).get('max_estimated_model_cost_usd')
    if cost_ceiling is not None and (type(cost_ceiling) not in (int,float) or not math.isfinite(cost_ceiling) or cost_ceiling <= 0):
        raise ValueError('max_estimated_model_cost_usd must be a positive number or null')
    for key in ('input_price_per_million_usd', 'output_price_per_million_usd'):
        x = model.get(key)
        if x is not None and (type(x) not in (int, float) or not math.isfinite(x) or x < 0):
            raise ValueError(f'{key} must be nonnegative or null')
    settings = cfg.get('settings', {})
    if type(settings.get('table_evidence',False)) is not bool:raise ValueError('table_evidence must be boolean')
    if settings.get('chunk_strategy', 'fixed') not in ('fixed', 'sentences'):
        raise ValueError('chunk_strategy must be fixed or sentences')
    if settings.get('answering_mode', 'model') not in ('model','source_calculation'):
        raise ValueError('answering_mode must be model or source_calculation')
    reviewers=settings.get('calculation_reviewers',[])
    if not isinstance(reviewers,list) or any(not isinstance(v,str) or not v.strip() for v in reviewers):raise ValueError('calculation_reviewers must list operator-authorized reviewer identities')
    if settings.get('answering_mode')=='source_calculation' and (runner!='rag_chat' or settings.get('chunk_strategy')!='sentences'):
        raise ValueError('Source calculation requires the built-in sentence index')
    for key, low, high in [('max_run_seconds', 1, 86400), ('study_source_candidates', 0, 64), ('max_tasks_per_run', 1, 200), ('max_model_calls_per_run', 1, 10000),
                           ('max_context_chars', 1, 1000000), ('max_chunks', 1, 20), ('chunk_chars', 250, 6000), ('overlap_chars', 0, 2000), ('max_documents_per_study', 1, 20)]:
        value = settings.get(key)
        if value is not None and (type(value) is not int or not low <= value <= high):
            raise ValueError(f'{key} must be integer {low}..{high}')
    agent = cfg.get('agent', {})
    if agent.get('protocol_version', 1) not in (1, 2):
        raise ValueError('Agent protocol_version must be 1 or 2')
    from .adapter import CONTROL_NAMES, validate_controls
    caps = agent.get('capabilities', [])
    if not isinstance(caps, list) or not all(isinstance(c, str) and c in CONTROL_NAMES for c in caps):
        raise ValueError('Agent capabilities contain unsupported controls')
    if settings.get('agent_retrieval_controls') is not None:
        validate_controls(settings['agent_retrieval_controls'])
    for section in (model, agent):
        if any(section.get(k) for k in ('api_key','password','authorization','access_token')):
            raise ValueError('Credentials must be environment variables, not literal config values')
        timeout = section.get('timeout_seconds', 90)
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 600:
            raise ValueError('timeout_seconds must be finite in (0,600]')
    if 'max_output_tokens' in model and (type(model['max_output_tokens']) is not int or not 1 <= model['max_output_tokens'] <= 100000):
        raise ValueError('max_output_tokens must be integer 1..100000')
    if cfg.get('measurement_kind', 'unverified_endpoint') not in ('local_test_adapter', 'external_provider', 'local_generation', 'unverified_endpoint'):
        raise ValueError('Invalid measurement_kind')
    from .routing import validate as validate_routing
    validate_routing(settings.get('retrieval_contract'),set(ids))
    if settings.get('retrieval_contract') is not None and cfg.get('runner','rag_chat')!='rag_chat':
        raise ValueError('Built-in retrieval_contract requires rag_chat; external adapters own their routing')
    if settings.get('retrieval_policy') is not None:
        from .policies import validate_policy
        validate_policy(settings['retrieval_policy'])
    cfg['_root'] = str(root)
    cfg['_config_hash'] = hashlib.sha256(json.dumps({k: v for k, v in cfg.items() if not k.startswith('_')}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    cfg.setdefault('id', root.name)
    cfg.setdefault('name', root.name)
    cfg.setdefault('settings', {})
    return cfg


def public_config(cfg: dict[str, Any]) -> dict[str, Any]:
    model = cfg.get('model', {})
    runner = cfg.get('runner', 'rag_chat')
    secret_env = (model if runner == 'rag_chat' else cfg.get('agent', {})).get('api_key_env', '')
    url = model.get('base_url', '') if runner == 'rag_chat' else cfg.get('agent', {}).get('url', '')
    hostname = urlparse(url).hostname or ''
    return {
        'id': cfg['id'], 'name': cfg['name'], 'runner': runner,
        'model_name': model.get('name') if runner == 'rag_chat' else 'External agent',
        'endpoint_host': hostname,
        'credential_ready': bool(os.environ.get(secret_env)) or hostname in ('localhost', '127.0.0.1', '::1'),
        'sources': [{'id': s['id'], 'name': s.get('name', s['id']),
                     'per_call_price_usd': s.get('per_call_price_usd')} for s in cfg['sources']],
        'model_pricing_configured': model.get('input_price_per_million_usd') is not None
             and model.get('output_price_per_million_usd') is not None,
        'data_root': cfg['_root'],
    }
