"""Access boundary tests; run against interpreted or compiled nodes via ISO_NODE."""
import http.client
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import tempfile
import urllib.parse

EXE=os.environ.get('ISO_NODE','./isobase-node')
TOKEN='aB09_-'*10

def fails(args):
    p=subprocess.run([EXE,*args],capture_output=True,text=True,timeout=4)
    assert p.returncode==2 and not p.stdout,(args,p.returncode,p.stdout,p.stderr)
    assert TOKEN not in p.stderr

class Node:
    def __init__(self,args):
        self.p=subprocess.Popen([EXE,'--port','0','--max-queries','1',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert select.select([self.p.stdout],[],[],5)[0]
        self.port=json.loads(self.p.stdout.readline())['port']
    def request(self,headers=None,path='/call?goal=true',method='GET',extra=b''):
        if headers is None:headers=[f'Host: 127.0.0.1:{self.port}',f'Authorization: Bearer {TOKEN}']
        with socket.create_connection(('127.0.0.1',self.port),timeout=4) as s:
            s.sendall((f'{method} {path} HTTP/1.1\r\n'+'\r\n'.join(headers)+'\r\n\r\n').encode()+extra)
            r=http.client.HTTPResponse(s);r.begin();body=r.read()
            assert TOKEN.encode() not in body
            return r.status,body,dict(r.getheaders())
    def close(self):
        self.p.terminate();self.p.wait(timeout=5)
        assert self.p.returncode==0 and not self.p.stderr.read()

with tempfile.TemporaryDirectory() as d:
    root=Path(d);token=root/'token'
    def write(value=TOKEN,mode=0o600):
        token.write_text(value);token.chmod(mode)
    fails([]);fails(['--auth','bad'])
    write();fails(['--auth','open','--auth-token-file',str(token)])
    fails(['--auth-token-file',str(root)])
    link=root/'link';link.symlink_to(token);fails(['--auth-token-file',str(link)])
    fifo=root/'fifo';os.mkfifo(fifo);fails(['--auth-token-file',str(fifo)])
    for value in ['', 'a'*31,'a'*257,TOKEN+'\nextra',TOKEN+'\x00',TOKEN+' ',TOKEN+'\r\n']:
        write(value);fails(['--auth-token-file',str(token)])
    write(mode=0o644);fails(['--auth-token-file',str(token)])
    write(TOKEN+'\n');node=Node(['--auth-token-file',str(token)])
    try:
        host=f'Host: 127.0.0.1:{node.port}';auth=f'Authorization: Bearer {TOKEN}'
        assert node.request()[0]==200
        assert node.request([host,f'authorization: bEaReR {TOKEN}'])[0]==200
        for headers,status in [
            ([host],401),([host,'Cookie: token='+TOKEN],401),
            ([host,'Authorization: Bearer '+'b'*60],401),
            ([host,'Authorization: Bearer '+TOKEN+'x'],401),
            ([host,auth,auth],400),([auth],400),([host,host,auth],400),
            (['Host: attacker.test',auth],403),(['Host: localhost:1',auth],403),
            ([host,auth,'Origin: null'],403),([host,auth,'Origin: https://attacker.test'],403),
            ([host,auth,f'Origin: http://localhost:{node.port}'],403),
            ([host,auth,f'Origin: http://127.0.0.1:{node.port}'],200),
            ([host,auth,'Sec-Fetch-Site: cross-site'],403),
            ([host,auth,'Sec-Fetch-Site: same-site'],403),
            ([host,auth,'Sec-Fetch-Site: same-origin'],200),
            ([host,auth,'Sec-Fetch-Site: none'],200),
            ([host,auth,'Sec-Fetch-Site: none','Sec-Fetch-Site: none'],400),
            ([host,auth,'Origin: null','Origin: null'],400),
            ([host,auth,'Transfer-Encoding: chunked'],400),
            ([host,auth,'Content-Length: 1'],400),
            ([host,auth,'Content-Length: 0','Content-Length: 0'],400),
            ([host,auth,'Content-Length: 0'],200),
            ([host,auth,'\rX-Bad: value','Origin: null'],400),
            ([host,auth,' X-Fold: value'],400),([host,auth,'X-Bad : value'],400),
            ([host,auth,'X-Bad: a\x01b'],400),([host,auth,'X-Bad: a\x00b'],400),
        ]:
            result=node.request(headers);assert result[0]==status,(headers,result)
            assert not any(k.lower().startswith('access-control-') for k in result[2])
        assert 'WWW-Authenticate' in node.request([host])[2]
        assert node.request(method='OPTIONS')[0]==405
        assert node.request(extra=b'x')[0]==400
        assert node.request(extra=b'GET /call?goal=true HTTP/1.1\r\n\r\n')[0]==400
        assert node.request([host],path='/call?goal=true&token='+TOKEN)[0]==401
        # A saved query survives rejected requests even with only one slot.
        path='/call?'+urllib.parse.urlencode(dict(goal='p(X)',src_text='p(a). p(b). p(c).',limit=1))
        first=node.request(path=path);assert json.loads(first[1])['data']==[{'X':'a'}]
        children=lambda:subprocess.run(['pgrep','-P',str(node.p.pid)],capture_output=True,text=True).stdout.strip()
        before=children();assert before
        for _ in range(4):assert node.request([host],path=path+'&offset=1')[0]==401
        assert children()==before
        second=node.request(path=path+'&offset=1');assert json.loads(second[1])['data']==[{'X':'b'}]
        assert children()==before
        assert node.request(path='/call?goal=true&format=prolog')[1]==b'success([true],false).\n'
        write('z'*64);assert node.request()[0]==200
        token.unlink();assert node.request()[0]==200
    finally:node.close()
    write('z'*64);node=Node(['--auth-token-file',str(token)])
    try:
        assert node.request()[0]==401
        assert node.request([f'Host: localhost:{node.port}','Authorization: Bearer '+'z'*64])[0]==200
    finally:node.close()
    for size in (32,256):
        value='v'*size;write(value);node=Node(['--auth-token-file',str(token)])
        try:
            host=f'Host: localhost:{node.port}'
            assert node.request([host,'Authorization: Bearer '+value])[0]==200
            assert node.request([host,'Authorization: Bearer '+value[:-1]])[0]==401
        finally:node.close()
    node=Node(['--auth','open'])
    try:
        assert node.request([f'Host: localhost:{node.port}'])[0]==200
        assert node.request(['Host: attacker.test'])[0]==403
        assert node.request([f'Host: localhost:{node.port}','Sec-Fetch-Site: cross-site'])[0]==403
    finally:node.close()
print('PASS security: startup policy, credentials, headers, browser boundary and protected continuations')
