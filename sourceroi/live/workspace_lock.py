"""Cooperative POSIX workspace quiescence. Trusted external writers must stop."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

@contextmanager
def workspace_lock(root,*,exclusive=False):
    from .config import secure_path
    root=Path(root).expanduser().resolve()
    folder=secure_path(root,'.sourceroi',must_exist=False);folder.mkdir(exist_ok=True)
    path=folder/'workspace.lock'
    if path.is_symlink():raise ValueError('Workspace lock symlinks forbidden')
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        if os.fstat(fd).st_nlink!=1:raise ValueError('Workspace lock hardlinks forbidden')
        try:fcntl.flock(fd,(fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Workspace busy: quiesce service/CLI/workers before backup or retry later')
        yield
    finally:os.close(fd)

class WorkspaceBoundary:
    def __init__(self,app,root):self.app=app;self.root=root
    async def __call__(self,scope,receive,send):
        from starlette.responses import JSONResponse
        if scope['type']!='http':return await self.app(scope,receive,send)
        try:
            with workspace_lock(self.root):return await self.app(scope,receive,send)
        except ValueError as exc:
            if 'Workspace busy:' not in str(exc):raise
            return await JSONResponse({'detail':'Workspace quiesced for maintenance'},503)(scope,receive,send)
