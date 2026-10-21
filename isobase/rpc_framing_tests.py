"""GNU RPC/promise request framing; optional live native peers, no engine changes."""
import argparse
import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
import urllib.parse
from outbound_test_policy import allow

ROOT = Path(__file__).resolve().parent


def atom(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "''") + "'"


def expect(worker, goal):
    result = subprocess.run([worker, f'query(({goal}),ok)', '100'], cwd=ROOT,
                            input='', capture_output=True, text=True, timeout=10)
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    expected = [{'type': 'success', 'answers': ['ok'], 'more': False}]
    assert result.returncode == 0 and actual == expected, (goal, result.returncode, actual, result.stderr)


class Capture(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests.append(urllib.parse.parse_qs(
            urllib.parse.urlsplit(self.path).query, keep_blank_values=True))
        body = b'failure.\n'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def wire_checks(worker):
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Capture)
    server.daemon_threads = True
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    peer = f'http://127.0.0.1:{server.server_port}'
    allow(peer)
    cases = [
        ('rpc', 'X=ok', None, '(V0=ok)', '(v(V0))'),
        ('rpc', '(X=a,Y=b)', None, '(V0=a,V1=b)', '(v(V0,V1))'),
        ('promise', 'X=ok', 'X-X', '(V0=ok)', '(V0-V0)'),
        ('promise', '(X=a;X=b)', 'X-X', '(V0=a;V0=b)', '(V0-V0)'),
        ('promise', '(X=a,Y=b)', 'X-Y', '(V0=a,V1=b)', '(V0-V1)'),
        ('promise', 'true', 'pair(X,Y)', '(true)', '(pair(V0,V1))'),
    ]
    try:
        for kind, goal, template, wire_goal, wire_template in cases:
            if kind == 'rpc':
                query = f'(rpc({atom(peer)},{goal},[once(true)])->fail;true)'
            else:
                query = f'promise({atom(peer)},{goal},R,[template({template})]),yield(R,Reply),Reply==failure'
            before = len(server.requests)
            expect(worker, query)
            assert len(server.requests) == before+1, server.requests
            request = server.requests[-1]
            assert request['goal'] == [wire_goal], request
            assert request['template'] == [wire_template], request
            assert request['src_text'] == [''], request
        print(f'PASS {len(cases)} captured wire framing/sharing assertions', flush=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def live_checks(worker, peer):
    allow(peer)
    uri = atom(peer)
    quoted = atom("it's +,; (λ) \\ end")
    cases = [
        f'rpc({uri},X=ok),X==ok',
        f'rpc({uri},(X=a,Y=b)),X==a,Y==b',
        f'findall(X,rpc({uri},(X=a;X=b),[limit(1)]),Xs),Xs==[a,b]',
        f'rpc({uri},X={quoted}),X=={quoted}',
        f'promise({uri},X=ok,R,[template(X-X),limit(1)]),var(X),'
        'yield(R,Reply),Reply=success([ok-ok],false),var(X)',
        f'promise({uri},(X=a,Y=b),R,[template(X-Y)]),var(X),var(Y),'
        'yield(R,Reply),Reply=success([a-b],false),var(X),var(Y)',
        f'promise({uri},(X=a;X=b),R,[template(X),limit(1)]),'
        'yield(R,Reply),Reply=success([a],true),var(X)',
        f'promise({uri},(X=a;X=b),R,[template(X),limit(1),once(true)]),'
        'yield(R,Reply),Reply=success([a],false),var(X)',
        f'promise({uri},X={quoted},R,[template(X)]),'
        f'yield(R,Reply),Reply=success([Answer],false),Answer=={quoted},var(X)',
        f'promise({uri},X=pair(A,A),R,[template(X)]),'
        'yield(R,Reply),Reply=success([pair(P,Q)],false),var(P),P==Q,var(X),var(A)',
        f'promise({uri},X=pair(A,B),R,[template(X)]),'
        'yield(R,Reply),Reply=success([pair(P,Q)],false),var(P),var(Q),P\\==Q,var(X),var(A),var(B)',
        f'promise({uri},(true->X=ok;X=wrong),R,[template(X)]),yield(R,Reply),Reply=success([ok],false),var(X)',
    ]
    for goal in cases:
        expect(worker, goal)
    print(f'PASS {len(cases)} live RPC/promise precedence, sharing, quoting and paging assertions: {peer}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', default=os.environ.get('ISO_WORKER', str(ROOT/'query-worker')))
    parser.add_argument('--peer', action='append', default=[])
    args = parser.parse_args()
    wire_checks(str(Path(args.worker).resolve()))
    for peer in args.peer:
        live_checks(str(Path(args.worker).resolve()), peer)


if __name__ == '__main__':
    main()
