"""Executable ISOBASE contract samples against the live SWI demonstrator.
Term variants compare structurally. Error contexts/messages are intentionally
reported as a separate compatibility gap, not hidden by string normalization.
"""
import http.client
import json
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import tempfile
import urllib.parse

ROOT=Path(__file__).resolve().parent
SWI=shutil.which('swipl') or '/Applications/SWI-Prolog.app/Contents/MacOS/swipl'
CASES=[]
def case(family,goal,template='ok',source='',**options):
    CASES.append(dict(family=family,goal=goal,template=template,src_text=source,**options))

for goal in ['true','fail','false','once((true;true))','catch(throw(ball),ball,true)',
             'call(true)','call(=,a,a)','(fail->fail;true)','\\+ fail']:
    case('control',goal)
case('control','(X=a;X=b),!','X')
case('control','G=(X=ok),G','X')
case('control','call_nth((X=a;X=b;X=c),N)','X-N')
case('control','call_nth((X=a;X=b;X=c),2)','X')
case('control','call_nth((X=a;throw(later)),1)','X')
case('control','call_nth(member(X,[a,b]),N),call_nth(member(Y,[c,d]),M)','r(X,N,Y,M)')
case('control','call_nth(member(X,[a,b]),3)')
case('control','time((X=a;X=b))','X')
case('control','time(fail)')
for goal in ['var(X)','atom(a)','integer(1)','float(1.0)','atomic(a)','compound(f(a))',
    'nonvar(a)','number(1)','callable(f(a))','ground(f(a))','acyclic_term(f(X,X))',
    'unify_with_occurs_check(X,f(X))','subsumes_term(f(X),f(a))','a\\=b','a@<b']:
    case('terms',goal)
for goal,template in [('X=Y','pair(X,Y)'),('functor(X,f,2)','X'),('arg(N,f(a,b),X)','N-X'),
    ('X=..[f,a,b]','X'),('copy_term(f(A,A),X)','X'),('term_variables(f(A,B,A),X)','X'),
    ('sort([b,a,a],X)','X'),('keysort([b-1,a-2,a-3],X)','X'),('compare(X,a,b)','X')]:
    case('terms',goal,template)
for expression in ['1+2','7//3','-7 rem 3','-7 mod 3','-7 div 3','abs(-2)','sign(-2)',
    'float(2)','floor(2.8)','floor(2)','ceiling(-2.8)','truncate(-2.8)','round(2.5)',
    'float_integer_part(2.8)','float_integer_part(2)','float_fractional_part(2)','float_fractional_part(2.5)','2**3','2^3','max(2,3)',
    'min(2,3)','sqrt(4)','sin(0)','cos(0)','atan(0)','exp(0)','log(1)','asin(0)',
    'acos(1)','atan2(0,1)','tan(0)','1<<4','16>>2','6 /\\ 3','6 \\/ 3','xor(6,3)']:
    case('arithmetic',f'X is {expression}','X')
for goal,template in [('atom_concat(a,b,X)','X'),("sub_atom(abc,Before,1,After,X)",'r(Before,After,X)'),
    ('atom_chars(ab,X)','X'),('atom_codes(ab,X)','X'),('char_code(a,X)','X'),
    ('number_chars(12,X)','X'),('number_codes(12,X)','X')]:case('atoms',goal,template)
for name,base in [('nth0',0),('nth1',1)]:
    case('prologue',f'{name}(N,[a,b,c],X)','N-X')
    case('prologue',f'{name}({base+1},[a,b,c],X)','X')
    case('prologue',f'{name}({base-1},[a,b,c],X)','X')
    case('prologue',f'{name}(N,[a,b,c],X,R)','r(N,X,R)')
    case('prologue',f'{name}({base+1},L,x,[a,b])','L')
for goal,template in [('member(X,[a,b])','X'),('append(A,B,[a,b])','A-B'),
    ('length(L,2)','L'),('between(1,3,X)','X'),('select(X,[a,b],R)','X-R'),('succ(X,2)','X')]:
    case('prologue',goal,template)
