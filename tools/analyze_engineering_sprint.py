"""No-inference analysis, historical integrity audit and equal-authority CI replay."""
from copy import deepcopy
import contextlib
import difflib
import io
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from tools.validate_engineering_sprint import ART,BASE,ROOT,dump as immutable_dump,sha
from tools.analyze_real_world_e2e import conventional
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark,_extract
from sourceroi.live.data_ci import digest,evidence_coverage
from sourceroi.live.grade import wilson_interval
from sourceroi.live.policies import select_context
from sourceroi.live.cli import main as cli


def dump(path,value):
    # Analysis is safely resumable after failure; never replace different evidence.
    if Path(path).exists():
        if json.loads(Path(path).read_text()) != value:raise ValueError('Different analysis artifact already exists: '+str(path))
        return
    immutable_dump(path,value)


def main():
    results=json.loads((ART/'results.json').read_text());ledger=json.loads((ART/'execution-log.json').read_text());summaries={};pending=[]
    original=results['variants']['original']['variant']; successes={r['id'] for r in original['tasks'] if r['correct']}
    for name,entry in results['variants'].items():
        rows=entry['variant']['tasks'];supported=[r for r in rows if r['id']!='canadian_favr']
        quality=(len(rows)==4 and all(r['correct'] for r in rows) and all(r['literal_reference_coverage']==1 for r in supported)
                 and all(not r['invalid_citations'] for r in rows) and not(successes-{r['id'] for r in rows if r['correct']}))
        summaries[name]={'supported_correct':sum(r['correct'] for r in supported),'supported_n':len(supported),
            'supported_accuracy_ci95':wilson_interval(sum(r['correct'] for r in supported),len(supported)),
            'registered_correct':sum(r['correct'] for r in rows),'registered_n':len(rows),
            'false_abstentions':sum(r['actual']=='INSUFFICIENT_EVIDENCE' for r in supported),
            'model_calls':sum(r['answer_origin']=='model' for r in rows),
            'prompt_tokens':sum(r['prompt_tokens'] for r in rows),'completion_tokens':sum(r['completion_tokens'] for r in rows),
            'total_tokens':sum(r['prompt_tokens']+r['completion_tokens'] for r in rows),
            'mean_latency_ms':entry['variant']['metrics']['mean_latency_ms'],
            'supported_full_reference_coverage':sum(r['literal_reference_coverage']==1 for r in supported),
            'invalid_citation_ids':sum(len(r['invalid_citations']) for r in rows),
            'independent_semantic_correctness':None,'independent_citation_correctness':None,
            'development_quality_rule_pass':quality,'deployment_qualified':False,
            'answers':[{k:r[k] for k in ['id','expected','actual','correct','literal_reference_coverage','citations','answer_origin']} for r in rows]}
        pending+=entry['review_items']
    for name,s in summaries.items():
        s['total_token_reduction_pct_vs_original']=100*(1-s['total_tokens']/summaries['original']['total_tokens'])
        s['quality_preserving_development_smoke_only']=bool(name!='original' and s['development_quality_rule_pass'] and summaries['original']['development_quality_rule_pass'] and s['total_tokens']<summaries['original']['total_tokens'])
    dump(ART/'pending-semantic-reviews.json',{'kind':'external_release_review_packet','independently_reviewed':False,'items':pending,
        'instructions':'External operator authorizes independent reviewers. Complete claim spans, quoted cited support, correctness and applicability. Software abstention is not a generated model answer. Do not infer semantic support from matching numbers. See tools/release_review_packet.py score.'})
    # Run ordinary maintained checkers with identical approved information and outputs.
    old=ROOT/'docs/artifacts/irs-e2e';release=json.loads((old/'release.json').read_text())
    before=read_config(ROOT/'workspace/irs-e2e/accepted');after=read_config(ROOT/'workspace/irs-e2e/candidate')
    annotations={r['id']:r for r in json.loads((old/'frozen-annotations.json').read_text())['annotations']}
    comparator={}
    for name in ['maintained_full_suite','maintained_with_diff']:
        evaluated=conventional(before,after,release,annotations)
        comparator[name]={'verdict':evaluated['verdict'],'wall_ms':evaluated['wall_ms'],'task_executions':12,
            'new_generation_calls':0,'new_tokens':0,'human_edits':None,'human_review_actions':None,'human_seconds':None,
            'conditions':evaluated['conditions']}
    beforetext=_extract(ROOT/'workspace/irs-e2e/accepted/sources/current/CURRENT notice.pdf')
    aftertext=_extract(ROOT/'workspace/irs-e2e/candidate/sources/current/CURRENT notice.pdf')
    dump(ART/'baseline-b-diffs-and-traces.json',{'source_diff':list(difflib.unified_diff(beforetext.splitlines(),aftertext.splitlines(),fromfile='2024',tofile='2025')),
        'outputs_and_retrieval_traces':{'baseline':release['baseline'],'candidate':release['candidate']},
        'approved_information':release['review'],'note':'Ordinary baseline B receives diffs/traces and equivalent approved facts. No human session was performed.'})
    # Exercise actual CLI entrypoint with recorded real outputs at evaluator boundary.
    # All source/version/review/strict checks execute; networking is forbidden.
    spec=old/'change-plan-v2.json';review=old/'technical-development-review-v2.json'
    execute=a.execute
    def callback(cfg,questions):
        stage='baseline' if cfg['_root']==before['_root'] else 'candidate'
        variant=deepcopy(release[stage]);ids={q['id'] for q in questions}
        variant['tasks']=[r for r in variant['tasks'] if r['id'] in ids]
        return variant
    def replay(*args,**kwargs):return execute(*args,**kwargs,callback=callback,persist=False)
    args=['--project',after['_root'],'release-check','--baseline',before['_root'],'--spec',str(spec),'--approval',str(review),
        '--policy','strict_grounded','--output',str(ART/'ci-replay.json'),'--allow-model-calls']
    start=time.perf_counter();stdout=io.StringIO()
    with patch.object(a,'execute',replay),patch('sourceroi.live.provider._post',side_effect=AssertionError('No inference during replay')),contextlib.redirect_stdout(stdout):
        exit_code=cli(args)
    ci=json.loads((ART/'ci-replay.json').read_text())
    comparator['sourceroi']={'verdict':ci['verdict'],'wall_ms':(time.perf_counter()-start)*1000,'task_executions':12,'new_generation_calls':0,'new_tokens':0,
        'human_edits':None,'human_review_actions':None,'human_seconds':None,'maintenance_counters':ci['maintenance'],
        'cli_exit_code':exit_code,'replay':True,'note':'Real CLI/control flow, preserved real outputs at callback boundary; not fresh inference or independent implementation.'}
    assert exit_code==a.EXIT_CODES['BLOCK'] and ci['verdict']=='BLOCK'
    dump(ART/'ci-execution.json',{'argv':args,'exit_code':exit_code,'stdout':stdout.getvalue(),'new_generation_calls':0,
        'network_disabled':True,'origin':'same-output callback replay at actual CLI entrypoint; inherited response usage is not new usage'})
    # Previously exposed IRS tasks: retrieval replay only, never new accuracy evidence.
    coverage=[]
    for stage in ['accepted','candidate']:
        cfg=read_config(ROOT/'workspace/irs-e2e'/stage);tasks=load_benchmark(cfg)
        if stage=='candidate':
            for t in tasks:
                ann=annotations[t['id']];t['evidence']=ann['evidence_after'];t['expected']=ann['expected_after']
        for policy in ['original','passage_coverage']:
            cfg=deepcopy(cfg);cfg['settings'].update(chunk_strategy='sentences' if policy=='passage_coverage' else 'fixed',retrieval_policy={'name':policy,'k':3})
            _,chunks=scan_sources(cfg)
            for task in tasks:
                ctx,trace=select_context(task['question'],chunks,cfg)
                coverage.append({'stage':stage,'policy':policy,'task':task['id'],'reference_coverage':evidence_coverage(task,{'retrieved_chunk_ids':[c['id'] for c in ctx]},ctx),
                                 'context_chars':sum(len(c['text']) for c in ctx),'new_model_calls':0,'answer_correctness':None})
    dump(ART/'historical-retrieval-replay.json',coverage)
    hashes=json.loads((ART/'before-hashes.json').read_text())
    historical={path:sha(ROOT/path)==value for path,value in hashes.items() if path.startswith('docs/artifacts/irs-e2e/') or path=='REAL_WORLD_VALIDATION_REPORT.md'}
    assert all(historical.values())
    assert ledger['actual_generation_requests']<=12 and ledger['elapsed_seconds']<=120
    assert len(list((ART/'calls').glob('*-request.json')))==ledger['actual_generation_requests']
    freeze=json.loads((ART/'freeze.json').read_text())
    assert all(sha(ROOT/path)==value for path,value in freeze['configuration_files'].items())
    dump(ART/'summary.json',{'classifications':'Development metrics only; independent final PENDING','variants':summaries,'comparators':comparator,
        'ledger_totals':{'generation_requests':ledger['actual_generation_requests'],'seconds':ledger['elapsed_seconds'],
            'reported_tokens':sum(e.get('usage',{}).get('total_tokens',0) for e in ledger['events']),'external_spend_usd':0},
        'historical_files_unchanged':all(historical.values()),'historical_files_checked':len(historical),
        'frozen_configuration_and_benchmark_unchanged':True,'independent_final_status':'PENDING','human_study_status':'PENDING',
        'comparison_limit':'Shared deterministic primitives; same-output replay not independently implemented checker validation. Single unnormalized timings; no human time savings measured.'})
    print(json.dumps({'summaries':summaries,'comparators':comparator},indent=2))


if __name__=='__main__':main()
