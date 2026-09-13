"""Bounded relational, higher-order and DCG contract cases."""
def add_cases(case):
    for n in range(1,5):
        lists=','.join(['[a,b]']*n)
        args=','.join(['X']*n)
        case('higher_order_modes',f'maplist(same,{lists})','ok',f'same({args}).')
        lists=','.join(['[a,b]']*(n-1)+['L'])
        case('higher_order_modes',f'maplist(same,{lists})','L',f'same({args}).',limit=3)
    for n in range(1,5):
        lists=','.join(['[1,2]']*n)
        args=','.join([f'X{i}' for i in range(n)])
        expr='+'.join([f'X{i}' for i in range(n)]+['A'])
        case('higher_order_modes',f'foldl(step,{lists},0,R)','R',f'step({args},A,B):-B is {expr}.')
    case('higher_order_modes','maplist(=(a),L)','L',limit=4)
    case('higher_order_modes','maplist(=,A,B)','A-B',limit=4)
    case('higher_order_modes','foldl(step,L,0,N)','L-N','step(a,A,B):-B is A+1.',limit=4)
    case('higher_order_modes','maplist(choose,[X,Y])','X-Y','choose(a). choose(b).')
    case('higher_order_modes','maplist(choose,[X,Y])','X-Y','choose(a):-!. choose(b).')
    case('higher_order_modes','catch(maplist(boom,[a,b]),E,true)','E','boom(a). boom(b):-throw(ball).')
    for n in range(0,8):
        extra=','.join(['a']*n)
        goal='call(p'+(','+extra if extra else '')+')'
        head='p'+('('+extra+')' if extra else '')
        case('closure_modes',goal,'ok',head+'.')
    for goal in ['maplist(42,[])','maplist(42,[a])','maplist(C,[a])',
                 'maplist(=,[a],[a,b])','maplist(=,[a|b],[a])',
                 'foldl(42,[],a,R)','foldl(C,[a],0,R)',
                 'phrase([a],42)','phrase([a],[a],42)','phrase(B,[])']:
        case('mode_errors',f'catch(({goal}),error(Form,_),true)','Form')
    for body,inp in [('[a],[b]','[a,b]'),('([a];[b])','[b]'),
                     ('([a]->[b];[c])','[a,b]'),('!,[a]','[a]'),
                     ('{X=a},[X]','[a]'),('\\+ [b],[a]','[a]')]:
        case('dcg_modes',f'phrase(word,{inp})','ok',f'word --> {body}.')
    case('dcg_modes','phrase(word,[a,b],Rest)','Rest','word --> [a].')
    case('dcg_modes','phrase(word,L)','L','word --> [a];[b].')