for goal,template in [('maplist(=(a),[a,a])','ok'),('maplist(=,[a,b],X)','X'),
    ('foldl(plus,[1,2,3],0,X)','X'),('findall(X,member(X,[a,b]),L)','L'),
    ('bagof(X,member(K-X,[a-1,b-2,a-3]),L)','K-L'),
    ('setof(X,K^member(K-X,[a-1,b-2,a-1]),L)','L')]:
    case('higher_order',goal,template,'plus(X,Y,Z):-Z is X+Y.' if 'foldl' in goal else '')
case('source','phrase(word,X)','X','word --> [a], [b].')
case('source','p(X)','X','p(a). p(b).')
case('source','p(X)','X',':- dynamic p/1.')
case('source','clause(p(X),B)','X-B','p(X):-member(X,[a,b]).')
case('source','clause(price(X,Y),B)','r(X,Y,B)')
case('source','price(widget,X)','X','list_price(widget,999).')
case('source','list_price(widget,X)','X','list_price(widget,999).')
case('guard_regression','true','ok','unsafe :- time(halt).')
case('rejection','true','ok','unsafe :- call_nth(halt,1).')
for goal in ['halt','assertz(p(a))','write(a)',"open('/tmp/forbidden',write,S)",
             'spawn(true,P)','self(P)','iso_native_shared(F,N,I)',
             'time(halt)','G=halt,time(G)']:
    case('rejection',goal)
case('rejection','call_nth(halt,1)')
case('rejection','G=halt,call_nth(G,1)')
case('guard_regression',"yield(1,M,[on_timeout(halt)])")

# Compare catchable formal error terms; implementation-specific contexts are
# deliberately excluded by the goal itself, as portable Prolog code can do.
for goal in ['arg(a,f(x),X)','arg(-1,f(x),X)','arg(1,x,X)',
    'functor(X,f,-1)','functor(X,42,1)','length([a|b],N)','length(L,-1)',
    'succ(-1,X)','sort(42,X)','keysort([a],X)','atom_length(42,X)',
    'number_codes(a,X)','char_code(ab,X)','nth0(-1,[a],X,R)',
    'nth1(0,[a],X,R)','nth1(a,[a],X)','call_nth(true,0)',
    'call_nth(true,a)','X is 1//0','X is sqrt(-1)','X is missing(1)',
    'X is floor(a)','X is float_integer_part(2)','X is float_fractional_part(2)']:
    case('errors',f'catch(({goal}),error(Form,_),true)','Form')

from mode_cases import add_cases
add_cases(case)
from boundary_cases import add_cases as add_boundary_cases
add_boundary_cases(case)
from predicate_mode_cases import add_cases as add_predicate_cases
add_predicate_cases(case)
from conversion_mode_cases import add_cases as add_conversion_cases
add_conversion_cases(case)
from list_mode_cases import add_cases as add_list_cases
add_list_cases(case)
from numeric_mode_cases import add_cases as add_numeric_cases
add_numeric_cases(case)
from term_mode_cases import add_cases as add_term_cases
add_term_cases(case)
from dcg_mode_cases import add_cases as add_dcg_cases
add_dcg_cases(case)
from higher_arithmetic_cases import add_cases as add_higher_arithmetic_cases
add_higher_arithmetic_cases(case)
from rpc_option_cases import add_cases as add_rpc_option_cases
add_rpc_option_cases(case)
from rpc_boundary_cases import add_cases as add_rpc_boundary_cases
add_rpc_boundary_cases(case)

# Host capabilities intentionally differ from SWI; verify the GNU declaration.
CAPABILITIES="runtime_property(implementation(gnu_native)),runtime_property(persistent(false)),runtime_property(inbound_addressable(false)),runtime_property(dom(false)),runtime_property(actor_isolation(os_process)),runtime_property(hard_termination(true)),findall(P,runtime_property(P),Ps),length(Ps,6)"

