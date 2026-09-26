"""Protected GNU↔GNU and GNU↔SWI RPC over disposable TLS bridges; no persistent keys."""
import http.client
import http.server
import json
import os
from pathlib import Path
import select
import socket
import ssl
import subprocess
import tempfile
import threading
import urllib.parse
from comparison_config import record_run,RUN_DIRECTORIES,digest
from https_tests import command,certificate

TOKEN='Gnu_Test_Only_'+('A'*40)
INBOUND='Caller_Test_Only_'+('C'*40)
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        auth=self.headers.get('Authorization')
        self.server.observations.append((urllib.parse.urlsplit(self.path).path,bool(auth),auth=='Bearer '+self.server.token))
        assert auth!='Bearer '+INBOUND,'inbound credential forwarded'
        if self.server.redirect:
            self.send_response(302);self.send_header('Location',self.server.redirect);self.end_headers();return
        if self.path.startswith('/source'):
            status,body=200,b'p(ok).'
        else:
            connection=http.client.HTTPConnection('127.0.0.1',self.server.backend,timeout=5)
            headers={'Authorization':auth} if auth else {}
            forward=self.path.replace('/nested/call?','/call?',1)
            connection.request('GET',forward,headers=headers)
            response=connection.getresponse();status=response.status;body=response.read();connection.close()
        self.send_response(status);self.end_headers();self.wfile.write(body)
class Bridge:
    def __init__(self,backend,token,cert,key):
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.observations=[];self.server.backend=backend;self.server.token=token;self.server.redirect=''
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.uri=f'https://localhost:{self.server.server_port}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

