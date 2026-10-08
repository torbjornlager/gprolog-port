"""Raw HTTP request-line regressions; no Prolog worker is needed."""
import http.client
import json
import os
import select
import socket
import subprocess


node = subprocess.Popen(
    [os.environ.get('ISO_NODE', './isobase-node'), '--auth', 'open', '--port', '0'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def request(line, fragmented=False):
    with socket.create_connection(('127.0.0.1', port), timeout=4) as sock:
        headers = f'\r\nHost: localhost:{port}\r\n\r\n'.encode()
        if fragmented:
            sock.sendall(line)
            sock.sendall(headers)
        else:
            sock.sendall(line + headers)
        response = http.client.HTTPResponse(sock)
        response.begin()
        return response.status, json.loads(response.read())


try:
    assert select.select([node.stdout], [], [], 5)[0], 'node startup timed out'
    port = json.loads(node.stdout.readline())['port']
    checked = 0
    # Test each non-NUL control in method, target and version. NUL is already
    # rejected by the byte reader and has its own diagnostic.
    for value in [*range(1, 32), 127]:
        control = bytes([value])
        for line in (
            b'G' + control + b'ET /missing HTTP/1.1',
            b'GET /call?goal=' + control + b'true HTTP/1.1',
            b'GET /missing HTTP/1.' + control + b'1',
        ):
            result = request(line, fragmented=bool(value % 2))
            assert result == (400, {'type': 'error', 'data': 'invalid_request'}), (line, result)
            checked += 1
    assert request(b'GET /call?goal=\x00true HTTP/1.1') == (
        400, {'type': 'error', 'data': 'invalid_headers'})
    token_bytes = b"!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    malformed_methods = 0
    for value in range(33, 256):
        if value in token_bytes:
            continue
        line = b'G' + bytes([value]) + b'ET /missing HTTP/1.1'
        assert request(line) == (400, {'type': 'error', 'data': 'invalid_request'}), line
        malformed_methods += 1
    for line in (b' /missing HTTP/1.1', b'GET  HTTP/1.1', b' GET /missing HTTP/1.1'):
        assert request(line) == (400, {'type': 'error', 'data': 'invalid_request'}), line
    for target in (b'/call#', b'/call#?goal=true', b'/call?goal=true#',
                   b'/call?goal=X%3D%27#%27', b'/missing#fragment'):
        for version in (b'HTTP/1.0', b'HTTP/1.1'):
            line = b'GET ' + target + b' ' + version
            assert request(line) == (400, {'type': 'error', 'data': 'invalid_request_target'}), line
    # A syntactically valid but unsupported method keeps its existing 405.
    for method in (b'POST', b'OPTIONS', b'get', b'CUSTOM-METHOD'):
        assert request(method + b' /missing HTTP/1.1')[0] == 405
    # Percent escapes remain valid URI text; these cases stop at routing,
    # allowing the test to run without an installed GNU Prolog runtime.
    for version in (b'HTTP/1.0', b'HTTP/1.1'):
        for target in (b'/missing', b'/missing?goal=%09true', b'/missing?goal=%0Atrue',
                       b'/missing?goal=%23'):
            assert request(b'GET ' + target + b' ' + version)[0] == 404
    print(f'PASS request line: {checked} controls, {malformed_methods} invalid method bytes, empty fields, fragments and valid routing')
finally:
    node.terminate()
    try:
        node.wait(timeout=5)
    except subprocess.TimeoutExpired:
        node.kill()
        node.wait()
        raise
    assert node.returncode == 0, (node.returncode, node.stderr.read())
    assert not node.stderr.read()
