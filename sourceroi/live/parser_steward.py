"""Trusted process steward: kill the group on parent loss or deadline.

Never parses customer documents. Configuration is written by the supervisor,
not accepted through a document or HTTP job payload.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def main():
    spec=json.loads(Path('steward-spec.json').read_text());child=None;started=time.monotonic()
    try:
        child=subprocess.Popen(spec['command'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)
        while child.poll() is None:
            if os.getppid()!=spec['parent'] or time.monotonic()-started>spec['wall']+.1:
                child.kill();child.wait(timeout=3)
                os.killpg(os.getpgrp(),signal.SIGKILL)
            time.sleep(.02)
        raise SystemExit(child.wait())
    finally:
        if child and child.poll() is None:child.kill();child.wait()

if __name__=='__main__':main()
