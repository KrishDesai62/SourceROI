"""Keep regression fixtures from reaching the real local inference runtime.

Fake provider fixtures bind ephemeral ports. The approved interactive llama.cpp
endpoint must never be used implicitly by a test, even if it is already running.
"""
import socket
import pytest


@pytest.fixture(autouse=True)
def isolate_live_model_endpoint(monkeypatch):
    connect=socket.socket.connect
    def guarded(sock,address):
        if isinstance(address,tuple) and len(address)>1 and address[1]==8788 and address[0] in ('127.0.0.1','localhost','::1'):
            raise OSError('Live inference endpoint blocked by regression-test isolation')
        return connect(sock,address)
    monkeypatch.setattr(socket.socket,'connect',guarded)


@pytest.fixture(scope='session',autouse=True)
def no_concurrent_owned_model_runtime():
    from sourceroi.live.experiment import runtime_lease
    with runtime_lease():
        yield
