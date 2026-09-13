"""Positive semantic checks and negative execution-policy regressions."""
from source_tests import query, answers

def allowed(goal, template='X', source=''):
    return answers(source, goal, template)

def denied(goal, source=''):
    events = query(source, goal, 'ok')
    assert events and events[-1]['type'] == 'error', (goal,events)
    assert 'permission_error' in events[-1]['term'], (goal,events)

assert allowed('G=(X=ok),call(G)') == ['ok']
assert allowed('call(=,X,ok)') == ['ok']
assert allowed('G=(X=ok),G') == ['ok']
assert allowed('findall(N,between(1,3,N),X)') == ["'.'(1,'.'(2,'.'(3,[])))"]
assert allowed('bagof(N,Y^member(Y-N,[a-1,b-2]),X)') == ["'.'(1,'.'(2,[]))"]
assert allowed('setof(N,member(N,[2,1,2]),X)') == ["'.'(1,'.'(2,[]))"]
assert allowed('G=Y^member(Y-N,[a-1,b-2]),bagof(N,G,X)') == ["'.'(1,'.'(2,[]))"]
assert allowed('catch(throw(oops),oops,X=handled)') == ['handled']
assert allowed('once((X=1;X=2))') == ['1']
assert allowed('(fail->X=no;X=yes)') == ['yes']
assert allowed('call_nth(maplist(=(a),L),3),L==[a,a]', template='ok') == ['ok']
assert allowed('maplist(=,[a,b],X)') == ["'.'(a,'.'(b,[]))"]
assert allowed('maplist(plus(2),[1,2],X)', source='plus(A,B,C):-C is A+B.') == ["'.'(3,'.'(4,[]))"]
assert allowed('foldl(add,[1,2,3],0,X)', source='add(A,B,C):-C is A+B.') == ['6']
assert allowed('phrase(([a],{X=ok}),[a])') == ['ok']
assert allowed('G=([a],{X=ok}),phrase(G,[a])') == ['ok']
# Clause introspection returns submitted bodies, not inserted guard predicates.
assert allowed('clause(p(X),B),B==call(X)', 'ok', 'p(X):-call(X).') == ['ok']
# Clause cut prunes the second clause, while call(!) remains opaque.
assert allowed('p(X)', source='p(X):-(X=one;X=two),!. p(three).') == ['one']
assert allowed('p(X)', source='p(X):-(X=one;X=two),call(!).') == ['one','two']

for goal in [
    'halt', 'write(hello)', 'read(X)', 'assertz(x)', 'retractall(x)',
    'abolish(x/0)', 'shell(true)', 'consult(missing)', 'spawn(true,X)',
    'send(x,y)', 'receive(x)', 'iso_alloc(1)', 'iso_execute(true)',
    'iso_owned(X,Y)', "'$call'(true)", 'user:halt',
    'G=halt,call(G)', 'G=halt,G', 'G=..[halt],call(G)',
    'call(call,halt)', 'findall(X,halt,Xs)', 'bagof(X,halt,Xs)',
    'setof(X,halt,Xs)', 'catch(throw(oops),E,halt)',
    'phrase({halt},[])', 'G={halt},phrase(G,[])',
    'maplist(halt,[0])', 'foldl(halt,[1],0,X)',
    'clause(iso_query(X,Y),B)', 'clause(member(X,Y),B)',
]:
    denied(goal)
for body in ['halt','call(halt)','findall(X,halt,L)','phrase({halt},[])']:
    denied('p', 'p :- '+body+'.')
denied('run(halt)', 'run(G) :- G.')
denied('run(halt)', 'run(G) :- call(G).')
denied('phrase(bad,[])', 'bad --> {halt}.')
denied('true', 'unused :- halt.')
assert 'instantiation_error' in query('', 'call(X)')[0]['term']
assert 'instantiation_error' in query('', 'X')[0]['term']
assert 'cyclic_term' in query('', 'X=f(X)')[0]['term']

# List-spine identity checks ignore cyclic elements and detect cycles of
# different periods, including a finite prefix leading into a cycle.
assert allowed('X=f(X),length([X,X],N)',template='N') == ['2']
assert allowed('(length([a|N],N)->X=bad;X=ok)') == ['ok']
for cycle in ['L=[a|L]', 'L=[a,b,c|L]', 'T=[a,b|T],length(P,100),append(P,T,L)']:
    assert allowed(cycle+',catch(length(L,_),error(representation_error(cyclic_term),_),X=ok)') == ['ok']
assert allowed('C=[97|C],catch(atom_codes(_,C),error(representation_error(cyclic_term),_),X=ok)') == ['ok']
print('PASS policy: control semantics, meta-calls, higher-order calls, DCGs, introspection and denied execution')

# Infinite ranges stop with a catchable error at the native integer boundary.
assert allowed('once(between(1152921504606846975,inf,X))') == ['1152921504606846975']
assert allowed('catch((between(1152921504606846975,inf,N),fail),error(evaluation_error(int_overflow),_),X=ok)') == ['ok']
for goal in ['nth0(X,[],_)','nth1(X,[],_,_)','succ(X,_)','succ(_,X)',
             'between(X,2,_)','between(1,X,_)','between(1,2,X)']:
    assert allowed('X=f(X),catch(('+goal+'),error(representation_error(cyclic_term),_),Y=ok)',template='Y') == ['ok']

# Float output is read back exactly, including the smallest subnormal and -0.
for value in ['0.1','-0.0','1.2345678901234567','4.9406564584124654e-324']:
    assert allowed('number_codes('+value+',C),number_codes(N,C),N==('+value+'),X=ok') == ['ok']
assert allowed('number_codes(0.1,[48,46,X])') == ['49']

# Sorting rejects cyclic spines with a finite catchable error.
assert allowed('L=[a-1|L],catch(keysort(L,_),error(representation_error(cyclic_term),_),X=ok)') == ['ok']

# DCG normalization must never erase or execute embedded forbidden goals.
assert allowed('phrase(({},[a]),X)') == ["'.'(a,[])"]
assert allowed('p(X)',source='p(L):-phrase(word,L). word --> {},[a].') == ["'.'(a,[])"]
for goal in ['phrase({write(a)},[])','G={write(a)},phrase(G,[])','phrase(({}, {write(a)}),[])']:
    denied(goal)

# Arithmetic order and signed-zero quadrants cross the foreign boundary.
assert allowed('X is round(-1.5)') == ['-2']
assert allowed('X is round(-0.49999999999999994)') == ['0']
assert allowed('X is atan2(0,0)') == ['0.0']
assert allowed('X is atan2(0.0,-0.0),X>3',template='ok') == ['ok']
assert allowed('X is atan2(-0.0,-0.0),X< -3',template='ok') == ['ok']
assert allowed('catch(X is Y+(1/0),error(evaluation_error(zero_divisor),_),R=ok)',template='R') == ['ok']
