"""Independent contract 0.2.0 checks; no comparison runtime supplies the answers."""
from source_tests import answers

GOALS = [
    'X is 2**3,float(X),X=:=8.0',
    'X is 2**60,float(X),X=:=1152921504606846976.0',
    'X is (-2)**3,float(X),X=:= -8.0',
    'X is 2**(-1),float(X),X=:=0.5',
    'X is 2.0**3,float(X),X=:=8.0',
    'X is 2**0,float(X),X=:=1.0',
    'X is 2**3+1,float(X),X=:=9.0',
    'X is 2^3,integer(X),X=:=8',
    "catch((X is 0**(-1),R=unexpected),error(evaluation_error(zero_divisor),_),R=ok),R==ok",
    "number_chars(N,['1','2']),N==12",
    "number_chars(12,L),L==['1','2']",
    "number_chars(12,['1',C]),C=='2'",
    "number_chars(12,['1'|T]),T==['2']",
    "number_chars(N,[-,' ','1']),N== -1",
    'number_codes(N,[49,50]),N==12',
    'number_codes(12,L),L==[49,50]',
    'number_codes(12,[49,C]),C==50',
    "\+ number_chars(12,['1','3'])",
    '\+ number_codes(12,[49,51])',
]
# Catch the formal error only; a success or silent failure cannot pass.
for number in ['N','1']:
    for value in ['0','49',"ab"]:
        GOALS.append(f'catch((number_chars({number},[{value}]),R=unexpected),error(type_error(character,{value}),_),R=ok),R==ok')
    for value in ["'1'","ab"]:
        GOALS.append(f'catch((number_codes({number},[{value}]),R=unexpected),error(type_error(character_code,{value}),_),R=ok),R==ok')
GOALS += [
    "catch((number_chars(N,['1',50]),R=unexpected),error(type_error(character,50),_),R=ok),R==ok",
    "catch((number_codes(N,[49,'2']),R=unexpected),error(type_error(character_code,'2'),_),R=ok),R==ok",
    "functor(L,'.',2),arg(1,L,49),arg(2,L,L),catch(number_chars(_,L),error(representation_error(cyclic_term),_),R=ok),R==ok",
]
# A real source predicate also exercises guarded rewriting during compilation.
SOURCE='\n'.join(f'numeric_contract({i}) :- {goal}.' for i,goal in enumerate(GOALS))+'\n'

def check_node(node):
    for i in range(len(GOALS)):
        result=node.call(f'numeric_contract({i}),Verified=ok')
        assert result['type']=='success' and result['data']==[{'Verified':'ok'}],(i,GOALS[i],result)

def main():
    for i,goal in enumerate(GOALS):
        assert answers('',goal,'ok')==['ok'],goal
        assert answers(SOURCE,f'numeric_contract({i})','ok')==['ok'],goal
    print(f'PASS {len(GOALS)} numeric requirements in direct and submitted-source execution')

if __name__=='__main__':main()
