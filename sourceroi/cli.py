"""Dual entrypoint: live v0.2, or the preserved offline demo."""
from __future__ import annotations
import sys

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0]=='demo':
        from .demo_cli import main as demo_main
        return demo_main(argv[1:])
    from .live.cli import main as live_main
    return live_main(argv)

if __name__=='__main__':
    raise SystemExit(main())
