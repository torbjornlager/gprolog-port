"""S03 controller lifecycle, ACLs and actual spawned-process inheritance."""
import http.client
import json
import os
from pathlib import Path
import platform
import secrets
import select
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
EXE=Path(os.environ.get('ISO_NODE',ROOT/'isobase-node')).resolve()

def provision(path):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as file:
        file.write(secrets.token_hex(32)+'\n')
    return path.read_text().strip()

def request(port,token):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    c.request('GET','/call?goal=true',headers={'Authorization':'Bearer '+token})
    r=c.getresponse();body=r.read();c.close()
    assert token.encode() not in body
    return r.status,body

def start(exe,token,env=None,pass_fds=()):
    p=subprocess.Popen([str(exe),'--auth-token-file',str(token),'--port','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,pass_fds=pass_fds)
    assert select.select([p.stdout],[],[],5)[0]
    line=p.stdout.readline()
    assert line,(p.poll(),p.stderr.read())
    return p,json.loads(line)['port']

def stop(p,values):
    p.terminate();p.wait(timeout=5);output=p.stderr.read()
    assert p.returncode==0 and all(v not in output for v in values)

def fails(token):
    p=subprocess.run([str(EXE),'--auth-token-file',str(token),'--port','0'],capture_output=True,text=True,timeout=5)
    assert p.returncode==2 and not p.stdout

with tempfile.TemporaryDirectory(prefix='credential-lifecycle-') as tmp:
    root=Path(tmp);token=root/'owner.token';first=provision(token)
    assert len(first)==64 and token.stat().st_mode&0o777==0o600
    try:provision(token);raise AssertionError('Existing credential overwritten')
    except FileExistsError:pass
    assert token.read_text().strip()==first
    link=root/'link';link.symlink_to(token)
    try:provision(link);raise AssertionError('Symlink followed')
    except FileExistsError:pass
    p,port=start(EXE,token)
    try:
        replacement=root/'replacement';second=provision(replacement);os.replace(replacement,token)
        assert request(port,first)[0]==200 and request(port,second)[0]==401
        token.unlink();assert request(port,first)[0]==200
    finally:stop(p,[first,second])
    fails(token) # Revoked/missing file cannot reopen the service.
    third=provision(token);p,port=start(EXE,token)
    try:assert request(port,first)[0]==401 and request(port,third)[0]==200
    finally:stop(p,[first,second,third])
    if platform.system()=='Darwin':
        subprocess.run(['chmod','+a','everyone allow read',str(token)],check=True)
        assert token.stat().st_mode&0o777==0o600
        fails(token)
        # The shared checker also protects outbound token and policy files.
        source=root/'acl.c';source.write_text('''#include <fcntl.h>
#include "credential_file.h"
int main(int argc,char **argv){(void)argc;int f=open(argv[1],O_RDONLY);int good=credential_private_fd(f);close(f);return good?0:1;}
''')
        binary=root/'acl';subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(ROOT),str(source),'-o',str(binary)],check=True)
        assert subprocess.run([str(binary),str(token)]).returncode==1
        subprocess.run(['chmod','-N',str(token)],check=True)
        assert subprocess.run([str(binary),str(token)]).returncode==0
    # Replace only a disposable node's supervisor with an observation helper.
    # The actual controller must spawn it with zero core limits, a minimal
    # environment and no inherited owner descriptor.
    node=root/'isobase-node';node.symlink_to(EXE)
    report=root/'report';source=root/'inspect.c'
    owner=root/'owner-secret';owner.write_text('descriptor-canary')
    with owner.open() as file:
        fd=file.fileno()
        source.write_text(f'''#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/resource.h>
int main(void){{
 struct rlimit r;getrlimit(RLIMIT_CORE,&r);
 int isolated=!getenv("AMBIENT_SECRET_CANARY") && !getenv("HOME") && (!getenv("ISO_OFFSET") || !strcmp(getenv("ISO_OFFSET"),"0"));
 errno=0;int closed=fcntl({fd},F_GETFD)==-1 && errno==EBADF;
 const char *path=getenv("ISO_OUTBOUND_POLICY");FILE *f=path?fopen(path,"w"):NULL;
 if(!f)return 2;
 fprintf(f,"%d %d %d\\n",r.rlim_cur==0 && r.rlim_max==0,isolated,closed);fclose(f);
 puts("{{\\"type\\":\\"error\\",\\"term\\":\\"inspection_complete\\"}}");return 0;
}}
''')
        subprocess.run(['cc','-Wall','-Wextra','-Werror',str(source),'-o',str(root/'query-supervisor')],check=True)
        env=dict(os.environ,AMBIENT_SECRET_CANARY=first,ISO_OFFSET='777',ISO_OUTBOUND_POLICY=str(report))
        p,port=start(node,token,env,(fd,))
        try:
            request(port,third)
            assert report.read_text().strip()=='1 1 1',report.read_text()
        finally:stop(p,[first,second,third])
        # Repeat through the real supervisor/fork/exec path to the worker.
        supervisor=root/'query-supervisor';supervisor.rename(root/'query-worker')
        supervisor.symlink_to(EXE.parent/'query-supervisor');report.unlink()
        p,port=start(node,token,env,(fd,))
        try:
            request(port,third)
            assert report.read_text().strip()=='1 1 1',report.read_text()
        finally:stop(p,[first,second,third])
    # Verify the same dump-setting helper fails closed and does not allow
    # raising limits afterward. It runs before secrets/Prolog in all 3 binaries.
    source.write_text('''#include <assert.h>
#include "process_security.h"
int main(void){assert(iso_disable_dumps());struct rlimit r;assert(!getrlimit(RLIMIT_CORE,&r));assert(!r.rlim_cur&&!r.rlim_max);r.rlim_cur=r.rlim_max=1;assert(setrlimit(RLIMIT_CORE,&r));return 0;}
''')
    subprocess.run(['cc','-I',str(ROOT),str(source),'-o',str(root/'limits')],check=True)
    subprocess.run([str(root/'limits')],check=True)
print('PASS credential provisioning, restart revocation, ACL rejection, dump limits and child environment/descriptor isolation')
