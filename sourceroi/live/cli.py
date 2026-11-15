"""CLI for genuine data and agent evaluations."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from .config import DEFAULT_WORKSPACE, SUPPORTED_EXTENSIONS, read_config, public_config
from .engine import compare_runs, preflight, run
from . import db


def make_workspace(documents: str, output: str, benchmark: str | None = None) -> Path:
    source = Path(documents).expanduser().resolve()
    destination = Path(output).expanduser().resolve()
    if not source.is_dir():
        raise ValueError('--documents must be an existing directory')
    if source == destination or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Input and output directories must be separate')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Output directory must be empty or nonexistent to avoid overwriting files')
    destination.mkdir(parents=True, exist_ok=True)
    folders = [p for p in source.iterdir() if p.is_dir() and not p.is_symlink()]
    # Immediate subdirectories are datasets; loose files become General.
    sources = []
    total = 0
    def copy_group(folder: Path, name: str, files: list[Path]):
        nonlocal total
        if not files:
            return
        ident = re.sub('[^a-zA-Z0-9_-]+','-',name).strip('-').lower() or 'documents'
        if not ident[0].isalpha():
            ident = 'data-'+ident
        while any(s['id']==ident for s in sources):
            ident += '-2'
        dst = destination/'sources'/ident
        dst.mkdir(parents=True,exist_ok=True)
        for f in files:
            if f.is_symlink() or f.stat().st_size > 12*1024*1024:
                continue
            target = dst/f.relative_to(folder)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(f,target)
            total += 1
        sources.append({'id':ident,'name':name,'path':f'sources/{ident}','per_call_price_usd':None})
    loose = [p for p in source.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    copy_group(source, 'General documents', loose)
    for folder in sorted(folders):
        files = [p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.is_symlink()]
        copy_group(folder, folder.name, files)
    if not total:
        raise ValueError('No supported files found; use .pdf, .docx, .md, .txt, .csv, .json, or .html')
    if total > 2500:
        raise ValueError('Workspace exceeds 2500 file cap')
    if benchmark:
        shutil.copy2(Path(benchmark).expanduser().resolve(),destination/'benchmark.jsonl')
    else:
        (destination/'benchmark.jsonl').write_text('',encoding='utf-8')
    cfg = {'id':re.sub('[^a-z0-9_-]+','-',destination.name.lower()).strip('-'),
           'name':destination.name.replace('-', ' ').title(),
           'runner':'rag_chat', 'benchmark':'benchmark.jsonl',
           'model': {'name':'gpt-4.1-mini','base_url':'https://api.openai.com/v1',
                     'api_key_env':'OPENAI_API_KEY','temperature':0,
                     'timeout_seconds':90,'max_output_tokens':500,
                     'input_price_per_million_usd':None,'output_price_per_million_usd':None},
           'settings': {'max_chunks':5,'chunk_chars':1100,'overlap_chars':150,
                        'max_tasks_per_run':50,'max_documents_per_study':8,'max_model_calls_per_run':100,
                        'max_estimated_model_cost_usd':None},
           'sources':sources}
    (destination/'project.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    return destination


def _main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m sourceroi',description='Real-source agent evaluation and Data CI')
    parser.add_argument('--project',default=str(DEFAULT_WORKSPACE),help='Workspace directory containing project.json')
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init',help='Copy your own source documents into a new workspace')
    init.add_argument('--documents',required=True)
    init.add_argument('--output',required=True)
    init.add_argument('--benchmark',help='Optional independent JSONL answer key to copy')
    serve=sub.add_parser('serve',help='Launch real evaluation dashboard (localhost only)')
    serve.add_argument('--host',default='127.0.0.1')
    serve.add_argument('--port',type=int,default=8765)
    serve.add_argument('--require-auth',action='store_true',help='Fail unless workspace identities were provisioned; execution disabled in this staged target')
    sub.add_parser('auth-migrate',help='Explicit stopped-writer schema upgrade; revokes sessions/receipts and fences unfinished jobs')
    sub.add_parser('auth-init',help='Initialize owner-only workspace identity store (no network or inference)')
    identity=sub.add_parser('auth-add-user',help='Add identity using an interactive hidden password prompt')
    identity.add_argument('--user',required=True)
    identity.add_argument('--role',required=True,choices=['viewer','operator','reviewer','admin'])
    role=sub.add_parser('auth-set-role',help='Change role and revoke existing sessions/approvals')
    role.add_argument('--user',required=True);role.add_argument('--role',required=True,choices=['viewer','operator','reviewer','admin'])
    reset=sub.add_parser('auth-reset-password',help='Reset password interactively and revoke sessions/approvals')
    reset.add_argument('--user',required=True)
    revoke=sub.add_parser('auth-disable-user',help='Disable user and revoke sessions and outstanding approvals')
    revoke.add_argument('--user',required=True)

    worker=sub.add_parser('job-worker-once',help='Foreground offline-only durable worker; never generates')
    worker.add_argument('--worker-id')
    sub.add_parser('job-recover',help='Seal expired owners conservatively; never redispatch')
    status=sub.add_parser('job-status');status.add_argument('--job-id',required=True)
    backup_cmd=sub.add_parser('workspace-backup');backup_cmd.add_argument('--output',type=Path,required=True);backup_cmd.add_argument('--quiesced',action='store_true')
    restore_cmd=sub.add_parser('workspace-restore');restore_cmd.add_argument('--archive',type=Path,required=True);restore_cmd.add_argument('--destination',type=Path,required=True);restore_cmd.add_argument('--sha256',required=True)
    retention=sub.add_parser('retention-preview');retention.add_argument('paths',nargs='+')
    runtime=sub.add_parser('runtime-cleanup',help='Inspect or remove only verified inactive runtime scratch, never workspace history')
    runtime.add_argument('--confirmed',action='store_true')
    runtime.add_argument('--operation',action='append')
    runtime.add_argument('--archive-directory',type=Path)
    sub.add_parser('doctor',help='Check workspace, data, tasks and provider configuration')
    decision=sub.add_parser('knowledge-decide',help='Offline evidence-only knowledge alternatives; never generates or applies changes')
    decision.add_argument('--request',type=Path,required=True)
    run_cmd=sub.add_parser('run',help='Run real LLM or customer-agent evaluations')
    run_cmd.add_argument('--without',nargs='*',default=[],help='Remove source IDs for counterfactual')
    run_cmd.add_argument('--ablate',action='store_true',help='Run baseline + each source removed')
    run_cmd.add_argument('--without-documents',nargs='*',default=[],help='Exclude specific document IDs')
    run_cmd.add_argument('--ablate-documents',nargs='*',default=[],help='Study specific document IDs one at a time')
    run_cmd.add_argument('--max-tasks',type=int,default=None)
    run_cmd.add_argument('--allow-model-calls',action='store_true',help='Confirm live model/API charges')
    run_cmd.add_argument('--json',action='store_true')
    sub.add_parser('runs',help='List saved evaluations')
    cmp=sub.add_parser('compare',help='Compare two previously saved live runs')
    cmp.add_argument('--before',required=True)
    cmp.add_argument('--after',required=True)
    cmp.add_argument('--fail-on-regression',action='store_true')
    optimize_cmd=sub.add_parser('optimize',help='Find the lowest-cost source set that satisfies a quality floor')
    optimize_cmd.add_argument('--quality-floor',type=float,default=0.9)
    optimize_cmd.add_argument('--objective',choices=['cost_per_success','token_budget','latency','balanced'],default='cost_per_success')
    optimize_cmd.add_argument('--min-citation-rate','--min-groundedness',dest='min_groundedness',type=float,default=0.75,
                              help='Citation validity threshold; does not measure semantic groundedness')
    optimize_cmd.add_argument('--max-tasks',type=int,default=None)
    optimize_cmd.add_argument('--json',action='store_true')
    optimize_cmd.add_argument('--allow-model-calls',action='store_true')
    optimize_cmd.add_argument('--repeats',type=int,default=1)
    optimize_cmd.add_argument('--max-candidates',type=int,default=8)
    optimize_cmd.add_argument('--max-accuracy-drop',type=float,default=0.0)
    optimize_cmd.add_argument('--max-regressions',type=int,default=0)
    study = sub.add_parser('study', help='Tune strong baselines and task-aware routing on development tasks')
    study.add_argument('--objective', choices=['token_budget','cost_per_success','latency','p95_latency','balanced'], default='token_budget')
    study.add_argument('--quality-floor', type=float, default=.95)
    study.add_argument('--min-groundedness', type=float, default=.9)
    study.add_argument('--repeats', type=int, default=1)
    study.add_argument('--reviews', type=Path, help='Completed claim-adjudication JSON packet')
    study.add_argument('--output', type=Path, required=True)
    study.add_argument('--allow-model-calls', action='store_true')
    study.add_argument('--approved-spend-usd', type=float, default=None,
                       help='Explicit approval required for remote execution; omit for free localhost only')
    dataset = sub.add_parser('public-benchmark', help='Import independently annotated SQuAD/HotpotQA documents and tasks')
    dataset.add_argument('--download', action='store_true', help='Download free public dataset files (no model calls)')
    dataset.add_argument('--cache', type=Path, default=Path('workspace/.cache/public-qa'))
    dataset.add_argument('--squad', type=Path)
    dataset.add_argument('--hotpot', type=Path)
    dataset.add_argument('--per-dataset', type=int, default=8)
    dataset.add_argument('--exclude-prior-workspace', type=Path, action='append', help='Exclude article families from an already exposed public workspace')
    dataset.add_argument('--tasks-per-article', type=int, default=1, help='Published SQuAD questions per article; groups never cross splits')
    dataset.add_argument('--output', type=Path, required=True)
    retrieval_audit = sub.add_parser('audit-retrieval', help='Check published support coverage without any model calls')
    retrieval_audit.add_argument('--output', type=Path, required=True)
    frozen = sub.add_parser('freeze', help='Create an immutable baseline source/configuration snapshot')
    frozen.add_argument('--output', type=Path, required=True)
    ci = sub.add_parser('data-ci', help='Compare a frozen source baseline to current data; localhost only')
    ci.add_argument('--baseline', type=Path, required=True)
    ci.add_argument('--output', type=Path, required=True)
    ci.add_argument('--max-tasks', type=int, default=20)
    ci.add_argument('--max-seconds', type=int, default=300)
    ci.add_argument('--max-regressions', type=int, default=0)
    ci.add_argument('--max-accuracy-drop', type=float, default=0)
    ci.add_argument('--max-evidence-drop', type=float, default=0)
    ci.add_argument('--affected-only', action='store_true')
    ci.add_argument('--repair', action='store_true')
    ci.add_argument('--ablate', action='store_true')
    ci.add_argument('--allow-model-calls', action='store_true')
    diagnosis = sub.add_parser('diagnose', help='Inspect stored task failures without model calls')
    diagnosis.add_argument('--run-id', required=True)
    diagnosis.add_argument('--output', type=Path, required=True)
    diagnosis.add_argument('--calculation-spec',type=Path,help='Task-ID mapping of review-only subject/unit/period arithmetic declarations; never changes answers or release verdicts')
    evidence_study=sub.add_parser('reliability-study',help='Bounded local evidence-aware comparison on grouped tasks')
    evidence_study.add_argument('--previous-policy',type=Path,required=True,help='Previously frozen policy or study JSON; no answer feedback is used')
    evidence_study.add_argument('--output',type=Path,required=True)
    evidence_study.add_argument('--max-calls',type=int,default=320)
    evidence_study.add_argument('--max-seconds',type=int,default=900)
    evidence_study.add_argument('--allow-model-calls',action='store_true')
    change=sub.add_parser('change-plan',help='Propose reviewable knowledge/test changes without inference')
    change.add_argument('--baseline',type=Path,required=True)
    change.add_argument('--output',type=Path,required=True)
    change.add_argument('--intent',type=Path)
    approve=sub.add_parser('change-review',help='Bind explicit review decisions to an exact change proposal')
    approve.add_argument('--spec',type=Path,required=True)
    approve.add_argument('--decisions',type=Path,required=True)
    approve.add_argument('--output',type=Path,required=True)
    release=sub.add_parser('release-check',help='Bounded local knowledge release assurance')
    release.add_argument('--baseline',type=Path,required=True)
    release.add_argument('--spec',type=Path,required=True)
    release.add_argument('--approval',type=Path)
    release.add_argument('--output',type=Path,required=True)
    release.add_argument('--max-calls',type=int,default=40)
    release.add_argument('--max-seconds',type=int,default=120)
    release.add_argument('--targeted',action='store_true')
    release.add_argument('--allow-model-calls',action='store_true')
    release.add_argument('--policy',choices=['legacy_exact','strict_grounded'])
    release.add_argument('--semantic-reviews',type=Path)
    release.add_argument('--reviewers',type=Path)
    sub.add_parser('knowledge-timeline',help='Exact-version release history')
    args=parser.parse_args(argv)
    try:
        if args.command=='init':
            path=make_workspace(args.documents,args.output,args.benchmark)
            print(f'Created real-data workspace at {path}')
            print('Next: add independently verified Q&A to benchmark.jsonl, set OPENAI_API_KEY, then serve.')
            return 0
        if args.command=='public-benchmark':
            from .datasets import fetch_public, build_public_workspace
            if args.download:
                paths = fetch_public(args.cache)
            elif args.squad and args.hotpot:
                paths = {'squad': args.squad, 'hotpot': args.hotpot}
            else:
                raise ValueError('Use --download or provide both --squad and --hotpot published JSON files')
            result = build_public_workspace(paths['squad'], paths['hotpot'], args.output, per_dataset=args.per_dataset, tasks_per_article=args.tasks_per_article,
                                            exclude_provenance=[p/'provenance.json' for p in args.exclude_prior_workspace] if args.exclude_prior_workspace else None)
            print(json.dumps(result, indent=2))
            return 0
        if args.command=='workspace-restore':
            from .workspace_recovery import restore
            print(json.dumps(restore(args.archive,args.destination,expected_sha256=args.sha256),indent=2));return 0
        if args.command=='runtime-cleanup':
            from .runtime_resources import inspect_cleanup
            print(json.dumps(inspect_cleanup(delete=args.confirmed,ids=args.operation,archive_directory=args.archive_directory),indent=2));return 0
        cfg=read_config(args.project)
        if args.command=='knowledge-decide':
            from .knowledge_decision import DecisionRequest,run as decide
            from .config import secure_path
            from .parser_boundary import snapshot
            body=snapshot(args.request.absolute(),args.request.absolute().parent,max_bytes=128*1024)['bytes']
            request=DecisionRequest.model_validate_json(body)
            baseline=secure_path(Path(cfg['_root']),'.sourceroi/snapshots/'+request.snapshot_id)
            print(json.dumps(decide(read_config(baseline),cfg,request),indent=2));return 0
        if args.command=='workspace-backup':
            from .workspace_recovery import backup
            print(json.dumps(backup(cfg['_root'],args.output,quiesced=args.quiesced),indent=2));return 0
        if args.command=='retention-preview':
            from .workspace_recovery import retention_preview
            print(json.dumps(retention_preview(cfg['_root'],args.paths),indent=2));return 0
        if args.command.startswith('job-'):
            from .security import SecurityStore
            from .durable_jobs import Jobs
            import uuid
            jobs=Jobs(SecurityStore(cfg['_root']))
            result=jobs.run_one(args.worker_id or 'worker-'+uuid.uuid4().hex) if args.command=='job-worker-once' else jobs.recover() if args.command=='job-recover' else jobs.get(args.job_id)
            print(json.dumps(result,indent=2));return 0

        if args.command=='auth-migrate':
            from .workspace_lock import workspace_lock
            from .security import SecurityStore
            with workspace_lock(cfg['_root'],exclusive=True):SecurityStore(cfg['_root'],migrate=True)
            print('Identity schema 2 ready; sessions/receipts revoked; unfinished jobs require reconciliation.');return 0
        if args.command.startswith('auth-'):
            import getpass
            from .security import SecurityStore
            store=SecurityStore(cfg['_root'],initialize=args.command=='auth-init')
            if args.command in ('auth-add-user','auth-reset-password'):
                if not sys.stdin.isatty():raise ValueError('Credential provisioning requires a private interactive terminal; no command-line or piped passwords')
                password=getpass.getpass('Password (16+ characters): ')
                if password!=getpass.getpass('Confirm password: '):raise ValueError('Passwords differ')
                if args.command=='auth-add-user':store.add_user(args.user,password,args.role)
                else:store.reset_password(args.user,password)
            elif args.command=='auth-set-role':store.set_role(args.user,args.role)
            elif args.command=='auth-disable-user':store.revoke_user(args.user)
            print('Identity operation completed. Single-tenant loopback only; authenticated model execution remains disabled.')
            return 0

        if args.command in ('change-plan','change-review','release-check','knowledge-timeline'):
            from . import assurance
            if args.command=='knowledge-timeline':
                print(json.dumps(assurance.timeline(cfg),indent=2));return 0
            if args.output.exists() or args.command=='release-check' and args.output.with_suffix('.md').exists():raise ValueError('Output exists; preserve immutable review/history artifacts')
            if args.command=='change-plan':
                result=assurance.propose(read_config(args.baseline),cfg,intent=json.loads(args.intent.read_text()) if args.intent else None);assurance.save_proposal(cfg,result)
            elif args.command=='change-review':
                spec=json.loads(args.spec.read_text());result=assurance.review(spec,**json.loads(args.decisions.read_text()));assurance.save_review(cfg,spec,result)
            else:
                if not args.allow_model_calls:raise ValueError('Acknowledge local inference with --allow-model-calls')
                result=assurance.execute(read_config(args.baseline),cfg,json.loads(args.spec.read_text()),
                    approval=json.loads(args.approval.read_text()) if args.approval else None,
                    max_calls=args.max_calls,max_seconds=args.max_seconds,targeted=args.targeted,policy=args.policy,
                    semantic_reviews={i['sample_key']:i for i in json.loads(args.semantic_reviews.read_text())['items']} if args.semantic_reviews else None,
                    reviewers=json.loads(args.reviewers.read_text()) if args.reviewers else [])
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,indent=2)+'\n')
            if args.command=='release-check':args.output.with_suffix('.md').write_text(assurance.markdown(result))
            print(json.dumps(result,indent=2))
            return assurance.EXIT_CODES[result['verdict']] if args.command=='release-check' else 0
        if args.command=='audit-retrieval':
            from .public_audit import audit_retrieval
            report = audit_retrieval(cfg)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
            print(json.dumps({'output': str(args.output), 'kind': report['kind'], 'model_calls': 0}, indent=2))
            return 0
        if args.command=='reliability-study':
            if args.output.exists():raise ValueError('Study output exists; choose a new path to preserve prior evidence')
            if not args.allow_model_calls:raise ValueError('Acknowledge local model execution with --allow-model-calls')
            if not 1<=args.max_calls<=500 or not 1<=args.max_seconds<=900:raise ValueError('Use max-calls 1..500 and max-seconds 1..900')
            from .reliability_study import run_reliability_study,export_reliability
            from .validation import Budget
            from .policies import validate_policy
            previous=json.loads(args.previous_policy.read_text())
            previous=previous.get('frozen_policies',{}).get('sourceroi',previous)
            validate_policy(previous)
            if cfg['model'].get('context_tokenizer')!='llama_cpp':raise ValueError('Configure the approved local llama.cpp tokenizer first')
            budget=Budget({**cfg['settings'],'max_model_calls_per_run':min(args.max_calls,cfg['settings'].get('max_model_calls_per_run',100)), 'max_run_seconds':args.max_seconds})
            report=run_reliability_study(cfg,previous,budget=budget)
            export_reliability(report,args.output)
            print(json.dumps({'id':report['run_id'],'verdict':report['verdict'],'generation_calls':report['generation_calls'],'output':str(args.output)},indent=2))
            return 3 if report['verdict']=='Rejected due to quality regression' else 0
        if args.command=='freeze':
            from .data_ci import freeze
            print(json.dumps(freeze(cfg,args.output),indent=2))
            return 0
        if args.command=='data-ci':
            if not args.allow_model_calls:
                raise ValueError('Acknowledge local model execution with --allow-model-calls')
            from .data_ci import run_data_ci
            from .validation import Budget
            if not 1 <= args.max_seconds <= 3600:
                raise ValueError('max-seconds must be 1..3600')
            budget=Budget({**cfg['settings'],'max_run_seconds':args.max_seconds})
            report=run_data_ci(read_config(args.baseline),cfg,max_tasks=args.max_tasks,
                max_regressions=args.max_regressions,max_accuracy_drop=args.max_accuracy_drop,
                max_evidence_drop=args.max_evidence_drop,affected_only=args.affected_only,
                repair=args.repair,ablate=args.ablate,budget=budget)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
            print(json.dumps({'id':report['run_id'],'verdict':report['verdict'],'output':str(args.output)},indent=2))
            return 3 if report['verdict']=='blocked' else 0
        if args.command=='diagnose':
            from .diagnosis import diagnose
            from .ingest import load_benchmark,scan_sources
            saved=db.get(cfg,args.run_id)
            if not saved or not saved.get('report'):
                raise ValueError('Stored run not found')
            report=saved['report']; variant=report.get('candidate') or next(iter(report.get('variants',[])),None)
            if variant is None: raise ValueError('Use a baseline/ablation or Data CI run for this diagnosis command')
            tasks={t['id']:t for t in load_benchmark(cfg)};docs,chunks=scan_sources(cfg)
            expected=report.get('candidate_manifest') or report.get('manifest')
            if expected and expected!={d['id']:d['fingerprint'] for d in docs}:
                raise ValueError('Corpus changed since the run; diagnose against its frozen snapshot')
            calculations=json.loads(args.calculation_spec.read_text()) if args.calculation_spec else {}
            if not isinstance(calculations,dict) or set(calculations)-set(tasks):raise ValueError('Calculation declarations must map known task IDs')
            findings=[diagnose(tasks[r['id']],r,chunks,cfg,calculation=calculations.get(r['id'])) for r in variant['tasks'] if not r['correct'] and r['id'] in tasks]
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps({'findings':findings},indent=2)+'\n')
            print(json.dumps({'output':str(args.output),'findings':len(findings)}))
            return 0
        if args.command=='serve':
            if args.host not in ('127.0.0.1','localhost','::1'):
                raise ValueError('This beta is localhost-only; do not expose it on the internet (no hosted authentication).')
            from .api import create_app
            import uvicorn
            print(f'SourceROI v0.2 live dashboard: http://{args.host}:{args.port}')
            print('No synthetic data or model results in live mode. Pricing only when configured.')
            uvicorn.run(create_app(args.project,authenticated=True if args.require_auth else None),host=args.host,port=args.port,log_level='warning',proxy_headers=False,access_log=False)
            return 0
        if args.command=='doctor':
            result={**public_config(cfg),**preflight(cfg)}
            print(json.dumps({k:v for k,v in result.items() if k!='documents'},indent=2))
            return 0 if result['benchmark_ready'] and result['corpus_ready'] and result['credential_ready'] else 2
        if args.command=='run':
            if not args.allow_model_calls:
                raise ValueError('Live calls may cost money; pass --allow-model-calls to proceed')
            mode='document_ablation' if args.ablate_documents else ('ablation' if args.ablate else 'baseline')
            run_id=db.begin(cfg,mode,args.without)
            try:
                report=run(cfg,exclude_sources=args.without,exclude_documents=args.without_documents,
                           document_ids=args.ablate_documents,mode=mode,max_tasks=args.max_tasks,notify=print)
                db.finish(cfg,run_id,report)
            except Exception as exc:
                db.finish(cfg,run_id,None,f'{type(exc).__name__}: {exc}')
                raise
            if args.json:
                print(json.dumps({'id':run_id,'report':report},indent=2))
            else:
                for v in report['variants']:
                    m=v['metrics']
                    print(f"Exclude {','.join(v['excluded_sources']+v['excluded_documents']) or '(none)'}: {m['passed']}/{m['task_count']} correct; "
                          f"{m['mean_latency_ms']:.0f}ms mean end-to-end; "
                          f"cost {'$'+str(m['total_cost_usd']) if m['total_cost_usd'] is not None else 'unknown'}")
                print('Saved run:',run_id)
            return 0
        if args.command=='runs':
            for row in db.list_runs(cfg,30):
                m=row.get('metrics',{})
                print(row['id'],row['created_at'][:19],row['status'],row['mode'],m.get('accuracy','--'))
            return 0
        if args.command=='compare':
            result=compare_runs(db.get(cfg,args.before),db.get(cfg,args.after))
            print(json.dumps(result,indent=2))
            return 3 if args.fail_on_regression and result['comparison']['lost_tasks'] else 0
        if args.command=='study':
            if not args.allow_model_calls:
                raise ValueError('Pass --allow-model-calls to acknowledge configured model execution')
            from .study import run_study, export_study
            from .grounding import load_reviews
            reviews = load_reviews(args.reviews) if args.reviews else {}
            report = run_study(cfg, objective=args.objective, quality_floor=args.quality_floor,
                               repeats=args.repeats, min_groundedness=args.min_groundedness,
                               reviews=reviews, approved_spend_usd=args.approved_spend_usd)
            export_study(report, args.output)
            print(json.dumps({'id': report['run_id'], 'verdict': report['observed_verdict'],
                              'deployment': report['deployment'], 'output': str(args.output)}, indent=2))
            return 0
        if args.command=='optimize':
            if not args.allow_model_calls:
                raise ValueError('Pass --allow-model-calls to acknowledge evaluation charges')
            from .validation import optimize
            run_id = db.begin(cfg, 'optimization_validation', [])
            try:
                result = optimize(cfg, quality_floor=args.quality_floor, min_citation_rate=args.min_groundedness,
                                  objective=args.objective, max_tasks=args.max_tasks,
                                  repeats=args.repeats, max_candidates=args.max_candidates,
                                  max_accuracy_drop=args.max_accuracy_drop, max_regressions=args.max_regressions)
                db.finish(cfg, run_id, result)
            except Exception as exc:
                db.finish(cfg, run_id, None, type(exc).__name__)
                raise
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                rec = result['recommended']
                print(f"Excluded sources: {rec['excluded_sources'] or '(none)'}")
                print(f"Deployment: {result['deployment']} | saved run: {run_id}")
                print(f"Decision: {rec['decision']} | accuracy={result['baseline']['accuracy']:.2%} -> {rec['accuracy']:.2%}")
                if rec.get('input_token_reduction_pct') is not None:
                    print(f"Input-token reduction: {rec['input_token_reduction_pct']}%")
                print(f"Delta cost: {rec.get('delta_cost_usd')} USD")
                print(f"Reason: {rec['reason']}")
            return 0
    except (OSError,ValueError,KeyError,RuntimeError,json.JSONDecodeError) as exc:
        print(f'SourceROI: {exc}',file=sys.stderr)
        return 2
    return 1


def main(argv=None):
    """Cooperate with complete-workspace quiescence for current CLI entry points."""
    values=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--project',default=str(DEFAULT_WORKSPACE))
    known,rest=parser.parse_known_args(values);command=rest[0] if rest else ''
    if command in ('workspace-backup','workspace-restore','init','auth-migrate') or '--help' in values or not Path(known.project).expanduser().is_dir():return _main(values)
    from .workspace_lock import workspace_lock
    try:
        with workspace_lock(known.project):return _main(values)
    except ValueError as exc:print(f'SourceROI: {exc}',file=sys.stderr);return 2
