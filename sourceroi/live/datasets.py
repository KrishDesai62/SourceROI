"""Small, attributed public QA workspaces with published answers and evidence.

Documents retain original text. Selection and splitting never use model results.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .parser_boundary import json_data as read_json_data
import tempfile
from urllib.parse import quote

import httpx

LICENSE = 'https://creativecommons.org/licenses/by-sa/4.0/'
SOURCES = {
    'squad': {'url': 'https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json',
              'homepage': 'https://rajpurkar.github.io/SQuAD-explorer/',
              'attribution': 'SQuAD 2.0, Rajpurkar, Jia and Liang (2018); Wikipedia contributors'},
    'hotpot': {'url': 'https://datasets-server.huggingface.co/rows?dataset=hotpotqa%2Fhotpot_qa&config=distractor&split=validation&offset=0&length=100',
               'homepage': 'https://hotpotqa.github.io/',
               'attribution': 'HotpotQA, Yang, Qi, Zhang et al. (2018); Wikipedia contributors'},
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def fetch_public(cache: str | Path):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, spec in SOURCES.items():
        destination = cache/(name+'.json')
        if not destination.exists():
            temporary = cache/(name+'.partial')
            try:
                with httpx.stream('GET', spec['url'], timeout=60, follow_redirects=True) as response:
                    response.raise_for_status()
                    if response.url.scheme != 'https':
                        raise ValueError('Dataset download redirected away from HTTPS')
                    size = 0
                    with temporary.open('wb') as output:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 64*1024*1024:
                                raise ValueError('Public download exceeds 64MB limit')
                            output.write(chunk)
                read_json_data(temporary)
                temporary.replace(destination)
            except (httpx.HTTPError, ValueError) as exc:
                temporary.unlink(missing_ok=True)
                raise ValueError(f'{name} public download unavailable ({type(exc).__name__}); use --squad/--hotpot local published JSON files') from None
        paths[name] = destination
    return paths


def squad_records(path):
    data = read_json_data(path)
    for article in data['data']:
        title = article['title']
        for paragraph in article['paragraphs']:
            text = paragraph['context']
            for qa in paragraph['qas']:
                # Keep published answerable tasks. No generated replacement answers.
                answers = qa.get('answers', [])
                if not answers or qa.get('is_impossible'):
                    continue
                evidence = []
                for answer in answers:
                    start, value = answer['answer_start'], answer['text']
                    if text[start:start+len(value)] != value:
                        raise ValueError('SQuAD answer span does not match its source text')
                    evidence.append({'title': title, 'start': start, 'end': start+len(value), 'quote': value})
                yield {'id': 'squad-'+qa['id'], 'question': qa['question'],
                       'answers': list(dict.fromkeys(a['text'] for a in answers)),
                       'documents': [(title, text)], 'evidence': evidence, 'dataset': 'squad', 'reasoning': 'single_document'}


def hotpot_records(path):
    data = read_json_data(path)
    # Official raw JSON and the official HF dataset server's row format are supported.
    rows = [row['row'] for row in data['rows']] if isinstance(data, dict) and 'rows' in data else data
    for row in rows:
        context = row['context']
        pairs = list(zip(context['title'], context['sentences'])) if isinstance(context, dict) else context
        documents = [(title, ''.join(sentences)) for title, sentences in pairs]
        facts = row['supporting_facts']
        facts = list(zip(facts['title'], facts['sent_id'])) if isinstance(facts, dict) else facts
        by_title = dict(pairs)
        evidence = []
        for title, ix in facts:
            if title not in by_title or type(ix) is not int or not 0 <= ix < len(by_title[title]):
                raise ValueError('Hotpot supporting fact references missing evidence')
            sentences = by_title[title]
            start = len(''.join(sentences[:ix]))
            evidence.append({'title': title, 'sentence_id': ix, 'start': start,
                             'end': start+len(sentences[ix]), 'quote': sentences[ix]})
        yield {'id': 'hotpot-'+str(row.get('_id') or row.get('id')), 'question': row['question'],
               'answers': [row['answer']], 'documents': documents, 'evidence': evidence,
               'dataset': 'hotpot', 'reasoning': row.get('type', 'multi_document')}


def build_public_workspace(squad, hotpot, output, *, per_dataset=8, tasks_per_article=1, exclude_provenance=None):
    if type(per_dataset) is not int or per_dataset < 2 or per_dataset > 100 or per_dataset % 2:
        raise ValueError('per_dataset must be an even integer 2..100')
    if type(tasks_per_article) is not int or not 1 <= tasks_per_article <= 4:
        raise ValueError('tasks_per_article must be 1..4')
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Public benchmark output must be empty; existing benchmarks are never overwritten')
    # Select disjoint article families, including distractors, before consulting answers.
    # One task per family prevents near-duplicate same-article questions crossing splits.
    records = []
    titles_used, text_hashes_used = set(), set()
    hash_owners = {}
    excluded_prior_sha256 = None
    if exclude_provenance is not None:
        prior_paths = exclude_provenance if isinstance(exclude_provenance, (list,tuple)) else [exclude_provenance]
        prior_hashes = []
        from .config import secure_path
        for value in prior_paths:
            prior_path = Path(value)
            prior = read_json_data(prior_path)
            prior_hashes.append(hashlib.sha256(prior_path.read_bytes()).hexdigest())
            for doc in prior['documents']:
                titles_used.add(' '.join(doc['title'].lower().replace('_',' ').split()))
                from .ingest import _extract
                prior_text=_extract(secure_path(prior_path.parent,doc['path']))
                text_hashes_used.add(digest(' '.join(prior_text.lower().split())))
        excluded_prior_sha256 = prior_hashes[0] if len(prior_hashes)==1 else prior_hashes
    for dataset_name, iterator in [('squad', squad_records(squad)), ('hotpot', hotpot_records(hotpot))]:
        selected, admitted_groups = [], {}
        for record in iterator:
            titles = {' '.join(t.lower().replace('_', ' ').split()) for t, _ in record['documents']}
            hashes = {digest(' '.join(text.lower().split())) for _, text in record['documents']}
            family = ('squad-article-'+digest(record['documents'][0][0])) if dataset_name == 'squad' else record['id']
            previous = admitted_groups.get(family, 0)
            if previous:
                if dataset_name != 'squad' or previous >= tasks_per_article:
                    continue
                if any(h in hash_owners and hash_owners[h] != family for h in hashes):
                    continue
            elif titles & titles_used or hashes & text_hashes_used:
                continue
            record['group_id'] = family if tasks_per_article > 1 else record['id']
            selected.append(record)
            admitted_groups[family] = previous+1
            titles_used |= titles
            text_hashes_used |= hashes
            hash_owners.update({h: family for h in hashes})
            if len(selected) == per_dataset:
                break
        if len(selected) != per_dataset:
            raise ValueError('Not enough disjoint public article groups; provide more published records or increase tasks_per_article for SQuAD')
        groups = sorted({r['group_id'] for r in selected}, key=digest)
        dev_groups = set(groups[:len(groups)//2])
        if not dev_groups or len(dev_groups) == len(groups):
            raise ValueError('Need at least two document groups per dataset for an independent split')
        for record in selected:
            record['split'] = 'development' if record['group_id'] in dev_groups else 'heldout'
        records.extend(sorted(selected, key=lambda r: digest(r['id'])))
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sourceroi-public-', dir=parent) as temp:
        root = Path(temp)/'workspace'
        root.mkdir()
        document_manifest, tasks = [], []
        for record in records:
            references = {}
            for title, text in record['documents']:
                name = digest(title+'\n'+text)+'.txt'
                relative = f"sources/{record['dataset']}/{name}"
                file = root/relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(text, encoding='utf-8')
                did = record['dataset']+'::'+name
                references[title] = did
                document_manifest.append({'id': did, 'path': relative, 'title': title,
                    'sha256': digest(text), 'source_url': 'https://en.wikipedia.org/wiki/'+quote(title.replace(' ', '_')),
                    'dataset': record['dataset'], 'license': LICENSE, 'modified': False})
            evidence = [{**e, 'document_id': references[e['title']]} for e in record['evidence']]
            tasks.append({'id': record['id'], 'question': record['question'], 'expected': record['answers'][0],
                          'accepted_answers': record['answers'], 'scoring': 'qa_exact', 'split': record['split'],
                          'group_id': record['group_id'], 'category': record['dataset']+'/'+record['reasoning'],
                          'review_status': 'published_dataset_annotations', 'reviewer': SOURCES[record['dataset']]['attribution'],
                          'evidence': evidence, 'dataset': record['dataset']})
        (root/'benchmark.jsonl').write_text(''.join(json.dumps(t, ensure_ascii=False)+'\n' for t in tasks))
        provenance = {'version': 1, 'kind': 'published_external_data', 'license': LICENSE,
            'datasets': {name: {**SOURCES[name], 'local_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                                'selection': f'first disjoint article groups; at most {tasks_per_article} SQuAD questions per article; split by SHA256 group ID, independent of predictions'}
                         for name, path in [('squad', squad), ('hotpot', hotpot)]},
            'documents': list({d['id']: d for d in document_manifest}.values()),
            'excluded_prior_provenance_sha256': excluded_prior_sha256,
            'split_groups': {split: sorted({r['group_id'] for r in records if r['split'] == split}) for split in ('development', 'heldout')},
            'limitations': ['Source URLs identify article attribution, not current live article content.',
                'Historic dataset snapshots may be outdated; no factual text was edited or fabricated.',
                'Published annotations are independent of the evaluated model but are not a new customer-specific human audit.',
                'Passage near-duplicates beyond matching titles and normalized exact text are not automatically detected.',
                'Potential pretraining contamination is unknown. Small public subsets cannot prove production generalization.']}
        (root/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
        (root/'ATTRIBUTION.md').write_text('# Public evaluation data\n\n'+ '\n\n'.join(
            f"{name}: {spec['attribution']}. {spec['homepage']} Dataset license: {LICENSE}" for name, spec in SOURCES.items())+
            '\n\nOriginal text retained. Filenames and document grouping adapted for SourceROI; original answer/evidence annotations retained.\n')
        cfg = {'id': 'public-qa', 'name': 'Public QA validation', 'runner': 'rag_chat',
               'benchmark': 'benchmark.jsonl', 'data_provenance': 'provenance.json',
               'measurement_kind': 'unverified_endpoint',
               'model': {'name': 'CONFIGURE_LOCAL_MODEL', 'base_url': 'http://localhost:11434/v1',
                         'temperature': 0, 'max_output_tokens': 200, 'timeout_seconds': 90,
                         'input_price_per_million_usd': None, 'output_price_per_million_usd': None},
               'settings': {'max_chunks': 5, 'chunk_chars': 1100, 'overlap_chars': 150,
                            'max_tasks_per_run': 50, 'max_model_calls_per_run': 1000 if len(tasks) <= 50 else 5000,
                            'study_source_candidates': 4},
               'sources': [{'id': name, 'name': name, 'path': 'sources/'+name, 'per_call_price_usd': 0}
                           for name in SOURCES]}
        (root/'project.json').write_text(json.dumps(cfg, indent=2)+'\n')
        if output.exists():
            output.rmdir()  # Only the verified empty destination, never user data.
        root.replace(output)
    return {'workspace': str(output), 'tasks': len(tasks), 'documents': len({d['id'] for d in document_manifest}),
            'datasets': list(SOURCES), 'provenance_sha256': hashlib.sha256((output/'provenance.json').read_bytes()).hexdigest()}


def verify_public_snapshot(cfg, documents):
    from .config import secure_path
    path = secure_path(Path(cfg['_root']), cfg.get('data_provenance', 'provenance.json'))
    provenance = read_json_data(path)
    if provenance.get('kind') != 'published_external_data':
        raise ValueError('Public audit requires published external-data provenance')
    expected = {d['id']: d['sha256'] for d in provenance['documents']}
    actual = {d['id']: d['fingerprint'] for d in documents}
    if expected != actual:
        raise ValueError('Public source snapshot changed; register a new benchmark version instead of altering the frozen corpus')
    return provenance
