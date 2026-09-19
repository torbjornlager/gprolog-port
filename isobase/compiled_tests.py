"""Native shared code must retain snapshot-mode policy and query semantics."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from build_shared import build,fix_arm64_comparisons
from shared_db_tests import SOURCE,Node
from proof_tree_tests import check_inspection, check_proofs

ROOT=Path(__file__).resolve().parent
extra='''
convert_number(N,C) :- number_chars(N,C).
round_value(A,R) :- R is round(A).
zero_angle(R) :- R is atan2(0,0).
empty_dcg --> {},[a].
dynamic_dcg --> {G=[a,b]},G.
collect_terms(L) :- findall(X,member(X,[a,b]),L).
variables_of(T,L) :- term_variables(T,L).
term_parts(T,L) :- T=..L.
sort_pairs(L,R) :- keysort(L,R).
list_range(N) :- between(1,inf,N).
list_successor(A,B) :- succ(A,B).
list_remove(N,L,E,R) :- nth1(N,L,E,R).
mortal(X):-human(X).
:- dynamic vacant/1.
:- multifile interleaved/1.
interleaved(a).
breaker(ok).
interleaved(b).
choice(X) :- (X=a;X=b),!.
choice(c).
hidden_callback(X) :- yield(999,X,[on_timeout(list_price(widget,X))]).
'''
with tempfile.TemporaryDirectory(prefix='compiled-tests-') as temp:
    root=Path(temp);source=root/'source.pl';source.write_text(SOURCE+extra)
    # Integer-index regression for the pinned ARM64 CMP immediate bug.
    values=[-922337203685477000,-8192,-4160,-1,0,4095,4096,4160,4224,8192,9984,16777216,922337203685477000]
    with source.open('a') as f:
        for value in values:f.write(f'indexed({value}).\n')
    bundle=build(source,root/'native')
    asm=root/'immediates.s'
    asm.write_text('\n'.join(f'\tcmp x0, #{v}' for v in values)+'\n\tret\n')
    fixed=fix_arm64_comparisons(asm)
    assert fixed>0 and asm.read_text().endswith('\n\tret\n')
    if __import__('platform').machine() in ('arm64','aarch64'):
        subprocess.run(['cc','-c',str(asm),'-o',str(root/'immediates.o')],check=True)
    interpreted=Node(source)
    os.environ['ISO_NODE']=str(bundle/'isobase-node')
    # The native node runs without --shared-db; the bundled executable owns it.
    class Native(Node):
        def __init__(self):
            self.p=subprocess.Popen([str(bundle/'isobase-node'),'--port','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            self.port=json.loads(self.p.stdout.readline())['port']
    native=Native()
    shadow='list_price(widget,999). list_price(gadget,999). word --> [local].'
    cases=[('round_value(-1.5,R)',{}),('round_value(-0.49999999999999994,R)',{}),
           ('zero_angle(R)',{}),
           ('phrase(empty_dcg,L)',{}),('phrase(dynamic_dcg,L)',{}),
           ('collect_terms(bad)',{}),('collect_terms(L)',{}),
           ('variables_of(f(X),bad)',{}),('term_parts(f(a),[f|bad])',{}),
           ('sort_pairs([a|T],R)',{}),
           ('convert_number(0.1,L)',{}),
           ("convert_number(N,['+','1','2'])",{}),
           ("atom_codes(A,[49,54,39,102,102]),atom_chars(A,L),convert_number(N,L)",{}),
           ('list_range(N)',{'limit':3}),('list_successor(0,bad)',{}),
           ('list_remove(N,[a,b],E,R)',{}),('list_remove(2,L,x,[a,b])',{}),
           ('convert_number(N,[49,101,51])',{}),('convert_number(12,[X|bad])',{}),('unicode_label(A),atom_chars(A,C),atom_length(A,N)',{}),('clause(unicode_label(A),true)',{}),('price(widget,X)',{}),('list_price(widget,X)',{'src_text':shadow}),
           ('price(widget,X)',{'src_text':shadow}),('phrase(word,X)',{'src_text':shadow}),
           ('shared_phrase(X)',{'src_text':shadow}),('path(a,X)',{}),
           ('choice(X)',{}),('interleaved(X)',{}),('vacant(X)',{}),
           ('price(widget,X)',{'src_text':'price(_,42).'}),
           ('list_price(widget,X)',{'src_text':':- dynamic list_price/2.'}),
           ('list_price(widget,X)',{'src_text':':- dynamic list_price/2. list_price(widget,8).'}),
           ('clause(local(X),B),B==price(widget,X)',{'src_text':'local(X):-price(widget,X).'}),
           ('clause(price(X,Y),B)',{}),('clause(vacant(X),B)',{}),
           ('clause(indexed(X),true)',{}),('clause(choice(X),B)',{}),("'$shared$price'(widget,X)",{}),
           ('assertz(list_price(widget,7))',{}),('retractall(list_price(_,_))',{}),
           ('iso_native_shared(F,N,I)',{}),('iso_shared_mode(M)',{}),
           ('hidden_callback(X)',{'src_text':shadow}),
           ('human(X)',{'limit':1}),('human(X)',{'offset':1,'limit':2})]
    for name in ['via_call','via_variable','via_apply']:cases.append((f'{name}(widget,X)',{'src_text':shadow}))
    for name in ['via_map','via_bag']:cases.append((f'{name}(X)',{'src_text':shadow}))
    try:
        check_inspection(native)
        check_inspection(interpreted)
        for value in values:
            assert native.call(f'indexed({value})')['type']=='success',value
        assert native.call('indexed(4161)')['type']=='failure'
        expected=[{'X':str(v)} for v in values]
        assert native.call('indexed(X)')['data']==expected
        for goal,params in cases:
            a=interpreted.call(goal,**params);b=native.call(goal,**params)
            assert a==b,(goal,a,b)
        proof_source=root/'proof-root.pl'
        # Use a separate compiled leaf with precisely the example's human facts.
        leaf_source=root/'proof-leaf.pl';leaf_source.write_text('human(plato). human(aristotle).')
        original_bundle=bundle
        bundle=build(leaf_source,root/'proof-leaf')
        leaf=Native()
        try:
            proof_source.write_text(f"mortal(X):-human(X). human(socrates). human(X):-rpc('http://127.0.0.1:{leaf.port}',human(X)).")
            bundle=build(proof_source,root/'proof-root')
            proof_node=Native()
            try: check_proofs(proof_node,leaf)
            finally: proof_node.close()
        finally: leaf.close();bundle=original_bundle
        # All sources are already compiled: changing/deleting build inputs has no effect.
        source.write_text('human(replaced).');source.unlink()
        (bundle/'shared-source.pl').unlink();(bundle/'shared-native.pl').unlink()
        assert native.call('price(widget,X)')['data']==[{'X':'100'}]
        assert native.call('human(X)')['data']==[{'X':'socrates'},{'X':'plato'},{'X':'aristotle'}]
        # Native/runtime built-in calls must still be policy checked remotely.
        u=f'http://127.0.0.1:{native.port}'
        assert native.call(f"rpc('{u}',unicode_label(A)),atom_codes(A,C)")['data'][0]['C']=='[26481,20140,128512]'
        assert native.call(f"rpc('{u}',label(A),[src_predicates([label/1])]),atom_codes(A,C)",src_text="label('東京😀').")['data'][0]['C']=='[26481,20140,128512]'
        assert interpreted.call(f"rpc('{u}',price(widget,X))")['data']==[{'X':'100'}]
        assert native.call(f"rpc('{u}',q(X),[src_predicates([q/1])])",src_text='q(a). q(b).')['data']==[{'X':'a'},{'X':'b'}]
        assert native.call(f"promise('{u}',price(widget,X),R,[template(X)]),yield(R,success([Y],false))")['data'][0]['Y']=='100'
        from rpc_source_tests import SourceServer
        fixture=SourceServer()
        try:
            assert native.call(f"rpc('{u}',p(X),[src_uri('{fixture.uri}/source/')])")['data']==[{'X':'slash'}]
            for options in ['timeout(bad),src_text(42)', 'src_text(42),http_timeout(bad)', 'http_timeout(none)']:
                goal=f"catch(rpc('{u}',true,[{options}]),error(E,_),true)"
                assert native.call(goal)==interpreted.call(goal)
        finally:fixture.close()
        # Mixing an interpreted snapshot with a compiled bundle must fail at startup.
        source.write_text('other(x).')
        result=subprocess.run([str(bundle/'isobase-node'),'--port','0','--shared-db',str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode!=0 and not result.stdout and 'cannot_be_overlaid' in result.stderr,result
        for test in ['tests.py','source_tests.py','policy_tests.py','rpc_source_tests.py']:
            env=dict(os.environ,ISO_WORKER=str(bundle/'query-worker'))
            subprocess.run(['python3',test],check=True,env=env,cwd=ROOT)
        env=dict(os.environ,ISO_NODE=str(bundle/'isobase-node'),ISO_SUPERVISOR=str(bundle/'query-supervisor'))
        subprocess.run(['python3','memory_tests.py'],check=True,env=env,cwd=ROOT)
        subprocess.run(['python3','memory_tests.py','--total-memory-mb','96'],check=True,env=env,cwd=ROOT)
    finally:
        native.close();interpreted.close();os.environ.pop('ISO_NODE',None)
    for index,bad in enumerate(['bad(.','p :- halt.',':- initialization(halt).','p :- missing.',
            "'$shared$hack'.",'iso_native_shared(a,0,a).','rpc(a,b).','x.\0']):
        source.write_text(bad);output=root/f'bad{index}'
        result=subprocess.run(['python3','build_shared.py',str(source),'--output',str(output)],capture_output=True,text=True,timeout=10)
        assert result.returncode!=0 and not output.exists(),(bad,result.stdout,result.stderr)
    print(f'PASS compiled shared DB: {len(cases)} paired cases, native RPC, private source, immutable build and rejected unsafe inputs')