def main():
    swi,trinity=record_run('outbound-credentials');checks=0;processes=[];bridges=[]
    with tempfile.TemporaryDirectory(prefix='outbound-credentials-') as tmp, tempfile.TemporaryFile(mode='w+') as log:
        root=Path(tmp);token=root/'gnu.token';token.write_text(TOKEN);token.chmod(0o600)
        swi_token=root/'swi.token';swi_token.touch(mode=0o600)
        policy=root/'policy';policy.touch(mode=0o600)
        def write(text):policy.write_text(text);policy.chmod(0o600)
        env=dict(os.environ,ISO_OUTBOUND_POLICY=str(policy),ISO_CA_FILE=str(root/'ca.pem'))
        try:
            command('openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'ca.key'),'-out',str(root/'ca.pem'),'-days','1','-subj','/CN=Disposable RPC Test CA','-addext','basicConstraints=critical,CA:TRUE')
            cert,key=certificate(root,'peer','DNS:localhost')
            node=subprocess.Popen([os.environ.get('ISO_NODE','./isobase-node'),'--auth-token-file',str(token),'--port','0'],stdout=subprocess.PIPE,stderr=log,text=True,env=env);processes.append(node)
            assert select.select([node.stdout],[],[],5)[0];gp=json.loads(node.stdout.readline())['port']
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));sp=sock.getsockname()[1]
            goal=f"node:node({sp},[profile(isobase),auth(private),ip('127.0.0.1')]),node_tokens:issue_token(owner,[execute],[],T),setup_call_cleanup(open('{swi_token}',write,S),format(S,'~s',[T]),close(S)),writeln(ready),flush_output,thread_get_message(stop)"
            peer=subprocess.Popen([swi,'-q','-s',str(trinity/'load.pl'),'-g',goal],stdout=subprocess.PIPE,stderr=log,text=True);processes.append(peer)
            assert select.select([peer.stdout],[],[],15)[0] and peer.stdout.readline().strip()=='ready'
            gnu=Bridge(gp,TOKEN,cert,key);bridges.append(gnu)
            sw=Bridge(sp,swi_token.read_text(),cert,key);bridges.append(sw)
            unrelated=Bridge(gp,TOKEN,cert,key);bridges.append(unrelated)
            def rule(bridge,secret=None,endpoint='/call'):
                line=f'https localhost {bridge.server.server_port} 127.0.0.1'
                return line+(f' rpc {endpoint} {secret}' if secret else '')+'\n'
            def run(goal,kind=None,configuration=env):
                nonlocal checks
                if kind:goal=f'catch(({goal},Caught=no),error({kind},_),Caught=yes),Caught==yes'
                p=subprocess.run([os.environ.get('ISO_WORKER','./query-worker'),f'query(({goal}),ok)','1'],input='',text=True,capture_output=True,env=configuration,timeout=8)
                # Diagnostics and query answers must not contain fixture credentials.
                assert TOKEN not in p.stdout+p.stderr and swi_token.read_text() not in p.stdout+p.stderr,'credential disclosure'
                rows=[json.loads(line) for line in p.stdout.splitlines()]
                assert p.returncode==0 and rows==[{'type':'success','answers':['ok'],'more':False}],(goal,rows,p.stderr)
                checks+=1
            for bridge,secret in [(gnu,token),(sw,swi_token)]:
                write(rule(bridge))
                run(f"rpc('{bridge.uri}',true)",'http_status_error' if bridge is gnu else 'authorization_error(anonymous,execution)')
                assert bridge.server.observations[-1][1] is False
                write(rule(bridge,secret))
                run(f"rpc('{bridge.uri}',true)")
                run(f"promise('{bridge.uri}',true,R,[template(ok)]),yield(R,success([ok],false))")
                assert all(entry[2] for entry in bridge.server.observations[-2:])
            write(rule(gnu,token,endpoint='/nested/call'))
            run(f"rpc('{gnu.uri}/nested',true)")
            run(f"rpc('{gnu.uri}',true)",'outbound_credential_scope')
            # An incoming bearer is never reused for an outgoing request.
            caller_token=root/'caller.token';caller_token.write_text(INBOUND);caller_token.chmod(0o600)
            caller=subprocess.Popen([os.environ.get('ISO_NODE','./isobase-node'),'--auth-token-file',str(caller_token),'--port','0'],stdout=subprocess.PIPE,stderr=log,text=True,env=env);processes.append(caller)
            assert select.select([caller.stdout],[],[],5)[0];cp=json.loads(caller.stdout.readline())['port']
            for credential in [None,token]:
                write(rule(gnu,credential))
                call=f"rpc('{gnu.uri}',true)"
                if credential is None:call=f'catch(({call},C=no),error(http_status_error,_),C=yes),C==yes'
                connection=http.client.HTTPConnection('127.0.0.1',cp,timeout=6)
                connection.request('GET','/call?'+urllib.parse.urlencode(dict(goal=call,template='ok',format='prolog')),headers={'Authorization':'Bearer '+INBOUND})
                response=connection.getresponse();body=response.read().decode().strip();connection.close()
                assert response.status==200 and body=='success([ok],false).',body
                assert gnu.server.observations[-1][1]==bool(credential)
                checks+=1
            write(rule(gnu,token)+rule(unrelated))
            run(f"rpc('{unrelated.uri}',true)",'http_status_error')
            assert unrelated.server.observations[-1][1] is False
            before=len(gnu.server.observations)
            run(f"rpc('{gnu.uri}/other',true)",'outbound_credential_scope')
            assert len(gnu.server.observations)==before
            # Source fetch on the SAME origin gets no credential; final RPC does.
            run(f"rpc('{gnu.uri}',p(ok),[src_uri('{gnu.uri}/source')])")
            assert gnu.server.observations[-2][0:2]==('/source',False) and gnu.server.observations[-1][2]
            # Submitted code cannot forward or replace a credential using HTTP options.
            run(f"rpc('{gnu.uri}',true,[request_header(authorization=stolen)])",'domain_error(rpc_option,request_header(authorization=stolen))')
            for location in [unrelated.uri+'/call',gnu.uri+'/other',f'http://127.0.0.1:{gp}/call']:
                gnu.server.redirect=location;before=len(unrelated.server.observations)
                run(f"rpc('{gnu.uri}',true)",'http_redirect_denied')
                assert len(unrelated.server.observations)==before
            gnu.server.redirect=''
            # No credential is sent over plaintext, even with an owner auth record.
            write(f'http 127.0.0.1 {gp} 127.0.0.1 rpc /call {token}\n')
            run(f"rpc('http://127.0.0.1:{gp}',true)",'outbound_policy_invalid')
            write(rule(gnu,token))
            for bad in ['short','A'*257,'A'*32+'\r\nInjected: bad','A'*32+'\x00']:
                token.write_text(bad);run(f"rpc('{gnu.uri}',true)",'outbound_credential_invalid')
            token.write_text('short')
            run(f"findall(N,(between(1,24,N),promise('{gnu.uri}',true,R),catch((yield(R,_),C=no),error(outbound_credential_invalid,_),C=yes),C==yes),Ns),length(Ns,24)")
            token.write_text(TOKEN);token.chmod(0o644);run(f"rpc('{gnu.uri}',true)",'outbound_credential_invalid');token.chmod(0o600)
            token.unlink();run(f"rpc('{gnu.uri}',true)",'outbound_credential_invalid')
            other=root/'other.token';other.write_text(TOKEN);other.chmod(0o600);token.symlink_to(other)
            run(f"rpc('{gnu.uri}',true)",'outbound_credential_invalid');token.unlink();token.write_text(TOKEN);token.chmod(0o600)
            # Reading the next token file contents does not fall back to the old token.
            token.write_text('Wrong_'+('B'*40));run(f"rpc('{gnu.uri}',true)",'http_status_error');token.write_text(TOKEN)
            run(f"rpc('{gnu.uri}',true)")
            # TLS failures must occur before any HTTP header is delivered.
            invalid_ca=dict(env,ISO_CA_FILE=str(root/'missing-ca'))
            before=len(gnu.server.observations);run(f"rpc('{gnu.uri}',true)",'https_ca_file_error',invalid_ca)
            assert len(gnu.server.observations)==before
            # A pinned SWI client reads the token privately, verifies our CA, then calls GNU.
            script=root/'caller.pl'
            script.write_text(f""":- use_module('{trinity}/prolog/web_prolog/rpc.pl').
:- use_module(library(readutil)).
:- initialization(main,main).
main :- read_file_to_string('{token}',T,[]),atomics_to_string(['Bearer ',T],H),
    rpc:rpc('{gnu.uri}',true,[request_header('Authorization'=H),cacert_file('{root}/ca.pem')]),writeln(ok).
""")
            p=subprocess.run([swi,'-q',str(script)],capture_output=True,text=True,timeout=10)
            assert TOKEN not in p.stdout+p.stderr
            assert p.returncode==0 and p.stdout.strip()=='ok',(p.returncode,p.stdout,p.stderr)
            checks+=1
            log.seek(0);diagnostics=log.read()
            assert TOKEN not in diagnostics and INBOUND not in diagnostics and swi_token.read_text() not in diagnostics,'credential in backend diagnostics'
            evidence={'passed':checks,'failed':0,'directions':['GNU to GNU','GNU to SWI','SWI to GNU'],
                      'transport':'verified TLS bridges to protected loopback backends',
                      'worker_sha256':digest(os.environ.get('ISO_WORKER','./query-worker')),
                      'node_sha256':digest(os.environ.get('ISO_NODE','./isobase-node'))}
            (RUN_DIRECTORIES['outbound-credentials']/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')
            print(f'PASS {checks} scoped credential checks; protected GNU→GNU, GNU→SWI and SWI→GNU')
        finally:
            for b in reversed(bridges):b.close()
            for p in processes:p.terminate()
            for p in processes:
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()

if __name__=='__main__':main()
