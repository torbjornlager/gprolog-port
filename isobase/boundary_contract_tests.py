from outbound_test_policy import allow
"""C04 requirements and a scoped TU Wien selection: both nodes vs explicit goals."""
import http.client
import http.server
import json
import os
import select
import socket
import subprocess
import tempfile
import threading
import urllib.parse
from comparison_config import CONTRACT_DIR,ROOT,RUN_DIRECTORIES,record_run

swi,trinity=record_run('boundary-contract')
from boundary_decisions import validate
decisions=validate()
selection=json.loads((CONTRACT_DIR/'iso-test-selection.json').read_text())['cases']
cases=[{'id':d['id'],'goal':d['probe'],'expected':'success([ok],false).'} for d in decisions if d['probe']]+selection
class PathFixture(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        good=urllib.parse.urlsplit(self.path).path=='/nested/call'
        body=b'success([v],false).' if good else b'failure.'
        self.send_response(200 if good else 404);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
fixture=http.server.ThreadingHTTPServer(('127.0.0.1',0),PathFixture)
threading.Thread(target=fixture.serve_forever,daemon=True).start()
processes=[];results=[]
try:
    with tempfile.TemporaryFile(mode='w+') as log:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        goal=f"node:node({port},[profile(isobase),auth(open),ip('127.0.0.1')]),writeln(ready),flush_output,thread_get_message(stop)"
        peer=subprocess.Popen([swi,'-q','-s',str(trinity/'load.pl'),'-g',goal],stdout=subprocess.PIPE,stderr=log,text=True);processes.append(peer)
        assert select.select([peer.stdout],[],[],15)[0] and peer.stdout.readline().strip()=='ready'
        node=subprocess.Popen([os.environ.get('ISO_COMPILED_NODE',str(ROOT/'isobase-node')),'--auth','open','--port','0','--time-ms','3000'],stdout=subprocess.PIPE,stderr=log,text=True);processes.append(node)
        assert select.select([node.stdout],[],[],5)[0];gp=json.loads(node.stdout.readline())['port']
        allow(f'http://127.0.0.1:{gp}');allow(f'http://127.0.0.1:{fixture.server_port}')
        for implementation,p in [('gnu',gp),('swi',port)]:
            for case in cases:
                goal=case['goal'].replace('__RPC_TARGET__',f'http://127.0.0.1:{gp}').replace('__PATH_TARGET__',f'http://127.0.0.1:{fixture.server_port}')
                connection=http.client.HTTPConnection('127.0.0.1',p,timeout=6)
                try:
                    connection.request('GET','/call?'+urllib.parse.urlencode({'goal':goal,'template':'ok','format':'prolog','limit':10,'timeout':3}))
                    response=connection.getresponse();body=response.read().decode().strip()
                    row={'implementation':implementation,'id':case['id'],'goal':case['goal'],'expected':case['expected'],'actual':body,'http_status':response.status,'pass':response.status==200 and body==case['expected']}
                except (OSError,http.client.HTTPException) as error:row={'implementation':implementation,'id':case['id'],'pass':False,'transport_error':str(error)}
                finally:connection.close()
                results.append(row)
        failed=[r for r in results if not r['pass']]
        for implementation in ['gnu','swi']:
            rows=[r for r in results if r['implementation']==implementation]
            print(f'{implementation}: {sum(r["pass"] for r in rows)}/{len(rows)} required probes passed')
        print(f'{sum(d["probe"] is None for d in decisions)} limit/extension observations are classified outside portable parity; not counted as passes')
        for row in failed:print(json.dumps(row))
        if failed:raise SystemExit(f'{len(failed)} unmet contract requirements; recorded without expected-failure waivers')
finally:
    (RUN_DIRECTORIES['boundary-contract']/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    fixture.shutdown();fixture.server_close()
    for p in processes:p.terminate()
    for p in processes:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
