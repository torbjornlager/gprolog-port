"""Public serving-node metadata through trusted bootstrap and HTTP workers."""
import argparse
import http.client
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import urllib.parse

ROOT=Path(__file__).resolve().parent
WORKER=Path(os.environ.get('ISO_WORKER',ROOT/'query-worker')).resolve()
SUPERVISOR=Path(os.environ.get('ISO_SUPERVISOR',ROOT/'query-supervisor')).resolve()
NODE=Path(os.environ.get('ISO_NODE',ROOT/'isobase-node')).resolve()
ROWS=[]


def check(case_id,title,operation):
    row=dict(candidate='gnu',id=case_id,title=title)
    try:row.update(status='pass',observation=operation())
    except Exception as error:row.update(status='fail',detail=str(error))
    ROWS.append(row)
    print(case_id,row['status'],flush=True)


def private(exe,goal,options=(),env=None):
    process=subprocess.Popen([str(exe),'query(('+goal+'),ok)','20',*options],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    try:
        assert select.select([process.stdout],[],[],5)[0],'worker event timeout'
        line=process.stdout.readline()
        event=json.loads(line)
        process.stdin.close()
        assert process.wait(timeout=5)==0,(event,process.stderr.read())
        assert not process.stderr.read()
        assert event==dict(type='success',answers=['ok'],more=False),event
        return event
    finally:
        if process.poll() is None:process.kill();process.wait()


class Node:
    def __init__(self,capacity=3,token=None,shared=None):
        command=[str(NODE),'--port','0','--max-queries',str(capacity),'--time-ms','2400',
                 '--max-owner-queries','1','--max-budget-queries','2']
        command+=['--auth-token-file',str(token)] if token else ['--auth','open']
        if shared:command+=['--shared-db',str(shared)]
        self.token=token.read_text().strip() if token else None
        env=dict(os.environ,ISO_NODE_SETTINGS='1:1:private',ISO_PUBLIC_NODE_SETTINGS='forged_public_metadata')
        self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        assert select.select([self.process.stdout],[],[],5)[0],'HTTP startup timeout'
        line=self.process.stdout.readline()
        assert line,(self.process.poll(),self.process.stderr.read())
        self.port=json.loads(line)['port']
        self.capacity=capacity
    def call(self,goal,**params):
        headers={'Authorization':'Bearer '+self.token} if self.token else {}
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        options=dict(goal=goal,format='prolog',template='ok');options.update(params)
        connection.request('GET','/call?'+urllib.parse.urlencode(options),headers=headers)
        response=connection.getresponse();body=response.read().decode();status=response.status;connection.close()
        if self.token:assert self.token not in body,'credential exposed'
        return status,body
    def success(self,goal,**params):
        status,body=self.call(goal,**params)
        assert status==200 and body=='success([ok],false).\n',(status,body)
        return body
    def snapshot(self,helper='node_setting',source=None):
        auth='private' if self.token else 'open'
        goal=(f"findall(K,{helper}(K,_),Keys),sort(Keys,[auth,max_inflight_calls,max_load_text_bytes,profile,sandbox,url]),"
              f"{helper}(url,'http://127.0.0.1:{self.port}'),{helper}(profile,isobase),{helper}(sandbox,whitelist),"
              f"{helper}(auth,{auth}),{helper}(max_inflight_calls,{self.capacity}),{helper}(max_load_text_bytes,1048576)")
        return self.success(goal,**({'src_text':source} if source else {}))
    def close(self):
        self.process.terminate();assert self.process.wait(timeout=5)==0
        diagnostic=self.process.stderr.read()
        assert not diagnostic,diagnostic


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    for i,exe in enumerate([WORKER,SUPERVISOR],1):
        check(f'GS-{i:03}','No serving-node settings in a standalone process',lambda e=exe:private(e,'findall(K-V,node_setting(K,V),[])',env=dict(os.environ,ISO_NODE_SETTINGS='1234:7:private')))
        goal=("node_setting(url,'http://127.0.0.1:1234'),node_setting(profile,isobase),"
              "node_setting(sandbox,whitelist),node_setting(auth,private),node_setting(max_inflight_calls,5),"
              "node_setting(max_load_text_bytes,1048576),\\+node_setting(auth,open),\\+node_setting(max_inflight_calls,8)")
        check(f'GS-{i+2:03}','Trusted bootstrap installs the exact public context',lambda e=exe,g=goal:private(e,g,['--node-settings','1234:5:private']))
    def malformed():
        inputs=['','0:3:open','65536:3:open','1234:0:open','1234:33:open','1234:3:dev',
                '1234:3:open:extra','1234:3:open\n','+1234:3:open',' 1234:3:open','1234:3:open).halt',
                '99999999999999999999999999:3:open','1234:99999999999999999999999999:open']
        for exe in [WORKER,SUPERVISOR]:
            for value in inputs:
                result=subprocess.run([str(exe),'query(true,ok)','1','--node-settings',value],capture_output=True,text=True,timeout=5)
                assert result.returncode==2 and not result.stdout,(exe.name,value,result.returncode,result.stdout,result.stderr)
            result=subprocess.run([str(exe),'query(true,ok)','1','--node-settings','1234:3:open','--node-settings','1234:3:open'],capture_output=True,text=True,timeout=5)
            assert result.returncode==2 and not result.stdout
        return dict(rejected=len(inputs)*2+2)
    check('GS-005','Malformed and duplicate trusted metadata is rejected before query execution',malformed)
    with tempfile.TemporaryDirectory(prefix='gnu-node-settings-') as directory:
        directory=Path(directory)
        token=directory/'credential';token.write_text('node_settings_fixture_credential_'+'a'*40);token.chmod(0o600)
        shared=directory/'shared.pl';shared.write_text('shared_probe(K,V):-node_setting(K,V).')
        a=Node(2);b=None
        try:
            b=Node(4,token,shared)
            check('GS-006','Open HTTP node reports real settings despite forged ambient metadata',a.snapshot)
            check('GS-007','Authenticated HTTP node keeps credentials and per-owner quotas private',b.snapshot)
            check('GS-008','Private source helpers can read the current node settings',lambda:b.snapshot('private_probe','private_probe(K,V):-node_setting(K,V).'))
            check('GS-009','Shared source helpers read the serving node rather than their load context',lambda:b.snapshot('shared_probe'))
            def unavailable():
                keys=['timeout','rate_window_seconds','max_term_text_bytes','max_call_requests_per_window',
                      'load_uri_allowed_origins','max_sessions_per_principal','max_session_spawns_per_window',
                      'max_ws_actors_per_principal','max_ws_frame_bytes','max_ws_commands_per_window',
                      'shared_db_source','principal_policies','owner_token','token_file','max_owner_queries','max_budget_queries']
                return b.success('findall(K,(member(K,['+','.join(keys)+']),node_setting(K,_)),[]),'
                                 '\\+node_setting(42,_),\\+node_setting(bad(key),_),\\+node_setting(profile,[]),\\+node_setting(max_load_text_bytes,[])')
            check('GS-010','Unknown, private and unavailable family values fail without coercion',unavailable)
            def readonly():
                return b.success('findall(K-V,node_setting(K,V),Before),\\+node_setting(profile,forged),'
                                 '\\+node_setting(auth,open),\\+node_setting(max_inflight_calls,8),'
                                 'findall(K-V,node_setting(K,V),After),After==Before')
            check('GS-011','Bound mismatches cannot change metadata or select defaults',readonly)
            def denied():
                observations=[]
                for goal,source in [('iso_node_public(P,C,A,B)',''),('iso_install_node_settings(1,1,open,1)',''),
                                    ('assertz(iso_node_public(1,1,open,1))',''),('true','node_setting(profile,forged).'),
                                    ('true',':- dynamic iso_node_public/4.')]:
                    status,body=b.call(goal,**({'src_text':source} if source else {}))
                    assert status==200 and body.startswith('error(') and 'permission_error' in body,(goal,body)
                    observations.append(body)
                b.snapshot()
                return observations
            check('GS-012','Queries and source cannot inspect, initialize or replace private metadata',denied)
            def isolated():
                a.snapshot();b.snapshot();a.snapshot()
                status,body=b.call('node_setting(auth,private)',node_settings='1234:1:open')
                assert status==400,(status,body)
                b.snapshot()
                return dict(ports=[a.port,b.port],capacities=[2,4],forged_http_metadata_status=status)
            check('GS-013','Independent nodes and unknown HTTP parameters cannot override owner metadata',isolated)
            def paging():
                collected=[]
                for offset,more in [(0,True),(2,True),(4,False)]:
                    status,body=b.call('node_setting(K,V)',format='json',limit=2,offset=offset)
                    event=json.loads(body)
                    assert status==200 and event.get('type')=='success' and event.get('more') is more,(status,event)
                    assert len(event['data'])==2,event
                    collected.extend(event['data'])
                assert sorted(row['K'] for row in collected)==['auth','max_inflight_calls','max_load_text_bytes','profile','sandbox','url'],collected
                b.snapshot()
                return collected
            check('GS-014','A retained continuation keeps its serving-node settings across pages',paging)
        finally:
            a.close()
            if b:b.close()
    report=dict(suite='gnu-node-settings-0.1',results=ROWS,counts={s:sum(r['status']==s for r in ROWS) for s in ['pass','fail']})
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    return int(any(r['status']=='fail' for r in ROWS))


if __name__=='__main__':raise SystemExit(main())
