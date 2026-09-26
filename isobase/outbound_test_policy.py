"""Explicit exact-origin grants for disposable fixtures; never edit owner policy."""
import atexit
import fcntl
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

path=os.environ.get('ISO_TEST_OUTBOUND_POLICY')
if not path:
    directory=tempfile.TemporaryDirectory(prefix='isobase-outbound-tests-')
    atexit.register(directory.cleanup)
    path=str(Path(directory.name)/'policy')
    Path(path).touch(mode=0o600)
    os.environ['ISO_TEST_OUTBOUND_POLICY']=path
os.environ['ISO_OUTBOUND_POLICY']=path

def allow(uri,ip='127.0.0.1'):
    parsed=urlsplit(uri)
    host=parsed.hostname
    if ':' in host:host='['+host+']'
    rule=f'{parsed.scheme} {host} {parsed.port or (443 if parsed.scheme=="https" else 80)} {ip}\n'
    with open(path+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        content=Path(path).read_text()
        if rule not in content.splitlines(keepends=True):
            fd,temp=tempfile.mkstemp(dir=str(Path(path).parent))
            with os.fdopen(fd,'w') as target:target.write(content+rule)
            os.replace(temp,path)
