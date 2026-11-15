"""Bounded local OS capability probe; observations are not guarantees."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.parser_boundary import supervise

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
code='''import resource,json
from pathlib import Path
result={}
try:
 resource.setrlimit(resource.RLIMIT_AS,(128*1024*1024,128*1024*1024))
 result['setrlimit']='accepted'
 try:
  block=bytearray(256*1024*1024)
  result['oversize_allocation']='succeeded'
 except MemoryError:result['oversize_allocation']='MemoryError'
except (ValueError,OSError) as exc:result['setrlimit']='unavailable';result['error']=type(exc).__name__+': '+str(exc)
Path('result.json').write_text(json.dumps(result))
'''
with tempfile.TemporaryDirectory() as directory:
    try:
        supervise([sys.executable,'-c',code],Path(directory),sandbox=True,wall=5)
        observation=json.loads((Path(directory)/'result.json').read_text())
    except Exception as exc:observation={'status':'probe_failed','error_type':type(exc).__name__,'detail':str(exc)}
hardware=subprocess.run(['/usr/sbin/sysctl','-n','hw.model','hw.memsize'],capture_output=True,text=True,timeout=3)
result={'platform':platform.platform(),'python':platform.python_version(),'hardware':hardware.stdout.splitlines(),
        'address_space_probe':observation,'hard_memory_guarantee':'PENDING; one allocation probe cannot certify all Mach/allocator paths',
        'crypto_library':'cryptography not present in verified Python closure; no new dependency downloaded','system_openssl':'LibreSSL 3.3.6 inspected; no reviewed encryption wrapper implemented','real_model_generations':0}
with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,indent=2))
