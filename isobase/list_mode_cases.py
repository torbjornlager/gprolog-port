"""Selected list/remainder and integer-relation modes; cycles use bounded goals."""
def add_cases(case):
    goals = []
    for name,base in [('nth0',0),('nth1',1)]:
        for args in [
            f'{base},[a,b],E,R', f'{base+1},[a,b],E,R',
            f'{base+2},[a,b],E,R', 'N,[a,a],a,R', 'N,L,x,[a,b]',
            f'{base},L,x,tail', f'{base+1},L,x,tail',
            'N,[a,b],E,[b]', 'N,[a,b],E,[wrong]',
            f'{base},[a|bad],E,R', f'{base+1},[a|bad],E,R',
            'N,[a,b|bad],E,R', 'N,bad,E,R', 'N,[],E,R',
            f'{base},[a|T],E,R', f'{base+1},[a|T],E,[]',
            '-1,[],E,R', '0,[],E,R', 'bad,[],E,R', '1.0,[],E,R',
            'f(x),bad,E,R', 'N,[a,b],E,bad']:
            goals.append(f'{name}({args})')
        for args in ['N,[],E','N,bad,E','N,[a,b|bad],E',
                     f'{base},[a|bad],E',f'{base+1},[a|bad],E',
                     '-1,[],E','bad,[],E','1.0,[],E',f'{base},L,E']:
            goals.append(f'{name}({args})')
    for args in ['A,B','0,B','A,0','A,1','1,2','1,3','-1,B','A,-1',
                 '-1,-1','bad,B','A,bad','1.0,B','A,1.0','bad,bad',
                 '0,bad','bad,0','-1,bad','bad,-1','0,1.0','1.0,0']:
        goals.append(f'succ({args})')
    for args in ['1,3,N','3,1,N','1,1,N','-2,1,N','1,3,2','1,3,4',
                 '1,3,2.0','1,3,bad','L,3,N','1,H,N','L,H,2',
                 'bad,3,N','1,bad,N','1.0,3,N','1,3.0,N','bad,bad,bad',
                 '3,1,bad','3,1,2.0','L,bad,N','bad,H,N',
                 '1,inf,3','1,infinite,3','1,inf,0','1,infinite,bad']:
        goals.append(f'between({args})')
    goals += ['member(X,[])','member(X,bad)','member(X,[a,b|bad])',
              'member(a,[a,a])','append([],bad,R)','append([a],bad,R)',
              'append([a|bad],B,R)','append(A,B,[a|bad])',
              'select(X,[a,a],R)','select(X,[a,b|bad],R)',
              'select(X,bad,R)','select(x,L,[a,b])']
    for goal in goals:
        case('list_modes',f'catch(({goal}),error(Form,_),true)',
             f'result(({goal}),Form)',limit=12)
    # Never enumerate an unbounded cycle on either reference or candidate.
    for goal,template in [
        ('L=[a,b|L],nth0(5,L,E)','E'),
        ('L=[a,b|L],nth1(6,L,E)','E'),
        ('L=[a,b|L],nth0(2,L,E,R),once(member(b,R))','E'),
        ('L=[a,b|L],nth1(3,L,E,R),once(member(b,R))','E'),
        ('L=[a|L],once(member(E,L))','E'),
        ('L=[a|L],once(select(E,L,R)),once(member(X,R))','E-X'),
        ('X=f(X),nth0(0,[X],E),E=X','ok'),
        ('X=f(X),nth1(1,[X],E,[])','ok'),
        ('L=[a|L],append([b],L,R),nth0(3,R,E)','E')]:
        case('list_cycles',goal,template)

    for goal,template in [
        ('between(-1,inf,N)','N'),('between(2,infinite,N)','N'),
        ('once((between(3,inf,N),N<6))','N'),
        ('call(between,1,inf,N)','N')]:
        case('list_modes',goal,template,limit=3)
    for goal in ['succ(1,bad)','succ(1,2.0)','succ(1,f(x))',
                 'between(L,inf,N)','between(bad,inf,N)',
                 'between(1,inf,1.0)','between(1,infinite,-1)']:
        case('list_modes',f'catch(({goal}),error(Form,_),true)',
             f'result(({goal}),Form)')
    for goal in ['nth0(X,[],E)','nth1(X,[],E)',
                 'nth0(X,[],E,R)','nth1(X,[],E,R)',
                 'succ(X,N)','succ(N,X)','between(X,2,N)',
                 'between(1,X,N)','between(1,2,X)','between(1,inf,X)']:
        # GNU uses a finite representation error for cyclic error culprits.
        case('list_cycle_errors',f'X=f(X),catch(({goal}),error(_,_),Status=caught)','Status')
