"""Selected acyclic term and all-solutions argument modes."""
def add_cases(case):
    goals=[]
    for args in ['T,F,N','T,f,0','T,12,0','T,1.5,0','T,[],0','T,f,2',
                 'T,F,2','T,f,N','T,f,-1','T,f,1.5','T,f,bad','T,f(x),0',
                 'T,12,1','f(a,b),F,N','f(a),f,2','f(a),bad,bad','a,F,N']:
        goals.append(f'functor({args})')
    for args in ['N,f(a,b),X','0,f(a),X','-1,f(a),X','1,T,X','N,T,X',
                 'N,a,X','1,a,X','bad,a,X','1.0,f(a),X','2,f(a),X','N,f(a,a),a']:
        goals.append(f'arg({args})')
    for goal in ['T=..L','T=..[]','T=..[f]','T=..[12]','T=..[1.5]',
                 'T=..[f,a,b]','T=..[F,a]','T=..[12,a]','T=..[f|Tail]',
                 'T=..[f|bad]','T=..bad','f(a)=..[F|Tail]','f(a)=..bad',
                 'f(a)=..[bad|Tail]','f(a)=..[f|bad]',
                 'copy_term(f(A,A),f(B,C)),B==C,A\\==B',
                 'copy_term(f(A,B),f(C,C)),var(A),var(B),A\\==B',
                 'copy_term(f(a),f(b))','copy_term(X,Y),X\\==Y',
                 'term_variables(f(A,B,A,C),L)','term_variables(T,L)',
                 'term_variables(f(A,B),[A,B])','term_variables(f(A,B),[B,A])',
                 'term_variables(f(A),[])','term_variables(f(A),bad)',
                 'term_variables(f(A),[X|bad])']:
        goals.append(goal)
    for args in ['O,a,b','O,1,1.0','O,1.0,1','O,f(a),g(a)',
                 'O,f(a,b),g(a)','bad,a,b','1,a,b','(<),a,b','(>),a,b',
                 'O,X,X']:
        goals.append(f'compare({args})')
    for pred in ['sort','keysort']:
        inputs=['L','[]','bad','[a|T]','[a|bad]']
        inputs += ['[b,a,a]','[1,1.0]','[f(b),f(a)]'] if pred=='sort' else ['[b-1,a-2,a-3]','[a]','[X]','[1-1,1.0-2]']
        for inp in inputs:goals.append(f'{pred}({inp},R)')
        for output in ['bad','[]','[X|bad]','[X|T]']:
            goals.append(f'{pred}([], {output})')
    for pred in ['findall','bagof','setof']:
        for args in ['X,fail,L','X,member(X,[b,a,a]),L','X,true,L',
                     'X,member(K-X,[a-1,b-2,a-3]),L',
                     'X,K^member(K-X,[a-1,b-2,a-3]),L',
                     'X,(X=a;throw(ball)),L','X,fail,bad','X,true,bad',
                     'X,true,[]','X,true,[a]','X,member(X,[a,b]),[a|T]',
                     'X,member(X,[a,b]),[a|bad]']:
            # findall does not interpret existential ^ as an operator.
            if pred=='findall' and 'K^' in args:continue
            goals.append(f'{pred}({args})')
    goals += ['f(a)=..[f,a|bad]','f(a)=..[bad|bad]','f(a)=..[f,b|bad]',
              'a=..[a|bad]','f(a)=..[f,a,b]','arg(bad,T,X)',
              'arg(-1,a,X)','arg(0,a,X)','arg(1.0,a,X)',
              'sort([b,a],bad)','keysort([b-1,a-2],bad)',
              'term_variables(f(A,B),[X,X])',
              'copy_term(f(A,A),C),C=f(B,D),B=x,D==x,var(A)',
              'findall(f(X,X),member(X,[A,B]),[f(P,Q),f(R,S)]),P==Q,R==S,P\\==R,var(A),var(B)',
              'bagof(X,member(K-X,[b-1,a-2,b-3]),L)',
              'setof(X,member(K-X,[b-1,a-2,b-1]),L)',
              'bagof(X,K^(member(K,[a,b]),X=K),L)',
              'setof(X,(X=1;X=1.0;X=1),L)']
    for pred in ['findall','bagof','setof']:
        for output in ['bad','[]','[a|bad]']:
            goals.append(f'{pred}(X,throw(ball),{output})')
        goals.append(f'{pred}(X,(X=a;X=b),[b])')
    for goal in goals:
        case('term_modes',f'catch(({goal}),Ball,(Ball=error(Form,_)->E=error(Form);E=Ball))',f'r(({goal}),E)',limit=12)
    for goal in [
        '1@<1.0','1.0@<1','1@=<1','f(a)@<f(b)','f(a)@>a','f(a)@>=f(a)',
        'f(X,X)==f(X,X)','f(X,X)\\==f(X,Y)',
        'subsumes_term(f(X,X),f(a,a)),var(X)',
        'subsumes_term(f(X,X),f(a,b))',
        'unify_with_occurs_check(X,f(X))',
        'unify_with_occurs_check(f(X,X),f(a,a)),X==a',
        'copy_term(f(A,B),f(X,Y)),A\\==X,B\\==Y,X\\==Y',
        'term_variables(f(A,g(B,A),C,B),[A,B,C])',
        'sort([X,X],L),L=[X],var(X)',
        'keysort([a-X,a-Y],L),L=[a-X,a-Y],X\\==Y',
        'findall(X,(X=a;X=b),L),var(X),L==[a,b]',
        'bagof(X,(X=b;X=a;X=b),L),var(X),L==[b,a,b]',
        'setof(X,(X=b;X=a;X=b),L),var(X),L==[a,b]',
        'findall(X,findall(Y,member(Y,[a,b]),X),L),L==[[a,b]]',
    ]:
        case('term_sharing_order',goal)
