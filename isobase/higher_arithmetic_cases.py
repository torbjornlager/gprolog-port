"""Selected higher-order aliasing, error timing and arithmetic modes."""
def add_cases(case):
    goals=[]
    for args in ['=,[],bad','=,bad,[]','=,[a|bad],[a]','=,[a],[b|bad]',
                 '=,[a|T],[a,b]','=,[X,X],[a,b]','C,[],[]','C,[],[a]',
                 'C,[a],[]','C,[a],[a]','42,[],[]','42,[a],[]',
                 '42,[a],[a]','atom,[a|bad]','atom,bad']:
        goals.append(f'maplist({args})')
    for args in ['C,[],a,R','C,bad,a,R','C,[a],a,R','42,[],a,R',
                 '42,[a],a,R','step,[1,2],0,R','step,[1|bad],0,R',
                 'step,[],0,bad','step,[1],0,2','step,[1],0,1']:
        goals.append(f'foldl({args})')
    for expr in ['X+(1/0)','(1/0)+X','f(X)+X','X+f(X)','f(X)','X','a','f(1)','1+X','X+f(1)','1.5//2','1//2.0',
                 '1 mod 0','1 rem 0','1 div 0','1.0 mod 2','1<<(-1)',
                 '1>>(-1)','(-2)^(-1)','(-2)**0.5','0^(-1)',
                 'floor(1.5)','round(-1.5)','ceiling(-1.5)','truncate(-1.5)',
                 'float_fractional_part(-1.5)','asin(2)','acos(2)','atan2(0,0)',
                 'round(-0.49999999999999994)','round(0.49999999999999994)','round(-0.5000000000000001)','round(0.5000000000000001)','round(-2.5)','round(-1.4)','round(-1.6)','round(-0.5)','round(0.5)','0**(-1)','0.0^(-1)','atan2(-0.0,0.0)','atan2(0.0,-0.0)','atan2(-0.0,-0.0)','max(1,1.0)','max(1.0,1)','min(1,1.0)','min(1.0,1)']:
        goals.append(f'R is {expr}')
    for goal in ['a is 1','1 is 1.0','1.0 is 1','R is 1/2','R is 0.0/(-1)',
                 'X=:=1','a<1','1<bad','X<bad','bad<X','1.0=:=1',
                 '1.0=\\=1','1=<1.0','1.0>=1']:
        goals.append(goal)
    for goal in goals:
        case('higher_arithmetic_modes',f'catch(({goal}),error(Form,_),true)',
             f'r(({goal}),Form)','step(X,A,B):-B is X+A.',limit=8)
    for goal in [
        'maplist(run([a]),[L])','maplist(run(([],[a])),[L])',
        'G=[a],maplist(run(G),[L])','foldl(add,[1,2,3],0,R)',
        'call(foldl,add,[1,2,3],0,R)',
        'maplist(choose,[X,Y])','maplist(choose,[X,X])',
        'catch(maplist(boom,[a,b]),ball,true)',
    ]:
        source='run(G,L):-phrase(G,L). add(X,A,B):-B is X+A. choose(a). choose(b). boom(a). boom(b):-throw(ball).'
        case('higher_context',goal,goal,source,limit=8)

    for template in ['(a,b)','(a;b)','(a->b)','(a:-b)','[a,b]','f((a,b))']:
        case('template_precedence','member(X,[a,b])',template,limit=1)
