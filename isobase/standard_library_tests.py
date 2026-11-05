"""The shared Appendix B library manifest through fresh guarded query workers."""
import json
from pathlib import Path
from source_tests import answers,query
pack=json.loads(Path(__file__).with_name('standard_library_cases.json').read_text())
for case in pack['cases']:
    actual=answers(pack['source'],'('+case['goal']+'),LibraryCheck=passed','LibraryCheck')
    assert actual==['passed'],(case['id'],actual)
for goal in [
    'G=current_prolog_flag,maplist(G,[bounded],[_])',
    'G=current_prolog_flag(bounded,_),countall(G,_)',
    'G=current_prolog_flag(bounded,_),forall(true,G)',
    'G=current_prolog_flag(bounded,_),call_nth(G,1)',
    'foldl(open,[no_such_file],read,_)',
]:
    event=query('',goal,'ok')[0]
    assert event['type']=='error' and 'permission_error' in event['term'],(goal,event)
for source in ['memberchk(_, _).','forall(_,_).','countall(_,0).',
               'maplist(_,_,_,_,_,_,_,_).','foldl(_,_,_,_,_,_).']:
    event=query(source,'true','ok')[0]
    assert event['type']=='error' and 'permission_error' in event['term'],(source,event)
print('PASS',len(pack['cases']),'shared library cases, 5 callback and 5 source-override controls')
