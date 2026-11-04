"""Strict RPC/promise Boolean options; use --worker for an isolated build."""
import argparse
import http.server
import json
from pathlib import Path
import subprocess
import threading
import urllib.parse
from outbound_test_policy import allow

ROOT = Path(__file__).resolve().parent

class Peer(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        fields = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        self.server.requests.append(fields)
        once = fields['once'][0] == 'true'
        offset = int(fields['offset'][0])
        value = 'ok' if offset == 0 else 'done'
        answer = f'pair({value},{value})' if 'pair' in fields['template'][0] else f'v({value})'
        more = 'true' if offset == 0 and not once else 'false'
        body = f'success([{answer}],{more}).\n'.encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(worker):
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Peer)
    server.daemon_threads = True
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    uri = f"'http://127.0.0.1:{server.server_port}'"
    allow(uri[1:-1])
    count = 0

    def expect(goal):
        nonlocal count
        p = subprocess.run([worker, f'query(({goal}),ok)', '100'], cwd=ROOT,
                           input='', capture_output=True, text=True, timeout=10)
        data = [json.loads(line) for line in p.stdout.splitlines()]
        assert p.returncode == 0 and data == [{'type': 'success', 'answers': ['ok'], 'more': False}], (goal, p.returncode, data, p.stderr)
        count += 1

    try:
        for value in ['1', '0', '-1', '1.0', '"true"', '"false"', "'TRUE'", '[t,r,u,e]', '@(true)']:
            for kind in ['rpc', 'promise']:
                for options in [f'[once({value})]', f'[once(false),once({value})]']:
                    goal = f'rpc({uri},true,{options})' if kind == 'rpc' else f'promise({uri},true,_,{options})'
                    before = len(server.requests)
                    expect(f'catch(({goal},fail),error(Formal,_),(Formal=type_error(atom,_);Formal=domain_error(boolean,_)))')
                    assert len(server.requests) == before, goal
        for kind in ['rpc', 'promise']:
            goal = f'rpc({uri},true,[once(B)])' if kind == 'rpc' else f'promise({uri},true,_,[once(B)])'
            before = len(server.requests)
            expect(f'catch(({goal},fail),error(instantiation_error,_),true),var(B)')
            assert len(server.requests) == before
        expect(f'findall(X,rpc({uri},X=ok,[once(true),once(false),limit(1)]),Xs),Xs==[ok]')
        expect(f'findall(X,rpc({uri},X=ok,[once(false),once(true),limit(1)]),Xs),Xs==[ok,done]')
        expect(f'promise({uri},X=ok,R,[once(true),template(pair(X,X))]),yield(R,A),A==success([pair(ok,ok)],false),var(X)')
        for kind in ['rpc','promise']:
            for options,formal in [('[limit(1),limit(0)]','type_error(positive_integer,0)'),
                    ('[limit(1),limit(bad)]','type_error(integer,bad)'),
                    ('[timeout(1),timeout(bad)]','type_error(number,bad)'),
                    ('[http_timeout(1),http_timeout(bad)]','type_error(number,bad)'),
                    ("[src_uri('http://127.0.0.1:1/source'),limit(0)]",'type_error(positive_integer,0)')]:
                goal=f'rpc({uri},true,{options})' if kind=='rpc' else f'promise({uri},true,R,{options})'
                before=len(server.requests)
                expect(f'catch(({goal},fail),error({formal},_),true)')
                assert len(server.requests)==before
        for option in ['offset(0)','template(X)']:
            before=len(server.requests)
            expect(f'catch((rpc({uri},true,[{option}]),fail),error(domain_error(rpc_option,_),_),true),var(X)')
            assert len(server.requests)==before
        for options in ['[timeout(1),timeout(bad)]','[on_timeout(42)]']:
            expect(f'promise({uri},X=ok,R,[once(true),template(pair(X,X))]),catch((yield(R,_,{options}),fail),error(_,_),true),yield(R,success([pair(ok,ok)],false)),var(X)')
        print(f'PASS {count} strict Boolean, zero-request, precedence, paging and sharing assertions')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', default=str(ROOT/'query-worker'))
    run(str(Path(parser.parse_args().worker).resolve()))
