"""Local-first FastAPI, jobs and durable run history. Not an internet-facing SaaS."""
from __future__ import annotations
import threading
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .config import read_config, public_config, secure_path
from .ingest import load_benchmark
from .engine import run, compare_runs, preflight, optimize_configurations
from . import db
from .knowledge_decision import DecisionRequest

WEB = Path(__file__).parent / 'web'


class SemanticReviewRequest(BaseModel):
    task_id: str
    binding: str
    decision: str
    claims: list[dict]
    dimensions: dict
    rationale: str = Field(min_length=1,max_length=3000)
    authorization_basis: str = Field(min_length=1,max_length=3000)
    model_config = {'extra':'forbid'}


class FixtureAuthorizationRequest(BaseModel):
    specification: dict
    max_attempts: int = Field(default=8,ge=1,le=40)
    max_seconds: int = Field(default=60,ge=1,le=60)


class DurableJobRequest(BaseModel):
    fixture_authorization: str | None = None
    fixture_responses: dict | None = None
    fixture_mode: str = 'valid'
    specification: dict
    approval: dict
    operation: str = 'offline_release_preflight'
    max_seconds: int = Field(default=60,ge=1,le=300)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1,max_length=64)
    password: str = Field(min_length=1,max_length=1024)


class RunRequest(BaseModel):
    mode: str = 'baseline'
    exclude_sources: list[str] = Field(default_factory=list)
    exclude_documents: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    max_tasks: int | None = Field(default=None, ge=1, le=200)
    acknowledge_model_calls: bool = False


class OptimizationRequest(BaseModel):
    acknowledge_model_calls: bool = False
    quality_floor: float = Field(default=.9, ge=0, le=1)
    min_citation_rate: float = Field(default=.75, ge=0, le=1)
    objective: str = 'cost_per_success'
    max_candidates: int = Field(default=8, ge=1, le=64)
    repeats: int = Field(default=1, ge=1, le=10)
    max_accuracy_drop: float = Field(default=0, ge=0, le=1)
    max_regressions: int = Field(default=0, ge=0, le=200)


class StudyRequest(BaseModel):
    acknowledge_model_calls: bool = False
    quality_floor: float = Field(default=.95, ge=0, le=1)
    min_groundedness: float | None = Field(default=.9, ge=0, le=1)
    objective: str = 'token_budget'
    repeats: int = Field(default=1, ge=1, le=10)
    approved_spend_usd: float | None = Field(default=None, gt=0)
    reviews: dict = Field(default_factory=dict)


class DataCIRequest(BaseModel):
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    acknowledge_model_calls: bool = False
    max_tasks: int = Field(default=12,ge=1,le=20)
    max_seconds: int = Field(default=300,ge=1,le=900)
    max_regressions: int = Field(default=0,ge=0,le=20)
    max_accuracy_drop: float = Field(default=0,ge=0,le=1)
    max_evidence_drop: float = Field(default=0,ge=0,le=1)
    affected_only: bool = False
    repair: bool = False


class ReliabilityRequest(BaseModel):
    previous_policy: dict
    acknowledge_model_calls: bool = False
    max_calls: int = Field(default=320,ge=1,le=500)
    max_seconds: int = Field(default=900,ge=1,le=900)


class ChangePlanRequest(BaseModel):
    intent: dict | None = None
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{32}$')


class ChangeReviewRequest(BaseModel):
    specification: dict
    decisions: dict


class ReleaseRequest(ChangePlanRequest):
    policy: str | None = None
    semantic_reviews: dict = Field(default_factory=dict)
    reviewers: list[str] = Field(default_factory=list)
    specification: dict
    approval: dict | None = None
    acknowledge_model_calls: bool = False
    targeted: bool = False
    max_calls: int = Field(default=40,ge=1,le=400)
    max_seconds: int = Field(default=120,ge=1,le=900)


class GuardHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Same-origin browser API; no CORS. Localhost-only deployment is enforced by CLI.
        origin = request.headers.get('origin')
        if request.method in ('POST','PUT','PATCH','DELETE') and origin:
            from urllib.parse import urlparse
            host = (urlparse(origin).hostname or '').lower()
            if host not in ('localhost','127.0.0.1','::1'):
                return JSONResponse({'detail':'Origin not permitted'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
        )
        return response


def create_app(workspace: str | Path | None = None, *, authenticated: bool | None = None) -> FastAPI:
    project_path = workspace
    app = FastAPI(title='SourceROI', version='0.2.0', docs_url=None, redoc_url=None, openapi_url=None)
    from .security import SecurityStore,IdentityBoundary
    from .config import DEFAULT_WORKSPACE
    project_path=Path(workspace or DEFAULT_WORKSPACE).expanduser().resolve()
    security_folder=project_path/'.sourceroi/security'
    provisioned=security_folder.exists() or security_folder.is_symlink()
    if authenticated is False and provisioned:
        raise ValueError('Cannot downgrade a provisioned workspace to unauthenticated HTTP')
    secured=provisioned if authenticated is None else authenticated
    store=SecurityStore(project_path) if secured else None
    app.state.security=store
    app.add_middleware(GuardHeaders)
    if store:app.add_middleware(IdentityBoundary,store=store)
    from .http_guard import LocalBoundary
    app.add_middleware(LocalBoundary)
    if project_path.is_dir():
        from .workspace_lock import WorkspaceBoundary
        app.add_middleware(WorkspaceBoundary,root=project_path)
    semaphore = threading.BoundedSemaphore(1)
    # Startup never changes another process's jobs. Lease-based recovery is a
    # separate phase; orphaned legacy rows remain visible rather than guessed.
    current = {'run_id':None, 'message':None}

    def cfg():
        try:
            config=read_config(project_path)
            if store:config['_strict_analysis_isolation']=True
            return config
        except (ValueError, FileNotFoundError, KeyError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.get('/api/v2/health')
    def health():
        return {'status':'ok', 'version':'0.2.0', 'service':'SourceROI local beta', 'authenticated':bool(store)}

    @app.get('/api/v2/ready')
    def readiness():
        try:
            config = cfg()
            with db.connect(config) as conn:
                integrity = conn.execute('PRAGMA quick_check').fetchone()[0]
            if integrity != 'ok':
                raise ValueError('Storage integrity check failed')
        except Exception:
            return JSONResponse({'status': 'not_ready', 'detail': 'Check local configuration and storage'}, status_code=503)
        return {'status': 'ready', 'deployment': 'authenticated-single-tenant-read-review' if store else 'single-user-loopback',
                'execution_enabled': not bool(store),
                'native_accounting': 'PENDING',
                'native_accounting_scope': 'Current process unverified; one historical bounded run reconciled', 'production_ready': False}

    @app.get('/api/v2/auth/mode')
    def auth_mode():return {'authenticated':bool(store),'execution_enabled':not bool(store)}

    @app.post('/api/v2/auth/login')
    def login(params: LoginRequest, request: Request):
        if not store:raise HTTPException(404,'Authentication not configured')
        try:session=store.login(params.username,params.password)
        except PermissionError:
            store.audit('login_request',status=401,request_id=request.state.request_id)
            raise HTTPException(401,'Invalid credentials or login temporarily unavailable')
        store.audit('login_request',session['user']['id'],request_id=request.state.request_id)
        response=JSONResponse({'user':session['user'],'csrf':session['csrf'],'expires_at':session['expires_at']})
        # Only literal loopback HTTP is supported. Secure cookies become required
        # with a separately tested HTTPS deployment; no proxy trust is enabled.
        response.set_cookie('sourceroi_session',session['token'],max_age=store.ttl,httponly=True,samesite='strict',path='/')
        return response

    @app.get('/api/v2/auth/session')
    def session(request: Request):
        if not store:raise HTTPException(404,'Authentication not configured')
        actor=request.state.principal
        return {'user':{k:actor[k] for k in ('id','name','role')},'expires_at':actor['expires']}

    @app.post('/api/v2/auth/logout')
    def logout(request: Request):
        if not store:raise HTTPException(404,'Authentication not configured')
        store.logout(request.state.session_token)
        response=JSONResponse({'status':'revoked'});response.delete_cookie('sourceroi_session',path='/');return response

    @app.post('/api/v2/fixture-authorizations',status_code=201)
    def fixture_authorize(params: FixtureAuthorizationRequest,request: Request):
        if not store:raise HTTPException(403,'Authentication required')
        from .durable_jobs import Jobs
        from .fixture_execution import authorize
        return authorize(Jobs(store),request.state.principal,params.specification,max_attempts=params.max_attempts,max_seconds=params.max_seconds)

    @app.post('/api/v2/jobs',status_code=202)
    def durable_submit(params: DurableJobRequest,request: Request):
        if not store:raise HTTPException(403,'Durable jobs require workspace authentication')
        from .durable_jobs import Jobs,JobConflict
        try:
            result=Jobs(store).submit(request.state.principal,request.headers.get('idempotency-key',''),params.specification,params.approval,operation=params.operation,max_seconds=params.max_seconds,fixture_authorization=params.fixture_authorization,fixture_responses=params.fixture_responses,fixture_mode=params.fixture_mode)
        except JobConflict as exc:raise HTTPException(409,str(exc)) from exc
        return {'job':result,'execution_enabled':False}

    @app.get('/api/v2/jobs/{job_id}')
    def durable_get(job_id: str,request: Request):
        if not store:raise HTTPException(403,'Durable jobs require workspace authentication')
        from .durable_jobs import Jobs
        jobs=Jobs(store);result=jobs.get(job_id);actor=request.state.principal
        if not result or result['actor']!=actor['id'] and actor['role']!='admin':raise HTTPException(404,'Job not found')
        return {'job':result,'events':jobs.events(job_id)}

    @app.post('/api/v2/jobs/{job_id}/cancel')
    def durable_cancel(job_id: str,request: Request):
        if not store:raise HTTPException(403,'Durable jobs require workspace authentication')
        from .durable_jobs import Jobs
        jobs=Jobs(store);result=jobs.get(job_id);actor=request.state.principal
        if not result or result['actor']!=actor['id'] and actor['role']!='admin':raise HTTPException(404,'Job not found')
        return {'job':jobs.cancel(job_id,actor)}

    def semantic_access(job_id,request):
        if not store:raise HTTPException(403,'Authentication required')
        from .durable_jobs import Jobs
        from .semantic_store import SemanticStore
        reviews=SemanticStore(Jobs(store));job=reviews.jobs.get(job_id)
        if not job or not reviews.allowed(job,request.state.principal):raise HTTPException(404,'Review assignment not found')
        return reviews

    @app.get('/api/v2/jobs/{job_id}/review-packet')
    def semantic_packet(job_id: str,task_id: str,request: Request):
        return semantic_access(job_id,request).packet(job_id,task_id)

    @app.post('/api/v2/jobs/{job_id}/semantic-reviews',status_code=201)
    def semantic_review(job_id: str,params: SemanticReviewRequest,request: Request):
        reviews=semantic_access(job_id,request)
        return reviews.put(job_id,params.task_id,request.state.principal,**params.model_dump(exclude={'task_id'}))

    @app.get('/api/v2/jobs/{job_id}/assessment')
    def semantic_assessment(job_id: str,request: Request):
        return semantic_access(job_id,request).assess(job_id)

    @app.get('/api/v2/project')
    def project():
        config = cfg()
        return {**public_config(config), **preflight(config),
                'running': {'id':current['run_id'], 'message':current['message']} if current['run_id'] else None}

    @app.get('/api/v2/runs')
    def runs(limit: int = Query(40, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
        return db.list_runs(cfg(), limit, offset=offset)

    @app.get('/api/v2/runs/{run_id}')
    def get_run(run_id: str):
        result = db.get(cfg(), run_id)
        if not result:
            raise HTTPException(404, 'Run not found')
        return result

    @app.post('/api/v2/knowledge/plan')
    def knowledge_plan(params: ChangePlanRequest, request: Request):
        from .assurance import propose,save_proposal
        config=cfg()
        path=secure_path(Path(config['_root']),'.sourceroi/snapshots/'+params.snapshot_id)
        if not (path/'project.json').is_file():raise HTTPException(404,'Frozen snapshot not found')
        result=propose(read_config(path),config,intent=params.intent)
        save_proposal(config,result)
        if store:store.register_plan(result,params.snapshot_id)
        return result

    @app.post('/api/v2/knowledge/decisions')
    def knowledge_decision(params: DecisionRequest):
        from .knowledge_decision import run as decide
        config=cfg()
        path=secure_path(Path(config['_root']),'.sourceroi/snapshots/'+params.snapshot_id)
        if not (path/'project.json').is_file():raise HTTPException(404,'Frozen snapshot not found')
        if not semaphore.acquire(blocking=False):raise HTTPException(409,'Another workspace evaluation is active')
        try:return decide(read_config(path),config,params)
        finally:semaphore.release()

    @app.post('/api/v2/knowledge/review')
    def knowledge_review(params: ChangeReviewRequest, request: Request):
        from .assurance import review,save_review
        decisions=dict(params.decisions)
        if store:
            from .assurance import validate_release_inputs
            actor=request.state.principal
            if decisions.get('reviewer') not in (None,actor['name']):raise HTTPException(403,'Reviewer must match authenticated identity')
            snapshot=store.registered_plan(params.specification)
            config=cfg();path=secure_path(Path(config['_root']),'.sourceroi/snapshots/'+snapshot)
            validate_release_inputs(read_config(path),config,params.specification)
            decisions['reviewer']=actor['name']
        try:result=review(params.specification,**decisions)
        except TypeError as exc:raise HTTPException(400,'Unsupported review decision fields') from exc
        if store:result=store.bind_approval(result,request.state.principal)
        save_review(cfg(),params.specification,result);return result

    @app.get('/api/v2/knowledge/releases/{run_id}/export')
    def knowledge_export(run_id: str, format: str = 'json'):
        import json
        from fastapi.responses import Response
        from .assurance import markdown
        row=db.get(cfg(),run_id)
        if not row or not row.get('report') or row['report'].get('kind')!='knowledge_release':
            raise HTTPException(404,'Knowledge release not found')
        if format not in ('json','markdown'):raise HTTPException(400,'Use json or markdown')
        body=json.dumps(row['report'],indent=2) if format=='json' else markdown(row['report'])
        return Response(body,media_type='application/json' if format=='json' else 'text/markdown')

    @app.get('/api/v2/knowledge/timeline')
    def knowledge_timeline():
        from .assurance import timeline
        return timeline(cfg())

    @app.post('/api/v2/knowledge/release')
    def knowledge_release(params: ReleaseRequest):
        from .assurance import execute
        if not params.acknowledge_model_calls:raise HTTPException(400,'Acknowledge local inference')
        if not semaphore.acquire(blocking=False):raise HTTPException(409,'An evaluation is already running')
        try:
            config=cfg()
            path=secure_path(Path(config['_root']),'.sourceroi/snapshots/'+params.snapshot_id)
            if not (path/'project.json').is_file():raise HTTPException(404,'Frozen snapshot not found')
            return execute(read_config(path),config,
                           params.specification,approval=params.approval,max_calls=params.max_calls,
                           max_seconds=params.max_seconds,targeted=params.targeted,policy=params.policy,semantic_reviews=params.semantic_reviews,reviewers=params.reviewers)
        finally:semaphore.release()

    @app.get('/api/v2/compare')
    def compare(before: str, after: str):
        config = cfg()
        return compare_runs(db.get(config, before), db.get(config, after))

    @app.get('/api/v2/optimize')
    def optimize_info():
        return {'detail': 'Use POST with acknowledge_model_calls=true to run optimization.'}

    @app.post('/api/v2/optimize')
    def optimize_job(params: OptimizationRequest):
        if not params.acknowledge_model_calls:
            raise HTTPException(400, 'Confirm model/API charges before optimization')
        config = cfg()
        if not semaphore.acquire(blocking=False):
            raise HTTPException(409, 'An evaluation is already running')
        rid = None
        try:
            rid = db.begin(config, 'optimization_validation', [])
            from .validation import optimize
            report = optimize(config, quality_floor=params.quality_floor,
                              min_citation_rate=params.min_citation_rate,
                              objective=params.objective, max_candidates=params.max_candidates,
                              repeats=params.repeats, max_accuracy_drop=params.max_accuracy_drop,
                              max_regressions=params.max_regressions)
            db.finish(config, rid, report)
            return {'id': rid, 'report': report}
        except Exception as exc:
            if rid:
                db.finish(config, rid, None, type(exc).__name__)
            raise
        finally:
            semaphore.release()

    @app.post('/api/v2/data-ci/freeze')
    def freeze_data():
        import uuid
        from .data_ci import freeze
        config=cfg()
        if not semaphore.acquire(blocking=False):
            raise HTTPException(409,'An evaluation is already running')
        try:
            identifier=uuid.uuid4().hex
            path=Path(config['_root'])/'.sourceroi'/'snapshots'/identifier
            result=freeze(config,path)
            return {'snapshot_id':identifier,**result}
        finally:
            semaphore.release()

    @app.post('/api/v2/data-ci')
    def execute_data_ci(params: DataCIRequest):
        if not params.acknowledge_model_calls:
            raise HTTPException(400,'Acknowledge local model execution')
        from .data_ci import run_data_ci
        from .validation import Budget
        config=cfg();path=Path(config['_root'])/'.sourceroi'/'snapshots'/params.snapshot_id
        if not path.is_dir():raise HTTPException(404,'Frozen snapshot not found')
        if not semaphore.acquire(blocking=False):raise HTTPException(409,'An evaluation is already running')
        try:
            current.update(run_id='data-ci',message='Comparing frozen and current sources')
            budget=Budget({**config['settings'],'max_run_seconds':params.max_seconds})
            report=run_data_ci(read_config(path),config,max_tasks=params.max_tasks,
                max_regressions=params.max_regressions,max_accuracy_drop=params.max_accuracy_drop,
                max_evidence_drop=params.max_evidence_drop,affected_only=params.affected_only,
                repair=params.repair,budget=budget)
            return {'id':report['run_id'],'report':report}
        finally:
            current.update(run_id=None,message=None);semaphore.release()

    @app.post('/api/v2/reliability-studies')
    def evidence_study(params: ReliabilityRequest):
        if not params.acknowledge_model_calls:raise HTTPException(400,'Acknowledge local model execution')
        from .reliability_study import run_reliability_study
        from .policies import validate_policy
        from .validation import Budget
        config=cfg();validate_policy(params.previous_policy)
        if config['model'].get('context_tokenizer')!='llama_cpp':raise HTTPException(400,'Configure the approved local tokenizer')
        if not semaphore.acquire(blocking=False):raise HTTPException(409,'An evaluation is already running')
        try:
            def update(event):current.update(run_id='evidence-study',message=f"{event['partition']}: {event['calls']} generation calls")
            budget=Budget({**config['settings'],'max_model_calls_per_run':min(params.max_calls,config['settings'].get('max_model_calls_per_run',100)),'max_run_seconds':params.max_seconds})
            report=run_reliability_study(config,params.previous_policy,budget=budget,notify=update)
            return {'id':report['run_id'],'report':report}
        finally:
            current.update(run_id=None,message=None);semaphore.release()

    @app.post('/api/v2/studies')
    def policy_study(params: StudyRequest):
        if not params.acknowledge_model_calls:
            raise HTTPException(400, 'Acknowledge configured model execution')
        config = cfg()
        if not semaphore.acquire(blocking=False):
            raise HTTPException(409, 'An evaluation is already running')
        try:
            from .study import run_study
            def update_study(progress):
                current.update(run_id=progress['run_id'], message=f"{progress['event']}: {progress['calls']}/{progress['max_calls']} calls")
            report = run_study(config, objective=params.objective, quality_floor=params.quality_floor,
                               min_groundedness=params.min_groundedness, repeats=params.repeats,
                               reviews=params.reviews, approved_spend_usd=params.approved_spend_usd, notify=update_study)
            return {'id': report['run_id'], 'report': report}
        finally:
            current.update(run_id=None, message=None)
            semaphore.release()

    @app.get('/api/v2/studies/{run_id}/export')
    def export_policy_study(run_id: str, format: str = 'json'):
        import tempfile
        from fastapi.responses import Response
        from .study import export_study
        row = db.get(cfg(), run_id)
        if not row or not row.get('report') or row['report'].get('kind') != 'standalone_policy_study':
            raise HTTPException(404, 'Study not found')
        if row['report']['status'] != 'completed':
            raise HTTPException(409, 'Study is incomplete')
        suffix = {'json': '.json', 'csv': '.csv', 'markdown': '.md', 'review': '.review.json'}.get(format)
        if suffix is None:
            raise HTTPException(400, 'Format must be json, csv, markdown, or review')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)/'study.json'
            export_study(row['report'], base)
            content = base.with_suffix(suffix).read_text()
        return Response(content, media_type={'json': 'application/json', 'csv': 'text/csv',
                                            'markdown': 'text/markdown', 'review': 'application/json'}[format],
                        headers={'Content-Disposition': 'attachment; filename="study'+suffix+'"'})

    @app.post('/api/v2/runs', status_code=202)
    def start_run(params: RunRequest):
        config = cfg()
        if not params.acknowledge_model_calls:
            raise HTTPException(400,'Confirm model/API calls and possible provider charges before starting')
        if params.mode not in ('baseline','ablation','document_ablation'):
            raise HTTPException(400, 'mode must be baseline, ablation, or document_ablation')
        known = {s['id'] for s in config['sources']}
        if not set(params.exclude_sources).issubset(known):
            raise HTTPException(400, 'Unknown excluded source ID')
        available_documents = {d['id'] for d in preflight(config)['documents']}
        if not set(params.exclude_documents+params.document_ids).issubset(available_documents):
            raise HTTPException(400,'Unknown document ID')
        if params.mode == 'document_ablation':
            max_docs = int(config.get('settings',{}).get('max_documents_per_study',8))
            if not 1 <= len(params.document_ids) <= max_docs:
                raise HTTPException(400, f'Select 1..{max_docs} documents')
        tasks = load_benchmark(config)
        max_tasks = min(len(tasks), int(config.get('settings',{}).get('max_tasks_per_run', 50)),
                        params.max_tasks or len(tasks))
        variants = 1+len(known) if params.mode=='ablation' else (1+len(params.document_ids) if params.mode=='document_ablation' else 1)
        if not max_tasks:
            raise HTTPException(400, 'Provide benchmark tasks before running')
        calls = max_tasks * variants
        if calls > int(config.get('settings',{}).get('max_model_calls_per_run', 100)):
            raise HTTPException(400, f'{calls} calls would exceed configured limit. Reduce max_tasks.')
        if params.mode in ('ablation','document_ablation') and (params.exclude_sources or params.exclude_documents):
            raise HTTPException(400, 'Ablation studies start from all documents and sources')
        if not semaphore.acquire(blocking=False):
            raise HTTPException(409, 'An evaluation is already running')
        try:
            run_id = db.begin(config, params.mode, params.exclude_sources)
        except Exception:
            semaphore.release()
            raise
        current['run_id'] = run_id
        current['message'] = 'Starting evaluation'

        def job():
            try:
                def update(msg): current['message'] = msg
                report = run(config, exclude_sources=params.exclude_sources, exclude_documents=params.exclude_documents,
                             document_ids=params.document_ids, mode=params.mode, max_tasks=params.max_tasks, notify=update)
                db.finish(config, run_id, report)
            except Exception as exc:
                db.finish(config, run_id, None, type(exc).__name__)
            finally:
                current['run_id'] = None
                current['message'] = None
                semaphore.release()
        # Acquire before returning the HTTP response so a background legacy run
        # cannot outlive the request's quiescence protection.
        from .workspace_lock import workspace_lock
        job_lock=workspace_lock(config['_root']);job_lock.__enter__()
        def locked_job():
            try:job()
            finally:job_lock.__exit__(None,None,None)
        try:threading.Thread(target=locked_job, daemon=True, name=f'sourceroi-{run_id}').start()
        except BaseException:
            job_lock.__exit__(None,None,None);semaphore.release();raise
        return {'id':run_id, 'status':'running', 'planned_model_calls':calls}

    @app.get('/')
    def index():
        return FileResponse(WEB/'index.html')

    @app.get('/app.js')
    def js():
        return FileResponse(WEB/'app.js', media_type='application/javascript')

    @app.get('/styles.css')
    def css():
        return FileResponse(WEB/'styles.css', media_type='text/css')

    return app
