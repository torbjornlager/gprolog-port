"""Web Prolog text reads as Unicode character atoms at every source boundary."""
import json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
count=0
def check(goal,source=None,shared=False):
    global count
    with tempfile.TemporaryDirectory() as d:
        env=dict(os.environ);args=[str(ROOT/'query-worker'),'query(('+goal+'),ok)','10']
        if source is not None:
            p=Path(d)/'source.pl';p.write_text(source)
            if shared:env['ISO_SHARED_DB']=str(p)
            else:args+=['--source',str(p)]
        r=subprocess.run(args,input='',text=True,capture_output=True,env=env,timeout=10)
        assert r.returncode==0 and not r.stderr,(goal,r.returncode,r.stderr)
        data=json.loads(r.stdout)
        assert data=={'type':'success','answers':['ok'],'more':False},(goal,data)
        count+=1
for goal in [
    'A="apa",A==[a,p,a]', 'A="",A==[]',
    "A=\"å😀\",A==['å','😀'],length(A,2)",
    "A=\"a\\n\\t\",A==[a,'\\n','\\t']",
    'A=[97,112,97],A==[97,112,97]',
    'A=[X,X],var(X),A=[Y,Z],Y==Z',
    'A=[x|T],var(T)', 'A=["apa",X],var(X),A=[[a,p,a],X]',
    'phrase("apa",L),L==[a,p,a]',
    'atom_codes(apa,[97,112,97]),atom_chars(apa,[a,p,a])',
]:check(goal)
for shared in [False,True]:
    check('word(L),L==[a,p,a]', 'word("apa").',shared)
    check("word(L),L==['å','😀']", 'word("å😀").',shared)
    check('phrase(word,L),L==[a,p,a]', 'word --> "apa".',shared)
    check('word(X,Y),var(X),X==Y', 'word(X,X):-"apa"=[a,p,a].',shared)
    check('word(L),L==[a,p,a]', '% "ignored"\n/* "ignored too" */ word("apa").',shared)
print(f'PASS {count} character-reader assertions: goals, Unicode, source, shared source, DCGs and variable sharing')
