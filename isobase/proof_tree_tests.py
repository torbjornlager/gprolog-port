"""Example 18 over two genuine shared databases, shipping only prove/2."""
from pathlib import Path
import tempfile
from shared_db_tests import Node

from comparison_config import CONTRACT_DIR, verify_contract
verify_contract()
INTERPRETER = (CONTRACT_DIR/'proof-tree-interpreter.pl').read_text()

def check_inspection(node):
    cases = [
        ('clause(price(widget,X),B),B==list_price(widget,X)', '', 'success'),
        ('clause(list_price(widget,X),B)', 'list_price(widget,999).', 'success'),
        ('clause(list_price(widget,100),true)', 'list_price(widget,999).', 'failure'),
        ('inspect_price(X)', 'list_price(widget,999).', 'success'),
        ('clause(iso_native_clause(X,Y),B)', '', 'error'),
        ('clause(iso_shared_original_clause(X,Y),B)', '', 'error'),
        ("clause('$shared$price'(X,Y),B)", '', 'error'),
        ('clause(member(X,Y),B)', '', 'error'),
    ]
    for goal, source, expected in cases:
        result = node.call(goal, src_text=source)
        assert result['type'] == expected, (goal, result)
    assert node.call('inspect_price(X)', src_text='list_price(widget,999).')['data'] == [{'X':'100'}]

def check_proofs(root, leaf):
    uri = f'http://127.0.0.1:{root.port}'
    leaf_uri = f'http://127.0.0.1:{leaf.port}'
    # Use unification rather than printer spelling to check the full proof.
    for who in ['socrates', 'plato', 'aristotle']:
        tail = 'true' if who == 'socrates' else f"((human({who})@'{leaf_uri}')/true)"
        expected = f"((mortal({who})@'{uri}')/(human({who})/{tail}))"
        goal = f"prove(rpc('{uri}',mortal({who})),Proof),Proof={expected}"
        answer = root.call(goal, src_text=INTERPRETER)
        assert answer['type'] == 'success', (goal, answer)
    result = root.call(f"prove(rpc('{uri}',mortal(Who)),Proof)", src_text=INTERPRETER)
    assert [r['Who'] for r in result['data']] == ['socrates','plato','aristotle'], result

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='proof-shared-') as tmp:
        path = Path(tmp)/'leaf.pl'
        path.write_text('human(plato). human(aristotle).')
        leaf = Node(path)
        try:
            path = Path(tmp)/'root.pl'
            path.write_text(f"mortal(X):-human(X). human(socrates). human(X):-rpc('http://127.0.0.1:{leaf.port}',human(X)).")
            root = Node(path)
            try: check_proofs(root, leaf)
            finally: root.close()
        finally: leaf.close()
    print('PASS distributed shared proof trees: exact example 18 interpreter, two databases, three complete proofs')
