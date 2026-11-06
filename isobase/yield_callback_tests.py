"""yield/3 timeout callbacks: formal failure, one result, and retained promises."""
import http.client
import http.server
import json
import os
import select
import subprocess
import threading
from urllib.parse import urlencode

from outbound_test_policy import allow


class SlowReply(http.server.BaseHTTPRequestHandler):
    released = threading.Event()

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith('/release/'):
            self.released.set()
        assert self.released.wait(8), 'fixture release'
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'success([ready],false).')


def check(uri, port, body):
    # Release the pending reply only after checking the callback, so the
    # timeout does not depend on scheduler timing or an artificial sleep.
    goal = (f"promise('{uri}',true,R),{body},"
            f"promise('{uri}/release',true,Gate),yield(Gate,_),"
            'yield(R,success([ready],false)),X=passed')
    SlowReply.released.clear()
    result = subprocess.run(
        [os.environ.get('ISO_WORKER', './query-worker'), f'query(({goal}),X)', '100'],
        input='', text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    messages = [json.loads(line) for line in result.stdout.splitlines()]
    assert messages == [{'type': 'success', 'answers': ['passed'], 'more': False}], (goal, messages)
    SlowReply.released.clear()
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    try:
        connection.request('GET', '/call?' + urlencode(dict(goal=goal, template='X', format='prolog')))
        response = connection.getresponse()
        result = response.read().decode()
        assert response.status == 200 and ''.join(result.split()) == 'success([passed],false).', (goal, result)
    finally:
        connection.close()


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), SlowReply)
threading.Thread(target=server.serve_forever, daemon=True).start()
uri = f'http://127.0.0.1:{server.server_port}'
allow(uri)
node = None
try:
    node = subprocess.Popen(
        [os.environ.get('ISO_NODE', './isobase-node'), '--auth', 'open', '--port', '0', '--time-ms', '5000'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert select.select([node.stdout], [], [], 5)[0], 'node readiness'
    port = json.loads(node.stdout.readline())['port']
    check(uri, port, 'catch(yield(R,_,[timeout(0),on_timeout(fail)]),E,true),'
               'nonvar(E),E=error(timeout_callback_failed(R),_)')
    check(uri, port, 'findall(V,yield(R,_,[timeout(0),on_timeout(member(V,[first,second]))]),[first])')
    check(uri, port, 'catch(yield(R,_,[timeout(0),on_timeout(throw(callback_ball))]),E,true),'
               'E==callback_ball')
    check(uri, port, 'yield(R,_,[timeout(0),on_timeout((fail;V=second))]),V==second')
    check(uri, port, 'yield(R,_,[timeout(0)])')
    print('PASS 10 worker/HTTP yield callback cases; every promise remains collectable')
finally:
    SlowReply.released.set()
    if node is not None:
        node.terminate()
        try:
            node.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            node.kill()
            node.communicate()
    server.shutdown()
    server.server_close()
