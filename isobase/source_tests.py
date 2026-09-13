import os
"""Submitted-source execution tests, with a fresh process per query."""
import json
import subprocess
import tempfile
from pathlib import Path

def query(source, goal, template='X', limit=2, commands='next\n' * 20):
    with tempfile.TemporaryDirectory(prefix='isobase-source-') as d:
        path = Path(d) / 'source.pl'
        path.write_text(source)
        p = subprocess.run([os.environ.get('ISO_WORKER','./query-worker'), f'query(({goal}),({template}))',
                            str(limit), '--source', str(path)],
                           input=commands, text=True, capture_output=True, timeout=10)
    assert p.returncode == 0 and not p.stderr, (p.returncode, p.stdout, p.stderr)
    return [json.loads(line) for line in p.stdout.splitlines()]

def answers(source, goal, template='X'):
    events = query(source, goal, template)
    assert all(e['type'] == 'success' for e in events), events
    return [a for e in events for a in e['answers']]

def test_source():
    # Compound phrase bodies work in GNU; the SWI node currently rejects this
    # despite accepting the equivalent source DCG. Keep an independent oracle.
    assert answers('','phrase(([a],{X=b},[X]),L),L==[a,b]','ok') == ['ok']
    assert answers('colour(red). colour(green). colour(blue).', 'colour(X)') == ['red','green','blue']
    assert answers('edge(a,b). edge(b,c). path(A,B):-edge(A,B). '
                   'path(A,B):-edge(A,C),path(C,B).', 'path(a,X)') == ['b','c']
    assert answers('pick(X) :- (X=one;X=two), !.', 'pick(X)') == ['one']
    assert answers('same(X,pair(X,X)).', 'same(Y,X),Y=hello') == ['pair(hello,hello)']
    assert answers('word --> [a], [b].', 'phrase(word,[a,b]),X=ok') == ['ok']
    assert answers(':- dynamic item/1. :- multifile item/1. '
                   ':- discontiguous item/1. item(one). item(two).', 'item(X)') == ['one','two']
    assert answers('% a comment\nlabel(\'hello world\').', 'label(X)') == ["'hello world'"]
    assert query('p :- throw(from_source).', 'p')[0]['term'] == 'from_source'
    assert query('p :- fail.', 'p') == [{'type':'failure'}]
    assert query(':- dynamic empty/1.', 'empty(X)') == [{'type':'failure'}]
    assert answers(':- dynamic a/1,b/1. a(one). b(two).', '(a(X);b(X))') == ['one','two']
    assert answers('item(one). :- dynamic item/1.', 'item(X)') == ['one']
    # Missing predicate in a different process confirms that source is not shared.
    assert 'permission_error' in query('', 'colour(X)')[0]['term']
    for source in [
        'broken(.',
        ':- initialization(halt).',
        ':- halt.',
        ':- op(500, xfx, custom).',
        'iso_query(_,_) :- halt.',
        'member(_,_) :- halt.',
        'term_expansion(X,X).',
        'goal_expansion(X,X).',
        "'$hidden'.",
        '42.',
        'X :- true.',
        ':- dynamic X.',
    ]:
        result = query(source, 'true', 'ok')
        assert result[0]['type'] == 'error', (source, result)
    assert query('x.' + ' ' * (1024*1024), 'x')[0]['type'] == 'error'
    print('PASS source facts, recursion, cuts, sharing, DCGs, declarations, errors, isolation and size limit')

if __name__ == '__main__':
    test_source()
