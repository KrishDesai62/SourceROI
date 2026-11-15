"""Additional opt-in native path; legacy native and arbitrary fixture gates stay shut."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CERTIFICATE=ROOT/'workspace/execution-resolution/native-certificate.json'


def validate(certificate,authorization,calls,seconds):
    if Path(certificate).resolve()!=CERTIFICATE.resolve():raise ValueError('Use the verified local native certificate, not an arbitrary runtime')
    cert=json.loads(CERTIFICATE.read_text())
    if cert.get('kind')!='sourceroi_instrumented_b12345' or cert.get('protocol_gate')!='VERIFIED':raise ValueError('Native instrumentation protocol gate incomplete')
    required={cert.get('binary'),cert.get('model'),str(ROOT/'sourceroi/live/native/accounting.h'),str(ROOT/'sourceroi/live/native_accounting.py')}
    if None in required or not required<=set(cert.get('files',{})):raise ValueError('Native certificate lacks binary/model/accounting file bindings')
    for name,value in cert['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=value:raise ValueError('Native build/instrumentation changed; reverify before inference')
    auth=json.loads(Path(authorization).read_text()) if authorization else {}
    if auth.get('status')!='approved' or not auth.get('authorization_basis') or auth.get('scope') not in ('accounting_smoke','benchmark'):
        raise ValueError('Explicit recorded inference authorization required')
    if auth.get('retries')!=0 or auth.get('external_spend_usd')!=0 or type(auth.get('max_attempts')) is not int or type(auth.get('max_seconds')) not in (int,float):raise ValueError('Authorization must bound attempts/runtime, disallow retries and external spending')
    if not math.isfinite(auth['max_seconds']) or auth['max_seconds']<=0 or auth['max_attempts']<=0:raise ValueError('Finite positive authorization limits required')
    if auth['scope']=='accounting_smoke' and (auth['max_attempts']>2 or auth['max_seconds']>30):raise ValueError('Recorded smoke budget cannot exceed existing authorization')
    if calls>auth['max_attempts'] or seconds>auth['max_seconds']:raise ValueError('Requested experiment exceeds authorization')
    if auth['scope']=='accounting_smoke' and (calls>2 or seconds>30):raise ValueError('Accounting smoke authorization is only two calls / 30 seconds')
    if auth['scope']=='benchmark' and cert.get('native_smoke')!='RECONCILED':raise ValueError('Native smoke must reconcile before benchmark authorization is usable')
    return {**cert,'authorization':auth}


def begin(native,run_id):
    """A recorded authorization is single-use, including interrupted startup."""
    import fcntl
    import os
    import re
    import time
    auth=native['authorization'];ident=auth.get('authorization_id','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',ident):raise ValueError('Stable authorization_id required')
    if auth['scope']=='accounting_smoke' and ident!='existing-two-call-accounting-smoke':raise ValueError('Existing smoke authorization cannot be reissued under another ID')
    root=ROOT/'workspace/execution-resolution/authorization-ledgers';root.mkdir(parents=True,exist_ok=True)
    path=root/(ident+'.json')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        row={'authorization':auth,'run_id':run_id,'started_monotonic':time.monotonic(),'attempts':[],'state':'active'}
        with path.open('x') as file:json.dump(row,file,indent=2);file.flush();os.fsync(file.fileno())
    return str(path)


def reserve(path,run_id,request_id):
    import fcntl
    import os
    import time
    path=Path(path)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        row=json.loads(path.read_text());elapsed=time.monotonic()-row['started_monotonic'];auth=row['authorization']
        if row['state']!='active' or row['run_id']!=run_id or not 0<=elapsed<auth['max_seconds'] or len(row['attempts'])>=auth['max_attempts']:
            raise ValueError('Single-use authorization exhausted, closed or expired; no dispatch')
        if request_id in row['attempts']:raise ValueError('Authorization request identity replay')
        row['attempts'].append(request_id)
        # A crash during this conservative write invalidates the ledger; never resume it.
        with path.open('w') as file:json.dump(row,file,indent=2);file.flush();os.fsync(file.fileno())


def finish(path):
    import fcntl
    import os
    import time
    path=Path(path)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        row=json.loads(path.read_text());row['state']='closed';row['elapsed_seconds']=time.monotonic()-row['started_monotonic']
        with path.open('w') as file:json.dump(row,file,indent=2);file.flush();os.fsync(file.fileno())
    return row
