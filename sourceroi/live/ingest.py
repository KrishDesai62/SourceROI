"""Extract real documents from the user's own folders. No synthetic corpus or hardcoded facts."""
from __future__ import annotations
import csv
import hashlib
import html
import io
import json
import re
from pathlib import Path
from typing import Any
from .config import SUPPORTED_EXTENSIONS, secure_path

_WORKER_ACTIVE = False

MAX_FILES = 2500
MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_EXTRACTED_CHARS = 400_000
MAX_TOTAL_TEXT_CHARS = 12_000_000


def _extract_in_process(path: Path, *, preserve_csv=False) -> str:
    if not _WORKER_ACTIVE:raise ValueError('Raw parser may execute only inside the isolated worker')
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Document must be a regular file at most 12MB')
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError('Unsupported document extension')
    if ext == '.pdf':
        with path.open('rb') as stream:
            if stream.read(5) != b'%PDF-': raise ValueError('PDF signature missing')
    if ext == '.docx':
        import zipfile
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 48 * 1024 * 1024:
                    raise ValueError('DOCX inflated resource limit exceeded')
                from pathlib import PurePosixPath
                import stat
                if any(PurePosixPath(e.filename).is_absolute() or '..' in PurePosixPath(e.filename).parts or '\\' in e.filename or stat.S_IFMT(e.external_attr>>16)==stat.S_IFLNK for e in entries):raise ValueError('Unsafe DOCX archive path/member')
                if '[Content_Types].xml' not in archive.namelist() or 'word/document.xml' not in archive.namelist():
                    raise ValueError('DOCX structure missing')
        except zipfile.BadZipFile as exc:
            raise ValueError('Invalid DOCX archive') from exc
    if ext == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError('PDF ingestion requires pypdf (pip install -e .)') from exc
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are unsupported')
        if len(reader.pages)>250:raise ValueError('PDF exceeds 250 page limit; no partial document accepted')
        # Extract text rather than OCR; image-only PDFs need OCR before import.
        parts = []
        for i, page in enumerate(reader.pages):
            parts.append(f'[Page {i+1}]\n{page.extract_text() or ""}')
        return '\n\n'.join(parts)
    if ext == '.docx':
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError('DOCX ingestion requires python-docx') from exc
        document = Document(str(path))
        return '\n'.join(p.text for p in document.paragraphs if p.text.strip()) + '\n' + '\n'.join(
            ' | '.join(c.text for c in row.cells) for t in document.tables for row in t.rows
        )
    if preserve_csv:
        with path.open(encoding='utf-8-sig',errors='replace',newline='') as stream:text=stream.read()
    else:text = path.read_text(encoding='utf-8-sig', errors='replace')
    if ext=='.csv' and sum(1 for _ in csv.reader(io.StringIO(text,newline='')))>10000:raise ValueError('CSV exceeds 10000 record limit')
    if ext=='.jsonl' and len(text.splitlines())>10000:raise ValueError('JSONL exceeds 10000 record limit')
    if ext in ('.html', '.htm'):
        text = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', text)
        return html.unescape(re.sub('<[^>]+>', ' ', text))
    if ext in ('.json', '.jsonl'):
        if ext == '.json':
            try:
                parsed=json.loads(text);stack=[(parsed,0)];nodes=0
                while stack:
                    value,depth=stack.pop();nodes+=1
                    if depth>64 or nodes>100000:raise ValueError('JSON complexity resource limit exceeded')
                    if isinstance(value,dict):stack.extend((v,depth+1) for v in value.values())
                    elif isinstance(value,list):stack.extend((v,depth+1) for v in value)
                return json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                return text
        return text
    if ext == '.csv' and not preserve_csv:
        rows = []
        for row in csv.DictReader(io.StringIO(text)):
            rows.append(' | '.join(f'{k}: {v}' for k, v in row.items()))
        return '\n'.join(rows)
    return text


def _extract(path: Path, *, preserve_csv=False) -> str:
    from .parser_boundary import extract
    return extract(path,preserve_csv=preserve_csv)


