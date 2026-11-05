"""Barrier-controlled continuation/retirement orderings on disposable controllers."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import promise_context_tests as base

ROOT=Path(__file__).resolve().parent
HOOK=r'''
/* Test-only barriers; installed solely in a disposable controller copy. */
static int audit_used;
static const char *audit_dir(void){return getenv("GNU_CONTEXT_RACE_DIR");}
static int audit_file(const char *name){char p[PATH_MAX];snprintf(p,sizeof p,"%s/%s",audit_dir(),name);return access(p,F_OK)==0;}
static void audit_mark(const char *name){char p[PATH_MAX];snprintf(p,sizeof p,"%s/%s",audit_dir(),name);int f=open(p,O_WRONLY|O_CREAT,0600);if(f>=0)close(f);}
static void audit_wait(void){for(int n=0;n<5000&&!audit_file("continue");n++)usleep(1000);}
static void audit_resume(Query *q){
 if(audit_dir()&&!audit_used&&audit_file("resume")){audit_used=1;q->expires=0;audit_mark("entered");audit_wait();}
}
static void audit_scan(Query *q){
 if(!audit_dir()||!q->pid)return;
 if(audit_used&&q->busy&&q->expires==0)audit_mark("busy_seen");
 if(!audit_used&&!q->busy&&audit_file("retire")){audit_used=1;q->expires=0;audit_mark("entered");audit_wait();}
}
'''

def instrument(directory,unsafe):
    original=(ROOT/'http.c').read_text();text=original
    text=text.replace('static void call_request(int fd,Request *r) {',HOOK+'\nstatic void call_request(int fd,Request *r) {')
    assert text.count('q->busy=1;char next[40];')==1
    text=text.replace('q->busy=1;char next[40];','q->busy=1;audit_resume(q);char next[40];')
    needle='pthread_mutex_lock(&mutex);for(int i=0;i<max_queries;i++)if(queries[i].pid&&!queries[i].busy&&queries[i].expires<=now())release(&queries[i]);enforce_memory();pthread_mutex_unlock(&mutex);'
    assert text.count(needle)==1
    predicate='queries[i].pid&&'+('' if unsafe else '!queries[i].busy&&')+'queries[i].expires<=now()'
    replacement='pthread_mutex_lock(&mutex);for(int i=0;i<max_queries;i++){audit_scan(&queries[i]);if('+predicate+')release(&queries[i]);}enforce_memory();pthread_mutex_unlock(&mutex);'
    text=text.replace(needle,replacement)
    source=directory/'http.c';source.write_text(text)
    exe=directory/'isobase-node'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-O2','-pthread','-I',str(ROOT),str(source),'-o',str(exe)],check=True,capture_output=True,text=True)
    for name in ['query-worker','query-supervisor']:(directory/name).symlink_to(ROOT/name)
    return exe,dict(source_sha256=hashlib.sha256(original.encode()).hexdigest(),instrumented_sha256=hashlib.sha256(text.encode()).hexdigest(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())

def trial(mode,unsafe=False):
    with tempfile.TemporaryDirectory(prefix='gnu-context-race-') as tmp:
        directory=Path(tmp);exe,hashes=instrument(directory,unsafe)
        prior=base.NODE;prior_dir=os.environ.get('GNU_CONTEXT_RACE_DIR')
        base.NODE=exe;os.environ['GNU_CONTEXT_RACE_DIR']=str(directory)
        peer=base.Peer();node=base.Node(idle=10000);owner=secrets.token_hex(32);gate=peer.gate('race')
        goal=base.held_goal(peer.url+'/hold/race')
        try:
            ref,first=base.created(node,goal,owner);assert gate.arrived.wait(5),'producer arrival'
            original=node.descendants();assert original,'retained execution'
            probe_owner=secrets.token_hex(32);probe_goal='member(X,[one,two,three])'
            assert node.call(probe_goal,'X',probe_owner,limit=1)=='success([one],true).'
            (directory/mode).touch()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                if mode=='resume':
                    resume=pool.submit(node.call,goal,'v(R,A)',owner,1,2)
                    base.wait_for(lambda:(directory/'entered').exists(),'resume admission barrier')
                    (directory/'continue').touch()
                    base.wait_for(lambda:(directory/'busy_seen').exists(),'expiry scan observes active retained query')
                    probe=node.call(probe_goal,'X',probe_owner,offset=1,limit=1);assert probe=='success([two],true).',probe
                    # Probe's admission mutex lies after the expiry scan/retirement.
                    survived=original<=node.descendants()
                    if unsafe:
                        assert not survived,'negative control must retire an active execution'
                        assert gate.closed.wait(5),'unsafe retirement closes pending producer'
                    else:assert survived,'active continuation must win over expiry'
                    gate.release.set();result=resume.result(timeout=6)
                    if not unsafe:
                        assert result==f'success([v({ref},barrier),v({ref},success([first],false))],false).',result
                        assert gate.count==1,'resume must preserve the original pending promise'
                else:
                    base.wait_for(lambda:(directory/'entered').exists(),'retirement decision barrier')
                    resume=pool.submit(node.call,goal,'v(R,A)',owner,1,2)
                    (directory/'continue').touch()
                    assert gate.closed.wait(5),'old producer closes before release'
                    base.wait_for(lambda:gate.count==2,'new request creates a new execution, not the retired scope')
                    assert not(original&node.descendants()),'retired execution must stay absent'
                    gate.release.set();result=resume.result(timeout=6)
                    assert result==f'success([v({ref},barrier),v({ref},success([first],false))],false).',result
                assert node.call(probe_goal,'X',probe_owner,offset=(2 if mode=='resume' else 1),limit=10)==('success([three],false).' if mode=='resume' else 'success([two,three],false).')
                base.wait_for(lambda:not node.descendants(),'execution resources reclaimed')
            return dict(mode=mode,negative_control=unsafe,reference=ref,first=first,continuation=result,producer_requests=gate.count,original_survived_admission=(survived if mode=='resume' else False),hashes=hashes)
        finally:
            (directory/'continue').touch();gate.release.set();node.close();peer.close();base.NODE=prior
            if prior_dir is None:os.environ.pop('GNU_CONTEXT_RACE_DIR',None)
            else:os.environ['GNU_CONTEXT_RACE_DIR']=prior_dir


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path);args=p.parse_args();rows=[]
    for id,mode,unsafe in [('GRACE-RESUME-FIRST','resume',False),('GRACE-RETIRE-FIRST','retire',False),('GRACE-NEGATIVE-ACTIVE','resume',True)]:
        row=dict(candidate='gnu',id=id,negative_control=unsafe)
        try:row.update(status='pass',observation=trial(mode,unsafe))
        except Exception as error:row.update(status='fail',detail=str(error))
        rows.append(row);print(id,row['status'],row.get('detail','').strip(),flush=True)
    if args.report:args.report.write_text(json.dumps(dict(suite='gnu-context-race-0.1',scope='Implementation regression barriers on disposable controllers, not three additional portable language cases',results=rows),indent=2)+'\n')
    return int(any(r['status']!='pass' for r in rows))
if __name__=='__main__':raise SystemExit(main())
