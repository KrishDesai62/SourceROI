"""Local runtime supervisor: parent death/deadline always retires its child group."""
import argparse
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--spec',required=True);parser.add_argument('--parent-fd',type=int,required=True)
    args=parser.parse_args();spec=json.loads(Path(args.spec).read_text());root=Path(spec['output']);started=time.monotonic();child=None;reason='startup_failure';code=None
    def stop(*_):raise InterruptedError('Supervisor interrupted')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        with (root/'server.log').open('xb') as log:
            # The owner creates the supervisor's private session. Keeping the
            # known fixture child in that group lets the owner retire it even
            # if the supervisor itself is killed before writing its PID record.
            child=subprocess.Popen(spec['command'],stdout=log,stderr=subprocess.STDOUT,close_fds=True,env={**{k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_','SOURCEROI_NATIVE_','AIP_','DYLD_','LD_','GGML_','HF_','HUGGINGFACE_'))},**spec.get('environment',{})})
            with (root/'runtime-start.json').open('x') as f:
                json.dump({'run_id':spec['run_id'],'runtime_pid':child.pid,'supervisor_pid':os.getpid()},f);f.flush();os.fsync(f.fileno())
            while True:
                code=child.poll()
                if code is not None:reason='runtime_exited';break
                if time.monotonic()-started>=spec['max_seconds']:reason='deadline';break
                ready,_,_=select.select([args.parent_fd],[],[],.05)
                if ready:
                    message=os.read(args.parent_fd,64)
                    reason='cancelled' if message.startswith(b'cancel') else 'owner_shutdown' if message.startswith(b'stop') else 'owner_disappeared'
                    break
    except BaseException as exc:
        reason='supervisor_'+type(exc).__name__
    finally:
        if child is not None and child.poll() is None:
            try:child.send_signal(signal.SIGKILL if reason in ('deadline','cancelled','owner_disappeared') else signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:child.kill()
                except ProcessLookupError:pass
                child.wait(timeout=2)
        if child is not None:code=child.returncode
        record={'run_id':spec['run_id'],'reason':reason,'runtime_returncode':code,'elapsed_seconds':time.monotonic()-started}
        with (root/'worker-exit.json').open('x') as f:json.dump(record,f,indent=2);f.flush();os.fsync(f.fileno())
        shutil.rmtree(spec['private_dir'],ignore_errors=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