def main():
    from rpc_source_tests import SourceServer
    processes=[];results=[]
    source_server=SourceServer()
    with tempfile.TemporaryDirectory(prefix='isobase-contract-') as d, tempfile.TemporaryFile(mode='w+') as log:
        try:
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));sp=sock.getsockname()[1]
            shared=ROOT/'shared-example.pl'
            # This disposable reference runs the entire corpus in one window.
            request_budget=max(1000,2*len(CASES))
            goal=f"node:node({sp},[profile(isobase),auth(open),max_call_requests_per_window({request_budget}),ip('127.0.0.1'),load_shared_db_file('{shared}')]),writeln(ready),flush_output,thread_get_message(stop)"
            swi=subprocess.Popen([SWI,'-q','-s','/Users/lager/trinity-demonstrator/load.pl','-g',goal],stdout=subprocess.PIPE,stderr=log,text=True);processes.append(swi)
            assert select.select([swi.stdout],[],[],15)[0],'SWI startup timeout'
            assert swi.stdout.readline().strip()=='ready'
            executable=os.environ.get('ISO_COMPILED_NODE','./isobase-node')
            argv=[executable,'--port','0','--time-ms','3000']
            if 'ISO_COMPILED_NODE' not in os.environ:argv+=['--shared-db',str(shared)]
            node=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=log,text=True);processes.append(node)
            gp=json.loads(node.stdout.readline())['port']
            def request(port,params):
                c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                c.request('GET','/call?'+urllib.parse.urlencode(params))
                r=c.getresponse();body=r.read().decode();c.close()
                assert r.status==200,(r.status,body)
                return body
            assert request(gp,dict(goal=CAPABILITIES,template='ok',format='prolog')).strip()=='success([ok],false).'
            for row in CASES:
                params={k:v for k,v in row.items() if k not in ('family','expected_gnu')};params.update(format='prolog');params.setdefault('limit',100)
                # Both clients use the same disposable target for RPC option comparisons.
                params={k:(v.replace('__RPC_TARGET__',f'http://127.0.0.1:{gp}').replace('__RPC_PORT__',str(gp)).replace('__SOURCE_TARGET__',source_server.uri) if isinstance(v,str) else v) for k,v in params.items()}
                try:
                    reference=request(sp,params) if row['family']!='guard_regression' else 'not_run_reference_guard_gap'
                    actual=request(gp,params)
                except Exception:
                    print('Request failed:',params,flush=True)
                    log.seek(0);print(log.read()[-4000:]);raise
                # Rejection messages differ by host but neither may execute.
                if row['family']=='guard_regression':same=actual.startswith('error(')
                elif row['family']=='rejection':same=actual.startswith('error(') and reference.startswith('error(')
                else:
                    expected=row.get('expected_gnu',reference)
                    probe=subprocess.run([SWI,'-q','-g','read(A),read(B),(A=@=B->halt;halt(1))'],input=expected+'\n'+actual,capture_output=True,text=True,timeout=3)
                    same=probe.returncode==0
                results.append(dict(**row,pass_=same,reference=reference,actual=actual))
            output=ROOT/'conformance-results.json';output.write_text(json.dumps(results,indent=2)+'\n')
            failures=[r for r in results if not r['pass_']]
            guards=sum(r['family']=='guard_regression' for r in results)
            boundaries=sum('expected_gnu' in r for r in results)
            print(f"Conformance samples: {len(results)-len(failures)}/{len(results)} passed ({guards} GNU-only guard checks; {boundaries} explicit host boundaries; remaining cases compared with SWI)")
            for row in failures:print(json.dumps(row))
            assert not failures,f'{len(failures)} contract differences; see {output}'
        finally:
            source_server.close()
            for p in processes:p.terminate()
            for p in processes:
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()

if __name__=='__main__':main()
