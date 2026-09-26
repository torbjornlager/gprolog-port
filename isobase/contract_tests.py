"""Independent draft-contract expectations, evaluated on both pinned nodes."""
import http.client
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import tempfile
import urllib.parse
from comparison_config import ROOT, RUN_DIRECTORIES, record_run, verify_contract

swi,trinity=record_run('contract')
contract=verify_contract();processes=[];results=[]
try:
    with tempfile.TemporaryFile(mode='w+') as log:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        goal=f"node:node({port},[profile(isobase),auth(open),ip('127.0.0.1')]),writeln(ready),flush_output,thread_get_message(stop)"
        reference=subprocess.Popen([swi,'-q','-s',str(trinity/'load.pl'),'-g',goal],stdout=subprocess.PIPE,stderr=log,text=True);processes.append(reference)
        assert select.select([reference.stdout],[],[],15)[0] and reference.stdout.readline().strip()=='ready','SWI startup failed'
        node=subprocess.Popen([os.environ.get('ISO_COMPILED_NODE',str(ROOT/'isobase-node')),'--auth','open','--port','0'],stdout=subprocess.PIPE,stderr=log,text=True);processes.append(node)
        assert select.select([node.stdout],[],[],5)[0],'GNU startup timeout'
        gp=json.loads(node.stdout.readline())['port']
        for implementation,p in [('gnu',gp),('swi',port)]:
            for case in contract['independent_cases']:
                connection=http.client.HTTPConnection('127.0.0.1',p,timeout=5)
                try:
                    connection.request('GET','/call?'+urllib.parse.urlencode({'goal':case['goal'],'template':case['template'],'format':'prolog','limit':10}))
                    response=connection.getresponse();body=response.read().decode().strip()
                    results.append({'implementation':implementation,'id':case['id'],'expected':case['expected'],'actual':body,'pass':response.status==200 and body==case['expected']})
                finally:connection.close()
        assert all(r['pass'] for r in results),results
        print(f'PASS contract {contract["version"]}: {len(results)} independent assertions (not a full conformance claim)')
finally:
    (RUN_DIRECTORIES['contract']/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    for p in processes:p.terminate()
    for p in processes:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