def extract_document(path, cfg):
    if _WORKER_ACTIVE:return _extract_in_process(path,preserve_csv=cfg.get('settings',{}).get('table_evidence',False))
    from .parser_boundary import extract
    return extract(path,preserve_csv=cfg.get('settings',{}).get('table_evidence',False),root=cfg['_root'])


def make_chunks(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    if overlap_chars >= chunk_chars:
        raise ValueError('overlap_chars must be smaller than chunk_chars')
    # Prefer paragraph break to avoid splitting facts, but always guarantee progress.
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        if end < len(text):
            mark = text.rfind('\n', start + chunk_chars // 2, end)
            if mark > start:
                end = mark + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(start + 1, end - overlap_chars)
    return chunks


def sentence_passages(text: str, max_chars: int) -> list[dict]:
    """Literal source spans, not rewritten summaries or verified standalone facts.

    Preserve common abbreviation/decimal boundaries and following qualifications.
    Oversize sentences are explicitly marked fragments. Offsets bind citations to
    the extracted document; metadata applicability and entailment still need review.
    """
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError('Passage size must be a positive integer')
    boundaries = [0]
    abbreviations = {'rev', 'proc', 'sec', 'no', 'dr', 'mr', 'mrs', 'ms', 'vs', 'fig', 'e.g', 'i.e'}
    for match in re.finditer(r'[.!?]\s+(?=[A-Z(])', text):
        prefix = text[:match.start()].rstrip()
        word = re.search(r'([\w.]+)$', prefix)
        if text[match.start()] == '.' and word and (word[1].lower() in abbreviations or len(word[1]) == 1):
            continue
        boundaries.append(match.start()+1)
    boundaries.append(len(text))
    spans = []
    for start, end in zip(boundaries, boundaries[1:]):
        while start < end and text[start].isspace(): start += 1
        while end > start and text[end-1].isspace(): end -= 1
        if start < end: spans.append((start, end))
    joined = []
    for start, end in spans:
        # Keep an immediately following caveat with its antecedent when possible.
        if joined and re.match(r'(?:However|Except|Unless|Provided|This|These|It)\b', text[start:end]) and end-joined[-1][0] <= max_chars:
            joined[-1] = (joined[-1][0], end)
        else: joined.append((start, end))
    result = []
    for start, end in joined:
        fragmented = end-start > max_chars
        while start < end:
            stop = min(end, start+max_chars)
            if stop < end:
                space = text.rfind(' ', start+max_chars//2, stop)
                if space > start: stop = space
            result.append({'text':text[start:stop], 'start':start, 'end':stop, 'fragmented':fragmented})
            start = stop
            while start < end and text[start].isspace(): start += 1
    return result


def _scan_sources_in_process(cfg: dict, *, include_text: bool = True) -> tuple[list[dict], list[dict]]:
    root = Path(cfg['_root']).resolve()
    st = cfg.get('settings', {})
    chunk_chars = int(st.get('chunk_chars', 1100))
    overlap = int(st.get('overlap_chars', 150))
    strategy = st.get('chunk_strategy', 'fixed')
    if strategy not in ('fixed', 'sentences'):
        raise ValueError('Unknown chunk strategy')
    original_titles = {}
    if cfg.get('data_provenance'):
        provenance = json.loads(secure_path(root, cfg['data_provenance']).read_text())
        original_titles = {d['id']: d['title'] for d in provenance.get('documents', [])
                           if isinstance(d.get('id'), str) and isinstance(d.get('title'), str)}
    documents, chunks = [], []
    total_chars = 0
    for source in cfg['sources']:
        folder = secure_path(root, source['path'])
        for path in sorted(folder.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            # Following symlinks could read secrets outside project.
            if not path.resolve().is_relative_to(root):
                raise ValueError(f'Symlink escapes workspace: {path}')
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(f'File exceeds 12MB limit: {path.relative_to(root)}')
            if len(documents) >= MAX_FILES:
                raise ValueError('Document count exceeds configured safety limit')
            content = _extract_in_process(path,preserve_csv=st.get('table_evidence',False))
            if len(content) > MAX_EXTRACTED_CHARS:
                raise ValueError('Extracted document exceeds 400000 character limit; no partial text accepted')
            if not content.strip():
                continue
            total_chars += len(content)
            if total_chars > MAX_TOTAL_TEXT_CHARS:
                raise ValueError('Extracted corpus exceeds 12 million characters')
            rel = path.relative_to(root).as_posix()
            document_id = f"{source['id']}::{path.relative_to(folder).as_posix()}"
            title = original_titles.get(document_id, path.name)
            if '_parser_texts' in cfg:cfg['_parser_texts'][document_id]=content
            fingerprint = hashlib.sha256(content.encode('utf-8')).hexdigest()
            documents.append({'id': document_id, 'source_id': source['id'], 'path': rel,
                              'title': title, 'fingerprint': fingerprint,
                              'characters': len(content), 'bytes': path.stat().st_size})
            if include_text:
                tables=[]
                if st.get('table_evidence',False):
                    from .tables import passages
                    tables=passages(content,path.suffix.lower(),chunk_chars)
                    raw_fingerprint=hashlib.sha256(path.read_bytes()).hexdigest() if tables else None
                    for part in tables:
                        identity=hashlib.sha256(part['text'].encode()).hexdigest()[:12]
                        chunks.append({**part,'id':f"{document_id}#chunk-t{part['start']}-{part['end']}-{identity}",
                            'document_id':document_id,'source_id':source['id'],'title':title,
                            'document_fingerprint':fingerprint,'chunk_strategy':'table','raw_source_sha256':raw_fingerprint,
                            'offset_basis':'UTF-8-sig decoded document characters, original newlines'})
                    if tables:
                        # Never also supply a decontextualized fragment of a table.
                        position=0
                        for start,end in [(p['start'],p['end']) for p in tables]+[(len(content),len(content))]:
                            if start>position:
                                for part in sentence_passages(content[position:start],chunk_chars):
                                    part={**part,'start':part['start']+position,'end':part['end']+position}
                                    identity=hashlib.sha256(part['text'].encode()).hexdigest()[:12]
                                    chunks.append({**part,'id':f"{document_id}#chunk-p{part['start']}-{part['end']}-{identity}",
                                        'document_id':document_id,'source_id':source['id'],'title':title,
                                        'document_fingerprint':fingerprint,'chunk_strategy':'sentences'})
                            position=end
                        continue
                if strategy == 'sentences':
                    for part in sentence_passages(content, chunk_chars):
                        identity = hashlib.sha256(part['text'].encode()).hexdigest()[:12]
                        chunks.append({**part, 'id':f"{document_id}#chunk-p{part['start']}-{part['end']}-{identity}",
                                       'document_id':document_id, 'source_id':source['id'], 'title':title,
                                       'document_fingerprint':fingerprint, 'chunk_strategy':strategy})
                    continue
                for ix, part in enumerate(make_chunks(content, chunk_chars, overlap)):
                    chunks.append({'id': f'{document_id}#chunk{ix}', 'document_id': document_id,
                                   'source_id': source['id'], 'text': part, 'title': title})
    return documents, chunks


def _load_benchmark_in_process(cfg: dict) -> list[dict[str, Any]]:
    path = secure_path(Path(cfg['_root']), cfg.get('benchmark', 'benchmark.jsonl'))
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Benchmark exceeds 12MB limit')
    tasks = []
    if path.suffix == '.jsonl':
        lines = [(i, line.strip()) for i, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1) if line.strip()]
        tasks = [_checked_task(json.loads(line), line_number) for line_number, line in lines]
    else:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, list):
            raise ValueError('Benchmark JSON must contain a list')
        tasks = [_checked_task(item, i) for i, item in enumerate(data, 1)]
    if len(tasks) > 10000:
        raise ValueError('Benchmark exceeds 10000 task limit')
    ids = [task['id'] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError('Benchmark task IDs must be unique')
    return tasks


def _checked_task(item: dict, line: int) -> dict:
    if not isinstance(item, dict) or not str(item.get('question', '')).strip():
        raise ValueError(f'Benchmark line {line} must have a question')
    if 'expected' not in item:
        raise ValueError(f'Benchmark line {line} needs independent expected ground truth')
    method = item.get('scoring', 'exact')
    if method not in ('exact', 'qa_exact', 'contains', 'numeric', 'regex','structured_exact'):
        raise ValueError(f'Unsupported scoring on benchmark line {line}')
    if len(str(item['question'])) > 6000 or len(str(item['expected'])) > 3000:
        raise ValueError(f'Benchmark entry too long on line {line}')
    split = item.get('split')
    if split not in (None, 'development', 'heldout'):
        raise ValueError('Task split must be development or heldout')
    if type(item.get('critical', False)) is not bool:
        raise ValueError('critical must be boolean')
    accepted = item.get('accepted_answers', [str(item['expected'])])
    evidence = item.get('evidence', [])
    if not isinstance(accepted, list) or not accepted or not all(isinstance(a, str) and a.strip() for a in accepted):
        raise ValueError('accepted_answers must be a nonempty list of strings')
    if not isinstance(evidence, list) or not all(isinstance(e, dict) and isinstance(e.get('document_id'), str) and isinstance(e.get('quote'), str) for e in evidence):
        raise ValueError('Evidence must contain document IDs and source quotes')
    result = {'critical': item.get('critical',False), 'accepted_answers': accepted, 'evidence': evidence, 'dataset': item.get('dataset'), 'group_id': str(item.get('group_id') or item.get('id') or f'task-{line}'),
            'review_status': str(item.get('review_status', 'unreviewed')),
            'reviewer': str(item.get('reviewer') or ''), 'split': split, 'id': str(item.get('id') or f'task-{line}'), 'question': str(item['question']),
            'expected': str(item['expected']), 'scoring': method,
            'tolerance': float(item.get('tolerance', 0)), 'category': str(item.get('category', 'General'))}

    for key in ('scope','requires_grounding','behavior_constraint','answer_contract','evidence_contract','calculation_contract','calculation_authorization'):
        if key in item:result[key]=item[key]
    if 'requires_grounding' in result and type(result['requires_grounding']) is not bool:raise ValueError('requires_grounding must be boolean')
    if 'behavior_constraint' in result and result['behavior_constraint'] not in ('protected','expected_change'):raise ValueError('Invalid behavior constraint')
    if 'scope' in result:
        if not isinstance(result['scope'],dict) or set(result['scope'])-{'jurisdiction','as_of','policy_scope'} or any(not isinstance(v,str) for v in result['scope'].values()):raise ValueError('Invalid task scope')
    from .answer_contract import validate as validate_answer
    from .evidence_contract import validate as validate_evidence
    validate_answer(result.get('answer_contract'));validate_evidence(result.get('evidence_contract'))
    from .facts import validate as validate_calculation
    validate_calculation(result.get('calculation_contract'))
    if 'calculation_authorization' in result and not isinstance(result['calculation_authorization'],dict):raise ValueError('Calculation authorization must be an explicit object')
    if method=='structured_exact':
        if result.get('answer_contract',{}).get('type')!='structured':raise ValueError('structured_exact requires explicit structured contract')
        result['expected_raw']=item['expected']
        if isinstance(item['expected'],dict):result['expected']=json.dumps(item['expected'],sort_keys=True,separators=(',',':'))
    return result


def scan_sources(cfg: dict, *, include_text: bool = True):
    if _WORKER_ACTIVE:return _scan_sources_in_process(cfg,include_text=include_text)
    from .parser_boundary import scan
    return scan(cfg,include_text=include_text)


def load_benchmark(cfg: dict):
    if _WORKER_ACTIVE:return _load_benchmark_in_process(cfg)
    from .parser_boundary import benchmark
    return benchmark(cfg)
