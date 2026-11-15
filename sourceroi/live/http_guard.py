"""Browser boundary for a single-user loopback service, not user authentication."""
import asyncio
from urllib.parse import urlsplit
import uuid
from starlette.responses import JSONResponse

MAX_BODY = 1024 * 1024
LOOPBACK = {'localhost', '127.0.0.1', '::1'}


def validate_browser_request(host, origin=None, *, scheme='http', testing=False):
    try:
        target = urlsplit(f'{scheme}://{host}')
        if target.username or target.password or target.path or target.query or target.fragment:
            return False
        if target.hostname not in LOOPBACK and not (testing and target.hostname == 'testserver'):
            return False
        port = target.port or (443 if scheme == 'https' else 80)
        if origin:
            source = urlsplit(origin)
            return (source.scheme == scheme and source.hostname == target.hostname
                    and (source.port or (443 if source.scheme == 'https' else 80)) == port
                    and not source.username and not source.password
                    and not source.path and not source.query and not source.fragment)
        return True
    except ValueError:
        return False


class LocalBoundary:
    """Bound streamed bodies before JSON parsing; distrust proxy and Host headers."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = {}
        for name, value in scope.get('headers', []):
            name = name.lower()
            if name in headers and name in (b'host', b'content-length', b'origin'):
                return await JSONResponse({'detail': 'Duplicate boundary header'}, 400)(scope, receive, send)
            headers[name] = value.decode('latin1')
        testing = (scope.get('client') or ('',))[0] == 'testclient'
        if not validate_browser_request(headers.get(b'host', ''), headers.get(b'origin'),
                                        scheme=scope.get('scheme', 'http'), testing=testing):
            return await JSONResponse({'detail': 'Host or Origin not permitted'}, 403)(scope, receive, send)
        if headers.get(b'sec-fetch-site') == 'cross-site':
            return await JSONResponse({'detail': 'Cross-site request not permitted'}, 403)(scope, receive, send)
        try:
            length = int(headers.get(b'content-length', '0'))
            if length < 0: raise ValueError()
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length'}, 400)(scope, receive, send)
        if length > MAX_BODY:
            return await JSONResponse({'detail': 'Request exceeds 1 MiB'}, 413)(scope, receive, send)
        body = bytearray()
        deadline = asyncio.get_running_loop().time() + 15
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=max(.001, deadline - asyncio.get_running_loop().time()))
            except asyncio.TimeoutError:
                return await JSONResponse({'detail': 'Request body timeout'}, 408)(scope, receive, send)
            if message['type'] == 'http.disconnect': return
            body.extend(message.get('body', b''))
            if len(body) > MAX_BODY:
                return await JSONResponse({'detail': 'Request exceeds 1 MiB'}, 413)(scope, receive, send)
            if not message.get('more_body'): break
        if body and scope['method'] in ('POST', 'PUT', 'PATCH') and headers.get(b'content-type', '').split(';')[0].strip() != 'application/json':
            return await JSONResponse({'detail': 'Use application/json'}, 415)(scope, receive, send)
        request_id = uuid.uuid4().hex
        scope.setdefault('state', {})['request_id'] = request_id
        consumed = False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        async def correlated(message):
            if message['type'] == 'http.response.start':
                message.setdefault('headers', []).append((b'x-request-id', request_id.encode()))
            await send(message)
        await self.app(scope, replay, correlated)
